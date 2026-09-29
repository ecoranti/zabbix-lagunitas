"""Servicios de negocio y SLA: disponibilidad medida por equipo, rol y red completa.

Cada equipo operativo es un servicio cuyo estado lo determinan los problemas con
tags  equipo=<host>  y  alcance=disponibilidad  (solo caídas, no advertencias de
latencia). El SLA mensual se calcula sobre todos los servicios con tag sla=red,
y se consulta en Services -> SLA report o en la página "SLA" del dashboard.
"""
from __future__ import annotations

import calendar
import datetime as dt

from .model import ESTADOS, ROLES, SERVICIO_RAIZ, SLA_NOMBRE
from .zbx import ZabbixAPI

TAG_SLA = {"tag": "sla", "value": "red"}
ALG_MAS_CRITICO_DE_HIJOS = 2  # el servicio toma el peor estado de sus hijos


def _ensure_service(api: ZabbixAPI, name: str, params: dict) -> str:
    found = api.call("service.get", {"filter": {"name": [name]}, "output": ["serviceid"]})
    if found:
        sid = found[0]["serviceid"]
        api.call("service.update", {"serviceid": sid, **params})
        return sid
    return api.call("service.create", {"name": name, **params})["serviceids"][0]


def ensure_services(api: ZabbixAPI, inv: dict, log=print) -> str:
    sitio = inv.get("sitio", "Las Lagunitas")
    raiz = _ensure_service(api, SERVICIO_RAIZ, {
        "algorithm": ALG_MAS_CRITICO_DE_HIJOS, "sortorder": 0,
        "description": "Disponibilidad global de la red comunitaria.",
        "tags": [{"tag": "sitio", "value": sitio}, TAG_SLA]})

    por_rol: dict[str, str] = {}
    creados = set()
    for orden, e in enumerate(inv["elementos"]):
        if not ESTADOS[e["estado"]]["monitoreado"]:
            continue
        rol = ROLES[e["rol"]]
        if rol["servicio"] not in por_rol:
            por_rol[rol["servicio"]] = _ensure_service(api, rol["servicio"], {
                "algorithm": ALG_MAS_CRITICO_DE_HIJOS, "sortorder": len(por_rol),
                "parents": [{"serviceid": raiz}],
                "tags": [{"tag": "sitio", "value": sitio}, TAG_SLA]})
        nombre = f"{rol['etiqueta']}: {e['nombre']}"
        _ensure_service(api, nombre, {
            "algorithm": ALG_MAS_CRITICO_DE_HIJOS, "sortorder": orden,
            "parents": [{"serviceid": por_rol[rol["servicio"]]}],
            "problem_tags": [{"tag": "equipo", "operator": 0, "value": e["host"]},
                             {"tag": "alcance", "operator": 0, "value": "disponibilidad"}],
            "tags": [{"tag": "sitio", "value": sitio}, {"tag": "equipo", "value": e["host"]}, TAG_SLA]})
        creados.add(nombre)

    # Servicios de equipos que dejaron de estar operativos o se quitaron del inventario.
    hijos = api.call("service.get", {"parentids": list(por_rol.values()) or ["0"],
                                     "output": ["serviceid", "name"]})
    sobrantes = [s["serviceid"] for s in hijos if s["name"] not in creados]
    if sobrantes:
        api.call("service.delete", sobrantes)
    log(f"  servicios: 1 raíz, {len(por_rol)} por rol, {len(creados)} equipos"
        + (f" ({len(sobrantes)} eliminados)" if sobrantes else ""))
    return raiz


def ensure_sla(api: ZabbixAPI, timezone: str, slo: str = "99.5", log=print) -> str:
    hoy = dt.date.today()
    inicio_mes = dt.datetime(hoy.year, hoy.month, 1, tzinfo=dt.timezone.utc)
    params = {
        "period": 2,  # mensual
        "slo": slo, "timezone": timezone,
        "effective_date": calendar.timegm(inicio_mes.timetuple()),
        "status": 1,
        "service_tags": [{"tag": TAG_SLA["tag"], "operator": 0, "value": TAG_SLA["value"]}],
        "description": "Objetivo de disponibilidad mensual de cada equipo operativo de la red "
                       "(solo cuentan caídas: problemas con tag alcance=disponibilidad).",
    }
    found = api.call("sla.get", {"filter": {"name": [SLA_NOMBRE]}, "output": ["slaid"]})
    if found:
        sid = found[0]["slaid"]
        params.pop("effective_date")  # conservar la fecha de inicio original
        api.call("sla.update", {"slaid": sid, **params})
    else:
        sid = api.call("sla.create", {"name": SLA_NOMBRE, **params})["slaids"][0]
    log(f"  SLA '{SLA_NOMBRE}' (SLO {slo} %)")
    return sid
