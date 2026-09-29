"""Simulador del laboratorio: un contenedor Alpine por equipo operativo del inventario.

Cada contenedor responde ICMP en su IP fija de la red Docker 'lagunitas_net'. Los
equipos con perfil SNMP (airos_snmp / mikrotik_snmp) corren además un agente SNMP
simulado (lab/snmpsim) que responde con los OIDs reales del fabricante, para validar
templates, triggers y dashboards sin hardware.
Se crean con restart=unless-stopped (sobreviven a reinicios de Colima/Docker) y
sin --rm, así que simular una caída es 'docker stop' y recuperarla 'docker start'.
"""
from __future__ import annotations

import ipaddress
import json
import subprocess

RED = "lagunitas_net"
SUBRED = "10.50.0.0/24"
from .config import ROOT

IMAGEN = "alpine:3.20"
IMAGEN_SNMP = "lagunitas/snmpsim:lab"
VERSION_SNMPSIM = "2"  # subir si cambia la imagen, para recrear los contenedores

AIROS = "1.3.6.1.4.1.41112.1.4"
STA = "1.24.232.41.138.27.44"  # índice de la estación simulada
# Escenarios de falla para validar alertas y demostrar el sistema: {nombre: (perfiles, [(OID, "tipo|valor")])}
ESCENARIOS = {
    "senal-debil": (("airmax-ap", "airmax-sm"), [
        (f"{AIROS}.5.1.5.1", "2|-78"), (f"{AIROS}.7.1.3.{STA}", "2|-79"), (f"{AIROS}.5.1.7.1", "2|82")]),
    "senal-critica": (("airmax-ap", "airmax-sm"), [
        (f"{AIROS}.5.1.5.1", "2|-86"), (f"{AIROS}.7.1.3.{STA}", "2|-87"), (f"{AIROS}.5.1.7.1", "2|64"),
        (f"{AIROS}.6.1.3.1", "2|48"), (f"{AIROS}.6.1.4.1", "2|25")]),
    "interferencia": (("airmax-ap", "airmax-sm"), [
        (f"{AIROS}.5.1.8.1", "2|-74"), (f"{AIROS}.5.1.7.1", "2|58"), (f"{AIROS}.6.1.3.1", "2|52"),
        (f"{AIROS}.6.1.4.1", "2|33")]),
    "sin-estaciones": (("airmax-ap",), [(f"{AIROS}.5.1.15.1", "2|0")]),
    "bateria-baja": (("mikrotik",), [("1.3.6.1.4.1.14988.1.1.3.8.0", "2|118")]),
    "bateria-critica": (("mikrotik",), [("1.3.6.1.4.1.14988.1.1.3.8.0", "2|113")]),
    "sin-internet": (("mikrotik",), [("1.3.6.1.2.1.2.2.1.8.7", "2|2")]),
    "sin-clientes": (("mikrotik",), [("1.3.6.1.4.1.14988.1.1.6.1.0", "2|0")]),
}
LABEL = "ar.lagunitas.lab=1"


def _docker(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=check)


def _en_subred(ip: str) -> bool:
    return ipaddress.ip_address(ip) in ipaddress.ip_network(SUBRED)


def simulables(inv: dict, todos: bool = False) -> list[dict]:
    """Elementos que se simulan con contenedor (los que tienen IP de la red de LAB)."""
    return [e for e in inv["todos"]
            if _en_subred(str(e["ip"])) and (todos or e["estado"] == "operativo")]


def perfil_simulado(e: dict) -> str:
    """Qué simula el contenedor: icmp, airmax-ap, airmax-sm o mikrotik."""
    if "mikrotik_snmp" in e["perfiles"]:
        return "mikrotik"
    if "airos_snmp" in e["perfiles"]:
        return "airmax-ap" if e["funcion"] == "ap" else "airmax-sm"
    return "icmp"


def _remoto(inv: dict, e: dict) -> dict:
    """Equipo del otro extremo del enlace de radio (para la tabla de estaciones simulada)."""
    if e["funcion"] == "ap":
        hijos = [x for x in inv["todos"] if x.get("padre") == e["host"]]
        return hijos[0] if hijos else e
    return inv["por_host"].get(e.get("padre") or "", e)


def _asegurar_imagen_snmp(log) -> None:
    if _docker("image", "inspect", IMAGEN_SNMP, check=False).returncode != 0:
        log("  construyendo la imagen del agente SNMP simulado...")
        _docker("build", "-q", "-t", IMAGEN_SNMP, str(ROOT / "lab" / "snmpsim"))


def _contenedores() -> dict[str, dict]:
    out = _docker("ps", "-a", "--format", "{{json .}}").stdout.splitlines()
    res = {}
    for line in out:
        c = json.loads(line)
        res[c["Names"]] = c
    return res


def ensure_red(log=print) -> None:
    if _docker("network", "inspect", RED, check=False).returncode != 0:
        _docker("network", "create", "--subnet", SUBRED, RED)
        log(f"  red {RED} ({SUBRED}) creada")


