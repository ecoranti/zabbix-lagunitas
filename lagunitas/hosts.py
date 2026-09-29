"""Grupos, hosts y dependencias entre triggers a partir del inventario."""
from __future__ import annotations

import os

from .model import ESTADOS, PERFILES, ROLES, SITIO_GRUPO, TPL_ICMP, TPL_UNIFI, TRIGGER_CAIDA
from .zbx import ZabbixAPI

# Objetos de la versión anterior del laboratorio (scripts sueltos, v1).
LEGACY_GRUPOS = ["Red Las Lagunitas - Simulados", "Dispositivos Reales", "Red Las Lagunitas"]
LEGACY_DASHBOARDS = ["Red Las Lagunitas"]
LEGACY_MAPAS = ["Topología Red Las Lagunitas"]


def ensure_hostgroup(api: ZabbixAPI, name: str) -> str:
    found = api.call("hostgroup.get", {"filter": {"name": [name]}, "output": ["groupid"]})
    if found:
        return found[0]["groupid"]
    return api.call("hostgroup.create", {"name": name})["groupids"][0]


def ensure_groups(api: ZabbixAPI) -> dict[str, str]:
    ids = {SITIO_GRUPO: ensure_hostgroup(api, SITIO_GRUPO)}
    for rol in ROLES.values():
        ids[rol["grupo"]] = ensure_hostgroup(api, rol["grupo"])
    return ids


def template_de_disponibilidad(elemento: dict) -> str | None:
    if "icmp" in elemento["perfiles"]:
        return TPL_ICMP
    if "unifi_api" in elemento["perfiles"]:
        return TPL_UNIFI
    return None


def migrar_legacy(api: ZabbixAPI, log=print) -> None:
    """Elimina hosts, dashboard y mapa de la versión v1 (scripts sueltos).

    Los hosts se recrean luego desde el inventario con los mismos nombres técnicos.
    Destructivo: se pierde el historial de los items v1 (hacer backup antes).
    """
    grupos = api.call("hostgroup.get", {"filter": {"name": LEGACY_GRUPOS}, "output": ["groupid", "name"],
                                        "selectHosts": ["hostid", "host"]})
    hostids = sorted({h["hostid"] for g in grupos for h in g["hosts"]})
    if hostids:
        api.call("host.delete", hostids)
        log(f"  eliminados {len(hostids)} hosts v1")
    for name in LEGACY_DASHBOARDS:
        for d in api.call("dashboard.get", {"filter": {"name": [name]}, "output": ["dashboardid"]}):
            api.call("dashboard.delete", [d["dashboardid"]])
            log(f"  eliminado dashboard v1 '{name}'")
    for name in LEGACY_MAPAS:
        for m in api.call("map.get", {"filter": {"name": [name]}, "output": ["sysmapid"]}):
            api.call("map.delete", [m["sysmapid"]])
            log(f"  eliminado mapa v1 '{name}'")
    for g in grupos:
        try:
            api.call("hostgroup.delete", [g["groupid"]])
            log(f"  eliminado grupo v1 '{g['name']}'")
        except Exception as exc:  # noqa: BLE001 - puede estar referenciado por otra config
            log(f"  [aviso] no se pudo borrar el grupo '{g['name']}': {exc}")


def _templateids(api: ZabbixAPI, perfiles: list[str]) -> list[dict]:
    nombres = [t for p in perfiles for t in PERFILES[p]["templates"]]
    found = api.call("template.get", {"filter": {"host": nombres}, "output": ["templateid", "host"]})
    faltan = set(nombres) - {t["host"] for t in found}
    if faltan:
        raise RuntimeError(f"Templates inexistentes en Zabbix: {sorted(faltan)}")
    return [{"templateid": t["templateid"]} for t in found]


def _interfaz(e: dict) -> dict:
    snmp = any(PERFILES[p]["interfaz"] == 2 for p in e["perfiles"])
    base = {"main": 1, "useip": 1, "ip": str(e["ip"]), "dns": ""}
    if snmp:
        return {**base, "type": 2, "port": "161",
                "details": {"version": 2, "bulk": 1, "community": "{$SNMP_COMMUNITY}"}}
    return {**base, "type": 1, "port": "10050"}


