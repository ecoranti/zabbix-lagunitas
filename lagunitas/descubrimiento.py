"""Descubrimiento de equipos: detectar y proponer.

Escanea un rango de IPs con el *network discovery* nativo de Zabbix (ICMP, SNMP v2c y
HTTPS), clasifica lo que responde (airMAX, Mikrotik, otro) y lo compara con el inventario.
No crea hosts: genera el bloque YAML para pegar en config/inventory.*.yaml, que sigue siendo
la fuente única de verdad. Después se aplica con `bin/lagunitas aprovisionar`.

La misma regla de descubrimiento la usa la página web *Monitoring -> Descubrimiento de
equipos* (módulo zabbix/modules/lagunitas-descubrimiento). La clasificación está replicada en
DescubrimientoService.php: si se cambia acá, cambiarla también allá.
"""
from __future__ import annotations

import ipaddress
import json
import os
import re
import time

from .zbx import ZabbixAPI

REGLA_NOMBRE = "Las Lagunitas - Escaneo bajo demanda"
# La regla queda activa para que los resultados sigan visibles; se reescanea una vez por día
# hasta el próximo escaneo manual, que la vuelve a crear desde cero.
REGLA_INTERVALO = "1d"
MACRO_COMUNIDAD = "{$SNMP_COMMUNITY}"
MAX_DIRECCIONES = 1024

OID_DESCR = "1.3.6.1.2.1.1.1.0"
OID_OBJETO = "1.3.6.1.2.1.1.2.0"
OID_NOMBRE = "1.3.6.1.2.1.1.5.0"

# Tipos de check de Zabbix (SVC_*)
SVC_SNMPV2C, SVC_ICMP, SVC_HTTPS = 11, 12, 14

# Prefijos de sysObjectID
OID_UBIQUITI = ("1.3.6.1.4.1.10002.", "1.3.6.1.4.1.41112.")
OID_MIKROTIK = ("1.3.6.1.4.1.14988.",)


def dchecks(comunidad: str = MACRO_COMUNIDAD) -> list[dict]:
    snmp = {"type": SVC_SNMPV2C, "ports": "161", "snmp_community": comunidad}
    return [
        {"type": SVC_ICMP},
        {**snmp, "key_": OID_DESCR},
        {**snmp, "key_": OID_OBJETO},
        {**snmp, "key_": OID_NOMBRE},
        {"type": SVC_HTTPS, "ports": "443"},
    ]


# ------------------------------------------------------------------ rangos de IP
def direcciones(rango: str) -> list[ipaddress.IPv4Address]:
    """Expande un rango con la sintaxis que acepta Zabbix: 10.50.0.0/24 (hasta /30), 10.50.0.1-60
    (rango en el último octeto) e IPs sueltas, separados por comas."""
    out: list[ipaddress.IPv4Address] = []
    for parte in (p.strip() for p in rango.split(",")):
        if not parte:
            continue
        try:
            if "/" in parte:
                red = ipaddress.IPv4Network(parte, strict=False)
                if red.prefixlen > 30:
                    raise ValueError("Zabbix acepta máscaras hasta /30; para un solo equipo poné la IP sola")
                out.extend(red.hosts())
            elif "-" in parte:
                ini, fin = parte.rsplit("-", 1)
                a = ipaddress.IPv4Address(ini)
                if not fin.isdigit() or int(fin) > 255:
                    raise ValueError("el rango va en el último octeto, ej. 10.50.0.1-60")
                b = ipaddress.IPv4Address(f"{str(a).rsplit('.', 1)[0]}.{fin}")
                if b < a:
                    raise ValueError("el final del rango es menor que el inicio")
                out.extend(ipaddress.IPv4Address(i) for i in range(int(a), int(b) + 1))
            else:
                out.append(ipaddress.IPv4Address(parte))
        except ValueError as exc:
            raise ValueError(f"rango inválido {parte!r}: {exc}") from exc
        if len(out) > MAX_DIRECCIONES:
            raise ValueError(f"el rango supera {MAX_DIRECCIONES} direcciones; escaneá por partes (ej. /24)")
    if not out:
        raise ValueError("rango vacío")
    return out


