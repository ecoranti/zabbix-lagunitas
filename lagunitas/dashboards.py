"""Dashboard principal "Centro de monitoreo" (NOC) de la red.

Páginas:
  0. Equipos           widget propio: tarjetas, filtros y tablas por rol con detalle por equipo.
  1. Estado de la red   honeycomb de equipos, alertas activas y mapa de topología.
  2. Detalle por equipo navegador de equipos: al seleccionar uno, el resto de los
                        widgets de la página muestra sus datos (comunicación entre
                        widgets de Zabbix 7.0).
  3. AP UniFi           métricas del access point real del laboratorio (si existe).
  4. SLA                cumplimiento mensual por equipo y ranking de disponibilidad.
"""
from __future__ import annotations

from . import widgets as W
from .model import DASHBOARD_NOMBRE, ROLES, SITIO_GRUPO, TPL_ICMP, TPL_UNIFI
from .zbx import ZabbixAPI

VERDE, AMARILLO, NARANJA, ROJO = "43A047", "FFC107", "FB8C00", "E53935"
NAV = "NAVEQ"  # referencia del navegador de equipos (página 2)


def _items_de(api: ZabbixAPI, hostid: str) -> dict[str, str]:
    return {i["key_"]: i["itemid"] for i in
            api.call("item.get", {"hostids": [hostid], "output": ["itemid", "key_"]})}


def _host_muestra(api: ZabbixAPI, inv: dict, hostids: dict[str, str], template: str) -> str | None:
    """Primer host operativo con el template dado (sus items sirven de "molde" para
    los widgets que luego se redirigen al equipo elegido en el navegador)."""
    perfil = "icmp" if template == TPL_ICMP else "unifi_api"
    for e in inv["elementos"]:
        if e["estado"] == "operativo" and perfil in e["perfiles"]:
            return hostids[e["host"]]
    return None