def _macros(e: dict, log) -> list[dict] | None:
    """Macros del host. Devuelve None si falta un secreto (no se tocan las existentes)."""
    macros = [{"macro": k, "value": str(v)} for k, v in (e.get("macros") or {}).items()]
    if "unifi_api" in e["perfiles"]:
        key = os.environ.get("UNIFI_API_KEY")
        if not key:
            log(f"  [aviso] {e['host']}: UNIFI_API_KEY no definida; no se actualizan sus macros")
            return None
        macros.append({"macro": "{$UNIFI.API.KEY}", "value": key, "type": 1,
                       "description": "API key de UniFi Network (secreta)"})
    if any(PERFILES[p]["interfaz"] == 2 for p in e["perfiles"]):
        community = os.environ.get("SNMP_COMMUNITY")
        if not community:
            log(f"  [aviso] {e['host']}: SNMP_COMMUNITY no definida; no se actualizan sus macros")
            return None
        macros.append({"macro": "{$SNMP_COMMUNITY}", "value": community, "type": 1})
    return macros


def ensure_hosts(api: ZabbixAPI, inv: dict, groups: dict[str, str], log=print) -> dict[str, str]:
    sitio = inv.get("sitio", "Las Lagunitas")
    hostids: dict[str, str] = {}
    for e in inv["todos"]:
        rol = ROLES[e["rol"]]
        estado = ESTADOS[e["estado"]]
        padre = e.get("padre")
        padre_nombre = inv["por_host"][padre]["nombre"] if padre else "—"
        params = {
            "host": e["host"],
            "name": e["nombre"],
            "status": 0 if estado["monitoreado"] else 1,
            "groups": [{"groupid": groups[SITIO_GRUPO]}, {"groupid": groups[rol["grupo"]]}],
            "templates": _templateids(api, e["perfiles"]),
            "tags": [{"tag": "sitio", "value": sitio}, {"tag": "rol", "value": rol["etiqueta"]},
                     {"tag": "estado", "value": estado["texto"]},
                     {"tag": "entorno", "value": inv.get("entorno", "")},
                     {"tag": "funcion", "value": e["funcion"]},
                     {"tag": "elemento", "value": e["elemento"]}],
            "description": (f"{rol['etiqueta']} de la Red Las Lagunitas. Estado del tramo: "
                            f"{estado['texto']}. Depende de: {padre_nombre}. Gestionado por el "
                            "provisionador (config/inventory.*.yaml): los cambios manuales se pisan."),
            "inventory_mode": 0,
            "inventory": {"type": rol["etiqueta"], "type_full": e["funcion"],
                          "hardware": e.get("equipo", "")[:255], "model": e.get("modelo", "")[:64],
                          "location": sitio, "site_city": "Alpa Corral, Córdoba",
                          "notes": f"Sitio: {inv['por_host'][e['elemento']]['nombre']}. "
                                   f"Depende de: {padre_nombre}"},
        }
        macros = _macros(e, log)
        if macros is not None:
            params["macros"] = macros

        found = api.call("host.get", {"filter": {"host": [e["host"]]}, "output": ["hostid"],
                                      "selectInterfaces": ["interfaceid", "type", "ip", "main"],
                                      "selectParentTemplates": ["templateid"]})
        if found:
            h = found[0]
            hid = h["hostid"]
            # Templates que ya no corresponden: se desvinculan limpiando sus items.
            actuales = {t["templateid"] for t in h["parentTemplates"]}
            deseados = {t["templateid"] for t in params["templates"]}
            quitar = [{"templateid": t} for t in actuales - deseados]
            if quitar:
                params["templates_clear"] = quitar
            # La interfaz debe existir antes de vincular templates que la requieren (SNMP).
            iface = _interfaz(e)
            main = next((i for i in h["interfaces"] if i["main"] == "1" and int(i["type"]) == iface["type"]), None)
            if main and main["ip"] != iface["ip"]:
                api.call("hostinterface.update", {"interfaceid": main["interfaceid"], "ip": iface["ip"]})
            elif not main:
                api.call("hostinterface.create", {"hostid": hid, **iface})
            api.call("host.update", {"hostid": hid, **params})
            accion = "actualizado"
        else:
            hid = api.call("host.create", {**params, "interfaces": [_interfaz(e)]})["hostids"][0]
            accion = "creado"
        hostids[e["host"]] = hid
        log(f"  {accion:11} {e['host']:<26} {e['ip']:<15} {estado['texto']}")
    return hostids


