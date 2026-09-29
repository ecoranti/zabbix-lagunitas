"""Templates propios del proyecto, definidos como código e instalados vía API.

- "Lagunitas - Disponibilidad ICMP": disponibilidad, pérdida y latencia por
  ping (checks simples del propio Zabbix server, sin agente en el equipo).
  Sirve para cualquier equipo con IP: torres, nodos, AirCube de hogares.
- "Lagunitas - AP UniFi por API": métricas de un AP UniFi a través de la API
  REST de UniFi Network (HTTP agent + items dependientes).

Cada template trae su dashboard de detalle, que Zabbix muestra por equipo en
Monitoring -> Hosts -> Dashboards (o desde el mapa / navegador de equipos).
"""
from __future__ import annotations

from . import widgets as W
from .model import SEVERIDAD, TEMPLATE_GRUPO, TPL_ICMP, TPL_UNIFI, TRIGGER_CAIDA
from .zbx import ZabbixAPI

# ----------------------------------------------------------------- utilidades


def ensure_template_group(api: ZabbixAPI, name: str) -> str:
    found = api.call("templategroup.get", {"filter": {"name": [name]}, "output": ["groupid"]})
    if found:
        return found[0]["groupid"]
    return api.call("templategroup.create", {"name": name})["groupids"][0]


def ensure_template(api: ZabbixAPI, name: str, groupid: str, description: str,
                    macros: list[dict], tags: list[dict]) -> str:
    found = api.call("template.get", {"filter": {"host": [name]}, "output": ["templateid"]})
    params = {"host": name, "name": name, "description": description,
              "groups": [{"groupid": groupid}], "macros": macros, "tags": tags}
    if found:
        tid = found[0]["templateid"]
        api.call("template.update", {"templateid": tid, **params})
        return tid
    return api.call("template.create", params)["templateids"][0]


def ensure_valuemap(api: ZabbixAPI, hostid: str, name: str, mappings: dict) -> str:
    maps = [{"type": "0", "value": str(k), "newvalue": v} for k, v in mappings.items()]
    found = api.call("valuemap.get", {"hostids": [hostid], "filter": {"name": [name]},
                                      "output": ["valuemapid"]})
    if found:
        vid = found[0]["valuemapid"]
        api.call("valuemap.update", {"valuemapid": vid, "mappings": maps})
        return vid
    return api.call("valuemap.create", {"hostid": hostid, "name": name, "mappings": maps})["valuemapids"][0]


def ensure_item(api: ZabbixAPI, hostid: str, spec: dict) -> str:
    found = api.call("item.get", {"hostids": [hostid], "filter": {"key_": spec["key_"]},
                                  "output": ["itemid"]})
    if found:
        iid = found[0]["itemid"]
        upd = {k: v for k, v in spec.items() if k not in ("hostid",)}
        api.call("item.update", {"itemid": iid, **upd})
        return iid
    return api.call("item.create", {"hostid": hostid, **spec})["itemids"][0]


def ensure_trigger(api: ZabbixAPI, hostid: str, spec: dict) -> str:
    found = api.call("trigger.get", {"hostids": [hostid], "filter": {"description": [spec["description"]]},
                                     "output": ["triggerid"]})
    if found:
        tid = found[0]["triggerid"]
        api.call("trigger.update", {"triggerid": tid, **spec})
        return tid
    return api.call("trigger.create", spec)["triggerids"][0]


def ensure_lld(api: ZabbixAPI, hostid: str, spec: dict) -> str:
    found = api.call("discoveryrule.get", {"hostids": [hostid], "filter": {"key_": spec["key_"]},
                                           "output": ["itemid"]})
    if found:
        rid = found[0]["itemid"]
        api.call("discoveryrule.update", {"itemid": rid, **spec})
        return rid
    return api.call("discoveryrule.create", {"hostid": hostid, **spec})["itemids"][0]


def ensure_item_prototype(api: ZabbixAPI, hostid: str, ruleid: str, spec: dict) -> str:
    found = api.call("itemprototype.get", {"discoveryids": [ruleid], "filter": {"key_": spec["key_"]},
                                           "output": ["itemid"]})
    if found:
        iid = found[0]["itemid"]
        api.call("itemprototype.update", {"itemid": iid, **spec})
        return iid
    return api.call("itemprototype.create", {"hostid": hostid, "ruleid": ruleid, **spec})["itemids"][0]