def build_pages(api: ZabbixAPI, inv: dict, hostids: dict[str, str], groups: dict[str, str],
                sysmapid: str, slaid: str, serviceid: str) -> list[dict]:
    g = [groups[SITIO_GRUPO]]
    pages = []

    # ------------------------------------------------------------- 0. Equipos
    pages.append({"name": "Equipos", "widgets": [
        W.lagunitas_red("Red Las Lagunitas — Equipos", (0, 0, 72, 30), g),
    ]})

    # ------------------------------------------------------- 1. Estado de la red
    pages.append({"name": "Estado de la red", "widgets": [
        W.honeycomb("Equipos monitoreados", (0, 0, 26, 8), g,
                    ["Disponibilidad (ICMP)", "Disponibilidad (UniFi)"], "PANAL",
                    thresholds=[(0, ROJO), (1, VERDE)]),
        W.problems_by_severity("Problemas por severidad", (0, 8, 26, 3), g),
        W.mapa("Topología", sysmapid, (26, 0, 46, 15), reference="MAPAT"),
        W.problems("Alertas activas", (0, 15, 72, 7), g,
                   show_lines=15, reference="ALERT"),
    ]})

    # ----------------------------------------------------- 2. Detalle por equipo
    muestra = _host_muestra(api, inv, hostids, TPL_ICMP)
    red = [groups[r["grupo"]] for k, r in ROLES.items() if k != "ap"]
    red = list(dict.fromkeys(red))
    if muestra:
        it = _items_de(api, muestra)
        pages.append({"name": "Detalle por equipo", "widgets": [
            # Solo torres, nodos y hogares: el AP del laboratorio tiene su propia página.
            W.host_navigator("Equipos (elegí uno)", (0, 0, 16, 18), red, NAV, group_by_tag="rol"),
            W.item_value("Estado actual", it["icmpping"], (16, 0, 14, 4), override=NAV, value_size=35,
                         thresholds=[(0, ROJO), (1, VERDE)]),
            W.item_value("Disponibilidad 24 h", it["lagunitas.disponibilidad[24h]"], (30, 0, 14, 4),
                         override=NAV, decimals=2, thresholds=[(0, ROJO), (95, AMARILLO), (99, VERDE)]),
            W.item_value("Disponibilidad 7 días", it["lagunitas.disponibilidad[7d]"], (44, 0, 14, 4),
                         override=NAV, decimals=2, thresholds=[(0, ROJO), (95, AMARILLO), (99, VERDE)]),
            W.item_value("Latencia actual", it["icmppingsec"], (58, 0, 14, 4), override=NAV, decimals=1,
                         thresholds=[(0, VERDE), (0.1, AMARILLO), (0.15, ROJO)]),
            W.svggraph("Latencia", (16, 4, 28, 5),
                       [{"itemids": [it["icmppingsec"]], "color": "1E88E5"}], override=NAV, lefty_min=0),
            W.svggraph("Pérdida de paquetes", (44, 4, 28, 5),
                       [{"itemids": [it["icmppingloss"]], "color": ROJO, "stairs": True}],
                       override=NAV, lefty_min=0),
            W.svggraph("Disponibilidad (1 = activo)", (16, 9, 56, 4),
                       [{"itemids": [it["icmpping"]], "color": VERDE, "stairs": True, "fill": 4}],
                       override=NAV, lefty_min=0, legend=False),
            W.problems("Problemas del equipo", (16, 13, 56, 5), g, override=NAV, show_lines=10),
        ]})

    # ------------------------------------------------------------- 3. AP UniFi
    ap = _host_muestra(api, inv, hostids, TPL_UNIFI)
    if ap:
        it = _items_de(api, ap)
        pct = [(0, VERDE), (60, AMARILLO), (85, ROJO)]
        pages.append({"name": "AP UniFi", "widgets": [
            W.item_value("Estado (UniFi)", it["ap.disponible"], (0, 0, 18, 4), value_size=35,
                         thresholds=[(0, ROJO), (1, VERDE)]),
            W.item_value("Uptime", it["ap.uptime"], (18, 0, 18, 4)),
            W.item_value("Firmware", it["ap.firmware"], (36, 0, 18, 4), show=(1, 2)),
            W.item_value("Controlador UniFi", it["net.tcp.service[https,{$UNIFI.HOST},{$UNIFI.PORT}]"],
                         (54, 0, 18, 4), thresholds=[(0, ROJO), (1, VERDE)]),
            W.gauge("CPU", it["ap.cpu.util"], (0, 4, 18, 5), 0, 100, pct, decimals=1),
            W.gauge("Memoria", it["ap.mem.util"], (18, 4, 18, 5), 0, 100, pct, decimals=1),
            W.gauge("Clientes conectados", it["ap.clients.count"], (36, 4, 18, 5), 0, 60,
                    [(0, VERDE), (30, AMARILLO), (50, NARANJA)], decimals=0),
            W.gauge("Reintentos 5 GHz", it["ap.radio.5ghz.retries"], (54, 4, 18, 5), 0, 100,
                    [(0, VERDE), (15, AMARILLO), (25, ROJO)], decimals=1),
            W.svggraph("Tráfico del uplink", (0, 9, 36, 6), [
                {"itemids": [it["ap.uplink.rx"]], "color": "1E88E5", "label": "RX"},
                {"itemids": [it["ap.uplink.tx"]], "color": ROJO, "label": "TX"}], lefty_min=0),
            W.svggraph("Reintentos TX por banda", (36, 9, 36, 6), [
                {"itemids": [it["ap.radio.24ghz.retries"]], "color": "8E24AA", "label": "2.4 GHz"},
                {"itemids": [it["ap.radio.5ghz.retries"]], "color": VERDE, "label": "5 GHz"},
                {"itemids": [it["ap.radio.6ghz.retries"]], "color": NARANJA, "label": "6 GHz"}],
                lefty_min=0),
        ]})

    # ------------------------------------------------------------------ 4. SLA
    pages.append({"name": "SLA", "widgets": [
        W.sla_report("Cumplimiento de SLA mensual", (0, 0, 72, 10), slaid, serviceid=None, show_periods=3),
        W.tophosts("Ranking de disponibilidad (7 días)", (0, 10, 72, 9), g, [
            {"name": "Equipo", "data": 2},
            {"name": "Disponibilidad 7 días", "data": 1, "item": "Disponibilidad últimos 7 días",
             "display": 2, "min": 0, "max": 100, "decimals": 3, "base_color": ROJO,
             "thresholds": [(95, AMARILLO), (99.5, VERDE)]},
            {"name": "Disponibilidad 24 h", "data": 1, "item": "Disponibilidad últimas 24 h",
             "display": 1, "decimals": 2, "thresholds": [(0, ROJO), (95, AMARILLO), (99.5, VERDE)]},
            {"name": "Latencia promedio 24 h", "data": 1, "item": "Latencia (ICMP)", "display": 1,
             "aggregate_function": 3, "decimals": 1},
        ], order_column=1, show_lines=30),
    ]})
    return pages


def ensure_dashboard(api: ZabbixAPI, inv: dict, hostids: dict[str, str], groups: dict[str, str],
                     sysmapid: str, slaid: str, serviceid: str, log=print) -> str:
    pages = build_pages(api, inv, hostids, groups, sysmapid, slaid, serviceid)
    params = {"display_period": 60, "auto_start": 0, "private": 0, "pages": pages}
    found = api.call("dashboard.get", {"filter": {"name": [DASHBOARD_NOMBRE]}, "output": ["dashboardid"]})
    if found:
        did = found[0]["dashboardid"]
        api.call("dashboard.update", {"dashboardid": did, **params})
    else:
        did = api.call("dashboard.create", {"name": DASHBOARD_NOMBRE, **params})["dashboardids"][0]
    log(f"  dashboard '{DASHBOARD_NOMBRE}': {len(pages)} páginas (id {did})")
    return did