def caida_triggerids(api: ZabbixAPI, inv: dict, hostids: dict[str, str]) -> dict[str, str]:
    """Trigger de 'equipo caído' de cada host (heredado del template de disponibilidad)."""
    out = {}
    for e in inv["todos"]:
        tpl = template_de_disponibilidad(e)
        if not tpl:
            continue
        found = api.call("trigger.get", {"hostids": [hostids[e["host"]]], "output": ["triggerid"],
                                         "filter": {"description": [TRIGGER_CAIDA[tpl]]}})
        if found:
            out[e["host"]] = found[0]["triggerid"]
    return out


def ensure_dependencies(api: ZabbixAPI, inv: dict, triggers: dict[str, str], log=print) -> int:
    """El trigger de caída de cada hijo depende del trigger de caída de su padre.

    Así, si cae una torre, Zabbix alerta solo por la torre y suprime las alertas de
    todos los nodos y hogares que cuelgan de ella (evita tormentas de alarmas).
    """
    n = 0
    for e in inv["todos"]:
        hijo, padre = triggers.get(e["host"]), triggers.get(e.get("padre") or "")
        if not hijo:
            continue
        deps = [{"triggerid": padre}] if padre else []
        api.call("trigger.update", {"triggerid": hijo, "dependencies": deps})
        n += bool(deps)
    log(f"  {n} dependencias padre -> hijo configuradas")
    n += _dependencias_snmp(api, inv, triggers, log)
    return n


# Triggers que se disparan cuando el equipo deja de responder: dependen de la caída
# (ICMP) del propio equipo para no duplicar la alerta.
TRIGGERS_CON_CAIDA = ["{HOST.NAME}: sin datos SNMP", "{HOST.NAME}: sin datos de la API de UniFi",
                      "{HOST.NAME}: controlador UniFi no accesible"]


def _dependencias_snmp(api: ZabbixAPI, inv: dict, triggers: dict[str, str], log) -> int:
    hosts = {h["host"]: h["hostid"] for h in api.call("host.get", {
        "filter": {"host": [e["host"] for e in inv["todos"]]}, "output": ["host"]})}
    n = 0
    for e in inv["todos"]:
        caida = triggers.get(e["host"])
        if not caida or e["host"] not in hosts:
            continue
        for t in api.call("trigger.get", {"hostids": [hosts[e["host"]]], "output": ["triggerid", "description"],
                                          "filter": {"description": TRIGGERS_CON_CAIDA},
                                          "selectDependencies": ["triggerid"]}):
            if t["triggerid"] == caida:
                continue
            actuales = {d["triggerid"] for d in t["dependencies"]}
            if caida not in actuales:
                api.call("trigger.update", {"triggerid": t["triggerid"], "dependencies":
                                            [{"triggerid": x} for x in actuales | {caida}]})
                n += 1
    if n:
        log(f"  {n} alertas de SNMP/API dependientes de la caída del propio equipo")
    return n


def ensure_zabbix_server_host(api: ZabbixAPI, log=print) -> None:
    """Auto-monitoreo del servidor: host 'Zabbix server' vía el contenedor zabbix-agent."""
    found = api.call("host.get", {"filter": {"host": ["Zabbix server"]}, "output": ["hostid"],
                                  "selectInterfaces": ["interfaceid", "type", "main"]})
    if not found:
        return
    h = found[0]
    agent = next((i for i in h["interfaces"] if i["type"] == "1" and i["main"] == "1"), None)
    if agent:
        api.call("hostinterface.update", {"interfaceid": agent["interfaceid"], "useip": 0,
                                          "dns": "zabbix-agent", "ip": "", "port": "10050"})
    api.call("host.update", {"hostid": h["hostid"], "status": 0})
    log("  'Zabbix server' habilitado (agente: zabbix-agent:10050)")