def ensure_trigger_prototype(api: ZabbixAPI, hostid: str, spec: dict) -> str:
    found = api.call("triggerprototype.get", {"hostids": [hostid], "filter": {"description": [spec["description"]]},
                                              "output": ["triggerid"]})
    if found:
        tid = found[0]["triggerid"]
        api.call("triggerprototype.update", {"triggerid": tid, **spec})
        return tid
    return api.call("triggerprototype.create", spec)["triggerids"][0]


def ensure_template_dashboard(api: ZabbixAPI, templateid: str, name: str, pages: list[dict]) -> str:
    found = api.call("templatedashboard.get", {"templateids": [templateid], "filter": {"name": [name]},
                                               "output": ["dashboardid"]})
    if found:
        did = found[0]["dashboardid"]
        api.call("templatedashboard.update", {"dashboardid": did, "pages": pages})
        return did
    return api.call("templatedashboard.create", {"templateid": templateid, "name": name,
                                                 "display_period": 30, "auto_start": 1,
                                                 "pages": pages})["dashboardids"][0]


def _tags(**kv) -> list[dict]:
    return [{"tag": k, "value": v} for k, v in kv.items()]


def _dep_item(key, name, master, jsonpath=None, value_type=0, units="", valuemapid=None,
              js=None, discard_on_error=False, history="90d", trends="365d", tags=None):
    pre = []
    if jsonpath:
        pre.append({"type": 12, "params": jsonpath,
                    "error_handler": 1 if discard_on_error else 0, "error_handler_params": ""})
    if js:
        pre.append({"type": 21, "params": js, "error_handler": 0, "error_handler_params": ""})
    spec = {"name": name, "key_": key, "type": 18, "master_itemid": master, "value_type": value_type,
            "units": units, "delay": "0", "history": history, "preprocessing": pre,
            "tags": tags or []}
    if value_type in (0, 3):
        spec["trends"] = trends
    if valuemapid:
        spec["valuemapid"] = valuemapid
    return spec


# ------------------------------------------------------ template ICMP genérico