# ------------------------------------------------------------------ regla de Zabbix
def ensure_comunidad(api: ZabbixAPI, log=print) -> None:
    """Macro global {$SNMP_COMMUNITY} (secreta) para la regla de descubrimiento.

    Los hosts tienen su propia macro con el mismo nombre; la global solo la usa el escaneo.
    """
    valor = os.environ.get("SNMP_COMMUNITY")
    actual = api.call("usermacro.get", {"globalmacro": True, "filter": {"macro": MACRO_COMUNIDAD}})
    spec = {"type": 1, "description": "Comunidad SNMP v2c usada por el escaneo de descubrimiento de equipos"}
    if actual:
        if valor:  # sin SNMP_COMMUNITY en .env se conserva el valor cargado a mano
            api.call("usermacro.updateglobal", {"globalmacroid": actual[0]["globalmacroid"], "value": valor, **spec})
        return
    if not valor:
        log("  [aviso] SNMP_COMMUNITY no definida: el escaneo usará la comunidad 'public'")
    api.call("usermacro.createglobal", {"macro": MACRO_COMUNIDAD, "value": valor or "public", **spec})


def iniciar(api: ZabbixAPI, rango: str, comunidad: str | None = None) -> str:
    """(Re)crea la regla con el rango indicado. Recrearla descarta los resultados anteriores
    y hace que el Zabbix server la ejecute apenas sincroniza la configuración (~10-60 s)."""
    direcciones(rango)
    viejas = api.call("drule.get", {"filter": {"name": [REGLA_NOMBRE]}, "output": ["druleid"]})
    if viejas:
        api.call("drule.delete", [d["druleid"] for d in viejas])
    r = api.call("drule.create", {"name": REGLA_NOMBRE, "iprange": rango.replace(" ", ""),
                                  "delay": REGLA_INTERVALO, "status": 0,
                                  "dchecks": dchecks(comunidad or MACRO_COMUNIDAD)})
    return r["druleids"][0]


def regla(api: ZabbixAPI) -> dict | None:
    r = api.call("drule.get", {"filter": {"name": [REGLA_NOMBRE]}, "output": ["druleid", "iprange"],
                               "selectDChecks": ["dcheckid", "type", "key_"]})
    return r[0] if r else None


def resultados(api: ZabbixAPI, druleid: str | None = None) -> list[dict]:
    """Equipos que respondieron al último escaneo, una entrada por IP."""
    r = regla(api) if druleid is None else api.call("drule.get", {
        "druleids": [druleid], "output": ["druleid", "iprange"],
        "selectDChecks": ["dcheckid", "type", "key_"]})[0]
    if not r:
        return []
    campo = {}
    for c in r["dchecks"]:
        t = int(c["type"])
        campo[c["dcheckid"]] = {SVC_ICMP: "icmp", SVC_HTTPS: "https"}.get(t) or {
            OID_DESCR: "descr", OID_OBJETO: "objeto", OID_NOMBRE: "nombre"}.get(c["key_"], "snmp")
    equipos: dict[str, dict] = {}
    for dh in api.call("dhost.get", {"druleids": [r["druleid"]], "output": ["dhostid"],
                                     "selectDServices": ["dcheckid", "ip", "dns", "value", "status",
                                                         "lastup"]}):
        for s in dh["dservices"]:
            if s["status"] != "0":
                continue
            e = equipos.setdefault(s["ip"], {"ip": s["ip"], "dns": s.get("dns", ""), "servicios": {},
                                             "visto": 0})
            e["servicios"][campo.get(s["dcheckid"], "otro")] = s.get("value", "")
            e["visto"] = max(e["visto"], int(s.get("lastup") or 0))
    out = [clasificar(e) for e in equipos.values()]
    return sorted(out, key=lambda e: ipaddress.IPv4Address(e["ip"]))


def esperar(api: ZabbixAPI, druleid: str, timeout: int = 300, estable: int = 30, log=print) -> list[dict]:
    """Espera hasta que aparezcan resultados y dejen de cambiar durante `estable` segundos."""
    inicio, ultima_firma, desde = time.time(), None, None
    res: list[dict] = []
    while time.time() - inicio < timeout:
        res = resultados(api, druleid)
        firma = tuple((e["ip"], tuple(sorted(e["servicios"]))) for e in res)
        if res and firma == ultima_firma:
            if time.time() - desde >= estable:
                return res
        else:
            ultima_firma, desde = firma, time.time()
            log(f"  ... {len(res)} equipos respondieron ({int(time.time() - inicio)} s)")
        time.sleep(5)
    return res


# ------------------------------------------------------------------ clasificación
def nombre_tecnico(texto: str) -> str:
    t = re.sub(r"[^A-Za-z0-9_.-]+", "_", texto.strip()).strip("_")
    return t[:60] or "Equipo"