def levantar(inv: dict, log=print) -> None:
    ensure_red(log)
    existentes = _contenedores()
    deseados = {e["host"]: e for e in simulables(inv)}
    if any(perfil_simulado(e) != "icmp" for e in deseados.values()):
        _asegurar_imagen_snmp(log)
    for nombre, e in deseados.items():
        c = existentes.get(nombre)
        perfil = perfil_simulado(e)
        etiqueta_perfil = f"ar.lagunitas.perfil={perfil}-v{VERSION_SNMPSIM}"
        if c and (LABEL.split("=")[0] not in c.get("Labels", "")
                  or etiqueta_perfil not in c.get("Labels", "")):
            _docker("rm", "-f", nombre)  # contenedor v1 o de otro perfil: se recrea
            c = None
        if c is None:
            base = ["run", "-d", "--name", nombre, "--hostname", nombre, "--network", RED,
                    "--ip", str(e["ip"]), "--restart", "unless-stopped", "--label", LABEL,
                    "--label", f"ar.lagunitas.rol={e['rol']}", "--label", etiqueta_perfil]
            if perfil == "icmp":
                _docker(*base, "--memory", "16m", IMAGEN, "sleep", "infinity")
            else:
                r = _remoto(inv, e)
                _docker(*base, "--memory", "96m", "-e", f"PERFIL={perfil}", "-e", f"NOMBRE={nombre}",
                        "-e", f"MODELO={e.get('modelo') or 'Ubiquiti airMAX'}", "-e", f"REMOTO={r['nombre']}",
                        "-e", f"IPREMOTA={r['ip']}", IMAGEN_SNMP)
            log(f"  creado     {nombre:<26} {e['ip']:<12} {perfil}")
        elif not c["State"] == "running":
            _docker("start", nombre)
            log(f"  iniciado   {nombre:<26} {e['ip']}")
    # Equipos que dejaron de estar operativos en el inventario.
    for nombre, c in existentes.items():
        if LABEL.split("=")[0] in c.get("Labels", "") and nombre not in deseados:
            _docker("rm", "-f", nombre)
            log(f"  eliminado  {nombre} (ya no está operativo en el inventario)")
    log(f"  {len(deseados)} equipos simulados en {RED}")


def apagar(log=print) -> None:
    for nombre, c in _contenedores().items():
        if LABEL.split("=")[0] in c.get("Labels", "") and c["State"] == "running":
            _docker("stop", "-t", "1", nombre)
            log(f"  detenido   {nombre}")


def descendientes(inv: dict, nombre: str) -> list[str]:
    """Equipos que dependen (directa o indirectamente) del dado, según el inventario."""
    hijos: dict[str, list[str]] = {}
    for e in inv["todos"]:
        if e.get("padre"):
            hijos.setdefault(e["padre"], []).append(e["host"])
    out, pila = [], list(hijos.get(nombre, []))
    while pila:
        h = pila.pop(0)
        if h not in out:
            out.append(h)
            pila.extend(hijos.get(h, []))
    return out


def _afectados(inv: dict, nombre: str, solo: bool) -> list[str]:
    if nombre not in inv["por_host"]:
        raise SystemExit(f"'{nombre}' no está en el inventario")
    existentes = _contenedores()
    # En la red real, si cae un equipo sus descendientes pierden el camino: en el LAB
    # se simula deteniendo también sus contenedores (salvo --solo).
    return [h for h in [nombre] + ([] if solo else descendientes(inv, nombre)) if h in existentes]


def caida(inv: dict, nombre: str, solo: bool = False, log=print) -> None:
    afectados = _afectados(inv, nombre, solo)
    for h in afectados:
        _docker("stop", "-t", "1", h)
    log(f"  {nombre} detenido" + (f" (+{len(afectados) - 1} equipos aguas abajo sin camino: "
                                  f"{', '.join(afectados[1:])})" if len(afectados) > 1 else ""))
    log("  Zabbix lo detecta en ~90 s: una sola alerta (la de la causa raíz); los equipos aguas "
        "abajo quedan 'Sin servicio' sin generar alertas propias.")


def recuperar(inv: dict, nombre: str, solo: bool = False, log=print) -> None:
    afectados = _afectados(inv, nombre, solo)
    for h in afectados:
        _docker("start", h)
    log(f"  {', '.join(afectados)} iniciado(s): el problema se resuelve solo en ~30-60 s")


def escenario(inv: dict, nombre: str, escenario_: str, log=print) -> None:
    """Aplica un escenario de falla al agente SNMP simulado de un equipo (o 'normal')."""
    if nombre not in inv["por_host"]:
        raise SystemExit(f"'{nombre}' no está en el inventario")
    perfil = perfil_simulado(inv["por_host"][nombre])
    if perfil == "icmp":
        raise SystemExit(f"{nombre} no tiene agente SNMP simulado (perfil solo icmp)")
    if escenario_ == "normal":
        _docker("exec", nombre, "perfil-reset")
        log(f"  {nombre}: valores normales restaurados")
        return
    if escenario_ not in ESCENARIOS:
        raise SystemExit(f"Escenario desconocido. Disponibles: normal, {', '.join(ESCENARIOS)}")
    perfiles, cambios = ESCENARIOS[escenario_]
    if perfil not in perfiles:
        raise SystemExit(f"El escenario '{escenario_}' aplica a {', '.join(perfiles)}; {nombre} es {perfil}")
    expr = " ".join(f"-e 's#^{oid}|.*#{oid}|{valor}#'" for oid, valor in cambios)
    _docker("exec", nombre, "sh", "-c", f"sed -i {expr} /tmp/snmp/public.snmprec")
    log(f"  {nombre}: escenario '{escenario_}' aplicado. Zabbix lo refleja en 1-15 min según el "
        f"trigger (promedios de 5-15 min). Volver con: bin/lagunitas lab escenario {nombre} normal")


def estado(inv: dict, log=print) -> None:
    existentes = _contenedores()
    for e in simulables(inv, todos=True):
        c = existentes.get(e["host"])
        cont = c["State"] if c else "sin contenedor"
        log(f"  {e['host']:<26} {e['ip']:<12} {perfil_simulado(e):<10} inventario={e['estado']:<15} "
            f"contenedor={cont}")