def install_icmp(api: ZabbixAPI, groupid: str) -> dict:
    tid = ensure_template(
        api, TPL_ICMP, groupid,
        "Disponibilidad, pérdida de paquetes y latencia por ICMP (fping del Zabbix server). "
        "No requiere agente en el equipo: sirve para torres, nodos y routers AirCube de hogares.",
        macros=[
            {"macro": "{$ICMP.PERDIDA.WARN}", "value": "20",
             "description": "Pérdida de paquetes (%) sostenida 5 min que dispara advertencia"},
            {"macro": "{$ICMP.LATENCIA.WARN}", "value": "0.15",
             "description": "Latencia promedio (s) en 5 min que dispara advertencia (150 ms)"},
            {"macro": "{$ICMP.CAIDA.PERIODO}", "value": "90s",
             "description": "Tiempo sin respuesta al ping (chequeo cada 30 s) para declarar el equipo caído"},
        ],
        tags=_tags(clase="red", objetivo="disponibilidad"),
    )
    vm = ensure_valuemap(api, tid, "Lagunitas - Estado", {0: "Caído", 1: "Activo"})
    tag_disp = _tags(componente="disponibilidad")
    ping = ensure_item(api, tid, {
        "name": "Disponibilidad (ICMP)", "key_": "icmpping", "type": 3, "value_type": 3,
        "delay": "30s", "history": "90d", "trends": "365d", "valuemapid": vm, "tags": tag_disp,
        "description": "1 si el equipo responde al ping, 0 si no responde."})
    loss = ensure_item(api, tid, {
        "name": "Pérdida de paquetes (ICMP)", "key_": "icmppingloss", "type": 3, "value_type": 0,
        "units": "%", "delay": "1m", "history": "90d", "trends": "365d", "tags": tag_disp})
    rtt = ensure_item(api, tid, {
        "name": "Latencia (ICMP)", "key_": "icmppingsec", "type": 3, "value_type": 0,
        "units": "s", "delay": "1m", "history": "90d", "trends": "365d", "tags": tag_disp})
    sla24 = ensure_item(api, tid, {
        "name": "Disponibilidad últimas 24 h", "key_": "lagunitas.disponibilidad[24h]", "type": 15,
        "value_type": 0, "units": "%", "delay": "5m", "history": "90d", "trends": "365d",
        "params": "avg(//icmpping,24h)*100", "tags": tag_disp})
    sla7d = ensure_item(api, tid, {
        "name": "Disponibilidad últimos 7 días", "key_": "lagunitas.disponibilidad[7d]", "type": 15,
        "value_type": 0, "units": "%", "delay": "15m", "history": "90d", "trends": "365d",
        "params": "avg(//icmpping,7d)*100", "tags": tag_disp})

    t = TPL_ICMP
    caida = ensure_trigger(api, tid, {
        "description": TRIGGER_CAIDA[TPL_ICMP],
        "expression": f"max(/{t}/icmpping,{{$ICMP.CAIDA.PERIODO}})=0",
        "priority": SEVERIDAD["high"], "manual_close": 0,
        "tags": _tags(alcance="disponibilidad", equipo="{HOST.HOST}"),
        "comments": "El equipo no respondió al ping durante {$ICMP.CAIDA.PERIODO} "
                    "(chequeo cada 30 s). Revisar alimentación (panel solar/batería), el enlace hacia su "
                    "equipo padre y el propio equipo. Si el padre también está caído, esta "
                    "alerta queda suprimida por dependencia."})
    ensure_trigger(api, tid, {
        "description": "{HOST.NAME}: pérdida de paquetes alta",
        "expression": f"min(/{t}/icmppingloss,5m)>{{$ICMP.PERDIDA.WARN}} and min(/{t}/icmppingloss,5m)<100",
        "priority": SEVERIDAD["warning"], "opdata": "Pérdida: {ITEM.LASTVALUE1}",
        "tags": _tags(alcance="calidad", equipo="{HOST.HOST}"),
        "dependencies": [{"triggerid": caida}],
        "comments": "Pérdida sostenida por encima de {$ICMP.PERDIDA.WARN}% durante 5 minutos: "
                    "posible interferencia, desalineación de antena o saturación del enlace."})
    ensure_trigger(api, tid, {
        "description": "{HOST.NAME}: latencia alta",
        "expression": f"avg(/{t}/icmppingsec,5m)>{{$ICMP.LATENCIA.WARN}}",
        "priority": SEVERIDAD["warning"], "opdata": "Latencia: {ITEM.LASTVALUE1}",
        "tags": _tags(alcance="calidad", equipo="{HOST.HOST}"),
        "dependencies": [{"triggerid": caida}],
        "comments": "Latencia promedio de 5 minutos por encima de {$ICMP.LATENCIA.WARN} s."})

    verde, amarillo, rojo = "43A047", "FFC107", "E53935"
    pages = [{"name": "Estado", "widgets": [
        W.item_value("Estado actual", ping, (0, 0, 18, 4), value_size=40,
                     thresholds=[(0, rojo), (1, verde)]),
        W.item_value("Disponibilidad 24 h", sla24, (18, 0, 18, 4), decimals=2,
                     thresholds=[(0, rojo), (95, amarillo), (99, verde)]),
        W.item_value("Disponibilidad 7 días", sla7d, (36, 0, 18, 4), decimals=2,
                     thresholds=[(0, rojo), (95, amarillo), (99, verde)]),
        W.item_value("Latencia actual", rtt, (54, 0, 18, 4), decimals=1,
                     thresholds=[(0, verde), (0.1, amarillo), (0.15, rojo)]),
        W.svggraph("Latencia (ICMP)", (0, 4, 36, 6), [{"itemids": [rtt], "color": "1E88E5"}], lefty_min=0),
        W.svggraph("Pérdida de paquetes (ICMP)", (36, 4, 36, 6),
                   [{"itemids": [loss], "color": "E53935", "stairs": True}], lefty_min=0),
        W.svggraph("Disponibilidad (1 = activo, 0 = caído)", (0, 10, 72, 5),
                   [{"itemids": [ping], "color": "43A047", "stairs": True, "fill": 4}], lefty_min=0),
    ]}]
    ensure_template_dashboard(api, tid, "Detalle del equipo", pages)
    return {"templateid": tid, "items": {"ping": ping, "loss": loss, "rtt": rtt, "sla24": sla24}}


# ---------------------------------------------------------- template AP UniFi