def clasificar(e: dict) -> dict:
    """Agrega tipo, perfiles, función y modelo sugeridos según lo que respondió el equipo."""
    s = e["servicios"]
    descr, objeto, nombre = s.get("descr", ""), s.get("objeto", ""), s.get("nombre", "")
    objeto = objeto.lstrip(".")
    snmp = any(k in s for k in ("descr", "objeto", "nombre", "snmp"))
    e.update(snmp=snmp, https="https" in s, icmp="icmp" in s, sysname=nombre, sysdescr=descr,
             funcion=None, modelo="")
    d = descr.lower()
    if "routeros" in d or objeto.startswith(OID_MIKROTIK):
        modelo = descr.split("RouterOS", 1)[-1].strip() if "RouterOS" in descr else ""
        e.update(tipo="mikrotik", tipo_texto="Router Mikrotik (SNMP)", perfiles=["icmp", "mikrotik_snmp"],
                 funcion="router", modelo=f"Mikrotik {modelo}".strip())
    elif objeto.startswith(OID_UBIQUITI) or "airos" in d or "ubnt" in d:
        e.update(tipo="airmax", tipo_texto="Radio Ubiquiti airMAX (SNMP)", perfiles=["icmp", "airos_snmp"])
    elif snmp:
        e.update(tipo="snmp", tipo_texto="Responde SNMP (no es airMAX ni Mikrotik)", perfiles=["icmp"])
    elif e["https"]:
        e.update(tipo="web", tipo_texto="Gestión web, sin SNMP (UniFi, airCube u otro)", perfiles=["icmp"])
    else:
        e.update(tipo="ping", tipo_texto="Solo responde ping", perfiles=["icmp"])
    dns = e.get("dns") or ""
    if nombre:
        base = nombre
    elif dns and dns != e["ip"]:
        base = dns.split(".")[0]
    else:
        base = "Equipo_" + e["ip"].replace(".", "_")
    e["host_sugerido"] = nombre_tecnico(base)
    return e


def _yaml_texto(t: str) -> str:
    """Comillas solo si el texto puede romper el YAML (':' '#' o caracteres especiales al inicio)."""
    t = t.replace("\r", " ").replace("\n", " ")
    return json.dumps(t, ensure_ascii=False) if re.search(r"[:#]|^[\s\-?\[\]{},&*!|>'\"%@`]", t) else t


# ------------------------------------------------------------------ comparación con el inventario
def comparar(equipos: list[dict], inv: dict, rango: str) -> dict:
    por_ip = {str(x.get("ip")): x for x in inv["todos"]}
    en_rango = {str(ip) for ip in direcciones(rango)}
    nuevos, conocidos = [], []
    for e in equipos:
        x = por_ip.get(e["ip"])
        if x is None:
            nuevos.append(e)
            continue
        faltan = [p for p in e["perfiles"] if p not in x["perfiles"] and p != "icmp"]
        conocidos.append({**e, "host": x["host"], "faltan_perfiles": faltan})
    vistos = {e["ip"] for e in equipos}
    ausentes = [x for ip, x in por_ip.items() if ip in en_rango and ip not in vistos
                and x.get("estado") == "operativo"]
    return {"nuevos": nuevos, "conocidos": conocidos, "ausentes": ausentes}


def propuesta_yaml(nuevos: list[dict], hosts_existentes: set[str] | None = None) -> str:
    """Bloque para pegar en `dispositivos:` de un sitio (o en `elementos:` agregando rol y mapa)."""
    usados = set(hosts_existentes or ())
    lineas = []
    for e in nuevos:
        host, n = e["host_sugerido"], 2
        while host in usados:
            host, n = f"{e['host_sugerido']}_{n}", n + 1
        usados.add(host)
        lineas += [
            (f"  # {e['ip']} — {e['tipo_texto']}" + (f" — {e['sysdescr']}" if e.get("sysdescr") else ""))
            .replace("\n", " ").replace("\r", " "),
            f"  - host: {host}",
            f"    nombre: {_yaml_texto(e['sysname'] or host.replace('_', ' '))}",
            f"    ip: {e['ip']}",
            f"    perfiles: [{', '.join(e['perfiles'])}]",
            f"    funcion: {e['funcion']}" if e["funcion"] else "    funcion: COMPLETAR   # ap | sm | ptp | router | switch | otro",
            f"    modelo: {_yaml_texto(e['modelo'])}" if e["modelo"] else "    modelo: COMPLETAR",
            "    padre: COMPLETAR      # equipo del que depende (por defecto, el principal del sitio)",
            "",
        ]
    if not lineas:
        return ""
    return ("# Propuesta generada por `bin/lagunitas descubrir`. Pegar dentro de 'dispositivos:'\n"
            "# del sitio correspondiente (o en 'elementos:' agregando rol, estado y mapa),\n"
            "# completar lo marcado y aplicar con `bin/lagunitas aprovisionar`.\n"
            + "\n".join(lineas))