def install_unifi(api: ZabbixAPI, groupid: str) -> dict:
    tid = ensure_template(
        api, TPL_UNIFI, groupid,
        "Access point UniFi monitoreado por la API de integración de UniFi Network "
        "(UniFi OS). Requiere una API key (Integrations -> Create API Key) en la macro "
        "secreta {$UNIFI.API.KEY} del host.",
        macros=[
            {"macro": "{$UNIFI.HOST}", "value": "", "description": "IP/DNS del controlador UniFi"},
            {"macro": "{$UNIFI.PORT}", "value": "443", "description": "Puerto HTTPS del controlador"},
            {"macro": "{$UNIFI.API.PATH}", "value": "/proxy/network/integration/v1",
             "description": "Ruta base de la API de integración"},
            {"macro": "{$UNIFI.SITE.ID}", "value": "", "description": "ID del site (GET /sites)"},
            {"macro": "{$UNIFI.DEVICE.ID}", "value": "", "description": "ID del AP (GET /sites/{id}/devices)"},
            {"macro": "{$UNIFI.API.KEY}", "value": "definir-en-el-host", "type": 1,
             "description": "API key (macro secreta, se define a nivel host)"},
            {"macro": "{$AP.CPU.WARN}", "value": "85", "description": "CPU (%) sostenida 5 min"},
            {"macro": "{$AP.MEM.WARN}", "value": "85", "description": "Memoria (%) sostenida 5 min"},
            {"macro": "{$AP.REINTENTOS.WARN}", "value": "20", "description": "Reintentos TX (%) promedio 15 min"},
            {"macro": "{$AP.SIN.DATOS}", "value": "5m", "description": "Tiempo sin datos de la API"},
        ],
        tags=_tags(clase="red", objetivo="wifi", fabricante="ubiquiti"),
    )
    vm_estado = ensure_valuemap(api, tid, "Lagunitas - Estado AP", {0: "Fuera de línea", 1: "En línea"})
    vm_srv = ensure_valuemap(api, tid, "Lagunitas - Servicio", {0: "Caído", 1: "Activo"})

    base = "https://{$UNIFI.HOST}:{$UNIFI.PORT}{$UNIFI.API.PATH}/sites/{$UNIFI.SITE.ID}"
    http_common = {"type": 19, "value_type": 4, "request_method": 0, "verify_peer": 0,
                   "verify_host": 0, "timeout": "10s", "history": "1d",
                   "headers": [{"name": "X-API-KEY", "value": "{$UNIFI.API.KEY}"},
                               {"name": "Accept", "value": "application/json"}],
                   "tags": _tags(componente="api")}

    ctrl = ensure_item(api, tid, {
        "name": "Controlador UniFi: HTTPS accesible", "type": 3, "value_type": 3,
        "key_": "net.tcp.service[https,{$UNIFI.HOST},{$UNIFI.PORT}]", "delay": "1m",
        "history": "90d", "trends": "365d", "valuemapid": vm_srv, "tags": _tags(componente="api")})
    stats = ensure_item(api, tid, {**http_common, "name": "AP: estadísticas (JSON crudo)",
                                   "key_": "ap.stats.raw", "delay": "1m",
                                   "url": f"{base}/devices/{{$UNIFI.DEVICE.ID}}/statistics/latest"})
    device = ensure_item(api, tid, {**http_common, "name": "AP: dispositivo (JSON crudo)",
                                    "key_": "ap.device.raw", "delay": "2m",
                                    "url": f"{base}/devices/{{$UNIFI.DEVICE.ID}}"})
    clients = ensure_item(api, tid, {**http_common, "name": "AP: clientes del sitio (JSON crudo)",
                                     "key_": "ap.clients.raw", "delay": "1m",
                                     "url": f"{base}/clients?limit=200"})

    tg = {"rend": _tags(componente="rendimiento"), "radio": _tags(componente="radio"),
          "sist": _tags(componente="sistema"), "disp": _tags(componente="disponibilidad")}
    ids = {}
    for key, name, path, units, tags in [
        ("ap.uptime", "AP: uptime", "$.uptimeSec", "uptime", tg["sist"]),
        ("ap.cpu.util", "AP: uso de CPU", "$.cpuUtilizationPct", "%", tg["rend"]),
        ("ap.mem.util", "AP: uso de memoria", "$.memoryUtilizationPct", "%", tg["rend"]),
        ("ap.load1", "AP: load average (1 min)", "$.loadAverage1Min", "", tg["rend"]),
        ("ap.uplink.tx", "AP: uplink TX", "$.uplink.txRateBps", "bps", tg["rend"]),
        ("ap.uplink.rx", "AP: uplink RX", "$.uplink.rxRateBps", "bps", tg["rend"]),
        ("ap.radio.24ghz.retries", "AP: reintentos TX radio 2.4 GHz", "$.interfaces.radios[0].txRetriesPct", "%", tg["radio"]),
        ("ap.radio.5ghz.retries", "AP: reintentos TX radio 5 GHz", "$.interfaces.radios[1].txRetriesPct", "%", tg["radio"]),
        ("ap.radio.6ghz.retries", "AP: reintentos TX radio 6 GHz", "$.interfaces.radios[2].txRetriesPct", "%", tg["radio"]),
    ]:
        # Los radios/uplink pueden faltar según el modelo: se descarta el valor sin
        # marcar el item como no soportado.
        opcional = key.startswith(("ap.radio", "ap.uplink"))
        ids[key] = ensure_item(api, tid, _dep_item(key, name, stats, jsonpath=path, units=units,
                                                   discard_on_error=opcional, tags=tags))
    ids["ap.clients.count"] = ensure_item(api, tid, _dep_item(
        "ap.clients.count", "AP: clientes conectados", clients, value_type=3, units="",
        jsonpath='$.data[?(@.uplinkDeviceId=="{$UNIFI.DEVICE.ID}")].length()', tags=tg["rend"]))
    ids["ap.estado"] = ensure_item(api, tid, _dep_item(
        "ap.estado", "AP: estado informado por UniFi", device, jsonpath="$.state", value_type=1,
        history="30d", tags=tg["disp"]))
    ids["ap.disponible"] = ensure_item(api, tid, _dep_item(
        "ap.disponible", "Disponibilidad (UniFi)", device, value_type=3, valuemapid=vm_estado,
        js="return JSON.parse(value).state === 'ONLINE' ? 1 : 0;", tags=tg["disp"]))
    ids["ap.firmware"] = ensure_item(api, tid, _dep_item(
        "ap.firmware", "AP: versión de firmware", device, jsonpath="$.firmwareVersion", value_type=1,
        discard_on_error=True, history="365d", tags=tg["sist"]))
    ids["ap.modelo"] = ensure_item(api, tid, _dep_item(
        "ap.modelo", "AP: modelo", device, jsonpath="$.model", value_type=1,
        discard_on_error=True, history="365d", tags=tg["sist"]))

    t = TPL_UNIFI
    ctrl_trig = ensure_trigger(api, tid, {
        "description": "{HOST.NAME}: controlador UniFi no accesible",
        "expression": f"max(/{t}/net.tcp.service[https,{{$UNIFI.HOST}},{{$UNIFI.PORT}}],#3)=0",
        "priority": SEVERIDAD["average"], "tags": _tags(alcance="api", equipo="{HOST.HOST}"),
        "comments": "No se puede abrir conexión HTTPS con el controlador UniFi: sin él no hay "
                    "métricas del AP. Verificar que UniFi OS Server esté encendido y el puerto."})
    nodata = ensure_trigger(api, tid, {
        "description": "{HOST.NAME}: sin datos de la API de UniFi",
        "expression": f"nodata(/{t}/ap.stats.raw,{{$AP.SIN.DATOS}})=1",
        "priority": SEVERIDAD["average"], "tags": _tags(alcance="api", equipo="{HOST.HOST}"),
        "dependencies": [{"triggerid": ctrl_trig}],
        "comments": "La API responde pero no entrega estadísticas: revisar API key, site/device ID."})
    caida = ensure_trigger(api, tid, {
        "description": TRIGGER_CAIDA[TPL_UNIFI],
        "expression": f"last(/{t}/ap.disponible)=0",
        "priority": SEVERIDAD["high"], "opdata": "Estado: {ITEM.LASTVALUE1}",
        "tags": _tags(alcance="disponibilidad", equipo="{HOST.HOST}"),
        "dependencies": [{"triggerid": nodata}],
        "comments": "El controlador informa el AP en un estado distinto de ONLINE."})
    for key, label in [("ap.cpu.util", "CPU"), ("ap.mem.util", "memoria")]:
        macro = "{$AP.CPU.WARN}" if key == "ap.cpu.util" else "{$AP.MEM.WARN}"
        ensure_trigger(api, tid, {
            "description": f"{{HOST.NAME}}: uso de {label} alto",
            "expression": f"min(/{t}/{key},5m)>{macro}",
            "priority": SEVERIDAD["warning"], "opdata": f"{label.capitalize()}: {{ITEM.LASTVALUE1}}",
            "tags": _tags(alcance="rendimiento", equipo="{HOST.HOST}"),
            "dependencies": [{"triggerid": caida}]})
    for key, banda in [("ap.radio.24ghz.retries", "2.4 GHz"), ("ap.radio.5ghz.retries", "5 GHz"),
                       ("ap.radio.6ghz.retries", "6 GHz")]:
        ensure_trigger(api, tid, {
            "description": f"{{HOST.NAME}}: reintentos altos en {banda}",
            "expression": f"avg(/{t}/{key},15m)>{{$AP.REINTENTOS.WARN}}",
            "priority": SEVERIDAD["warning"], "opdata": "Reintentos: {ITEM.LASTVALUE1}",
            "tags": _tags(alcance="radio", equipo="{HOST.HOST}"),
            "dependencies": [{"triggerid": caida}],
            "comments": f"Reintentos de transmisión sostenidos en {banda}: interferencia, "
                        "canal saturado o clientes con mala señal."})
    ensure_trigger(api, tid, {
        "description": "{HOST.NAME}: el AP se reinició",
        "expression": f"last(/{t}/ap.uptime)<600",
        "priority": SEVERIDAD["info"], "manual_close": 1,
        "tags": _tags(alcance="sistema", equipo="{HOST.HOST}"),
        "comments": "Uptime menor a 10 minutos: reinicio por corte de energía o actualización."})
    ensure_trigger(api, tid, {
        "description": "{HOST.NAME}: cambió la versión de firmware",
        "expression": f"last(/{t}/ap.firmware,#1)<>last(/{t}/ap.firmware,#2)",
        "priority": SEVERIDAD["info"], "manual_close": 1,
        "tags": _tags(alcance="sistema", equipo="{HOST.HOST}")})

    verde, amarillo, naranja, rojo = "43A047", "FFC107", "FB8C00", "E53935"
    pct = [(0, verde), (60, amarillo), (85, rojo)]
    pages = [
        {"name": "Resumen", "widgets": [
            W.item_value("Estado", ids["ap.disponible"], (0, 0, 18, 4), value_size=35,
                         thresholds=[(0, rojo), (1, verde)]),
            W.item_value("Uptime", ids["ap.uptime"], (18, 0, 18, 4)),
            W.item_value("Firmware", ids["ap.firmware"], (36, 0, 18, 4), show=(1, 2)),
            W.item_value("Controlador UniFi", ctrl, (54, 0, 18, 4),
                         thresholds=[(0, rojo), (1, verde)]),
            W.gauge("CPU", ids["ap.cpu.util"], (0, 4, 24, 5), 0, 100, pct, decimals=1),
            W.gauge("Memoria", ids["ap.mem.util"], (24, 4, 24, 5), 0, 100, pct, decimals=1),
            W.gauge("Clientes conectados", ids["ap.clients.count"], (48, 4, 24, 5), 0, 60,
                    [(0, verde), (30, amarillo), (50, naranja)], decimals=0),
            W.svggraph("Tráfico del uplink", (0, 9, 36, 6), [
                {"itemids": [ids["ap.uplink.rx"]], "color": "1E88E5", "label": "RX"},
                {"itemids": [ids["ap.uplink.tx"]], "color": "E53935", "label": "TX"}], lefty_min=0),
            W.svggraph("Clientes conectados", (36, 9, 36, 6),
                       [{"itemids": [ids["ap.clients.count"]], "color": "00897B", "stairs": True}],
                       lefty_min=0),
        ]},
        {"name": "Radio y sistema", "widgets": [
            W.svggraph("Reintentos TX por banda", (0, 0, 72, 6), [
                {"itemids": [ids["ap.radio.24ghz.retries"]], "color": "8E24AA", "label": "2.4 GHz"},
                {"itemids": [ids["ap.radio.5ghz.retries"]], "color": "43A047", "label": "5 GHz"},
                {"itemids": [ids["ap.radio.6ghz.retries"]], "color": "FB8C00", "label": "6 GHz"}],
                lefty_min=0),
            W.svggraph("CPU y memoria", (0, 6, 36, 6), [
                {"itemids": [ids["ap.cpu.util"]], "color": "E53935", "label": "CPU"},
                {"itemids": [ids["ap.mem.util"]], "color": "1E88E5", "label": "Memoria"}], lefty_min=0),
            W.svggraph("Load average", (36, 6, 36, 6),
                       [{"itemids": [ids["ap.load1"]], "color": "546E7A"}], lefty_min=0),
        ]},
    ]
    ensure_template_dashboard(api, tid, "Detalle del AP UniFi", pages)
    return {"templateid": tid, "items": ids}


def install_all(api: ZabbixAPI) -> dict:
    from . import templates_snmp
    gid = ensure_template_group(api, TEMPLATE_GRUPO)
    return {TPL_ICMP: install_icmp(api, gid), TPL_UNIFI: install_unifi(api, gid),
            **templates_snmp.install_all(api, gid)}
