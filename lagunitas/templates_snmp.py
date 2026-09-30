"""Templates SNMP para los equipos de campo de la red Las Lagunitas.

- "Lagunitas - Ubiquiti airMAX por SNMP": radios airOS 6/8 (PowerBeam, LiteBeam,
  NanoStation, NanoLoco). Métricas de radio de UBNT-AirMAX-MIB (enterprise 41112):
  señal, ruido, SNR, CCQ, calidad/capacidad airMAX, tasas, frecuencia, ancho de canal,
  distancia, potencia, modo AP/estación, estaciones asociadas (descubrimiento) e
  interfaces (IF-MIB), más CPU, memoria, temperatura, modelo y firmware.
- "Lagunitas - Mikrotik por SNMP": routers RouterOS (RB750/RB950). CPU, memoria,
  temperatura, voltaje de alimentación (clave con energía solar), leases DHCP activos,
  interfaces y estado del enlace PPPoE a Internet.

Ninguno incluye ICMP: la disponibilidad la aporta "Lagunitas - Disponibilidad ICMP"
(perfil icmp), que se vincula junto con estos (perfiles airos_snmp / mikrotik_snmp).
Los OIDs se validaron contra agentes simulados (lab/snmpsim) con las MIB del fabricante.
"""
from __future__ import annotations

from . import widgets as W
from .model import INTERVALO, SEVERIDAD, TPL_AIRMAX, TPL_MIKROTIK
from .templates import (_tags, ensure_item, ensure_item_prototype, ensure_lld, ensure_template,
                        ensure_template_dashboard, ensure_trigger, ensure_trigger_prototype,
                        ensure_valuemap)
from .zbx import ZabbixAPI

SNMP = 20          # tipo de item: SNMP agent
CALC = 15          # calculado
INTERNO = 5        # interno de Zabbix
FLOAT, CHAR, UINT, TEXT = 0, 1, 3, 4
AIROS = "1.3.6.1.4.1.41112.1.4"
MTK = "1.3.6.1.4.1.14988.1.1"

VERDE, AMARILLO, NARANJA, ROJO, AZUL = "43A047", "FFC107", "FB8C00", "E53935", "1E88E5"


def _snmp(name, key, oid, vtype=FLOAT, units="", delay=INTERVALO, history="90d", pre=None, vm=None,
          tags=None, desc=""):
    spec = {"name": name, "key_": key, "type": SNMP, "snmp_oid": f"get[{oid}]", "value_type": vtype,
            "units": units, "delay": delay, "history": history, "tags": tags or [], "description": desc,
            "preprocessing": list(pre or [])}
    if vtype in (FLOAT, UINT):
        spec["trends"] = "365d"
    if vm:
        spec["valuemapid"] = vm
    return spec


def _mult(factor) -> dict:
    return {"type": 1, "params": str(factor), "error_handler": 0, "error_handler_params": ""}


def _por_segundo() -> dict:
    return {"type": 10, "params": "", "error_handler": 0, "error_handler_params": ""}


def _descartar_sin_cambios(heartbeat="1h") -> dict:
    return {"type": 20, "params": heartbeat, "error_handler": 0, "error_handler_params": ""}


# ----------------------------------------------------------- interfaces (IF-MIB)


def _interfaces(api: ZabbixAPI, tid: str, prefijo: str, vm_oper: str, filtro_macro: str,
                tag_equipo: str) -> str:
    """Descubrimiento de interfaces con estado, tráfico (bps), errores y velocidad."""
    rid = ensure_lld(api, tid, {
        "name": "Descubrimiento de interfaces", "key_": f"{prefijo}.if.discovery", "type": SNMP,
        "snmp_oid": "discovery[{#IFNAME},1.3.6.1.2.1.31.1.1.1.1,{#IFTYPE},1.3.6.1.2.1.2.2.1.3,"
                    "{#IFALIAS},1.3.6.1.2.1.31.1.1.1.18]",
        "delay": "1h", "lifetime": "7d",
        "filter": {"evaltype": 0, "conditions": [
            {"macro": "{#IFNAME}", "value": filtro_macro, "operator": 8}]},
        "description": "Interfaces del equipo (IF-MIB). Filtro: " + filtro_macro})
    tags = [{"tag": "componente", "value": "red"}, {"tag": "interfaz", "value": "{#IFNAME}"}]
    ensure_item_prototype(api, tid, rid, {
        "name": "Interfaz {#IFNAME}: estado", "key_": f"{prefijo}.if.estado[{{#IFNAME}}]", "type": SNMP,
        "snmp_oid": "get[1.3.6.1.2.1.2.2.1.8.{#SNMPINDEX}]", "value_type": UINT, "delay": INTERVALO,
        "history": "90d", "trends": "365d", "valuemapid": vm_oper, "tags": tags,
        "preprocessing": [_descartar_sin_cambios()]})
    for sentido, oid in (("entrante", "1.3.6.1.2.1.31.1.1.1.6"), ("saliente", "1.3.6.1.2.1.31.1.1.1.10")):
        ensure_item_prototype(api, tid, rid, {
            "name": f"Interfaz {{#IFNAME}}: tráfico {sentido}",
            "key_": f"{prefijo}.if.{'in' if sentido == 'entrante' else 'out'}[{{#IFNAME}}]", "type": SNMP,
            "snmp_oid": f"get[{oid}.{{#SNMPINDEX}}]", "value_type": UINT, "units": "bps", "delay": INTERVALO,
            "history": "30d", "trends": "365d", "tags": tags,
            "preprocessing": [_por_segundo(), _mult(8)]})
    for sentido, oid in (("entrada", "1.3.6.1.2.1.2.2.1.14"), ("salida", "1.3.6.1.2.1.2.2.1.20")):
        ensure_item_prototype(api, tid, rid, {
            "name": f"Interfaz {{#IFNAME}}: errores de {sentido}",
            "key_": f"{prefijo}.if.err{'in' if sentido == 'entrada' else 'out'}[{{#IFNAME}}]", "type": SNMP,
            "snmp_oid": f"get[{oid}.{{#SNMPINDEX}}]", "value_type": FLOAT, "units": "/s", "delay": INTERVALO,
            "history": "30d", "trends": "365d", "tags": tags, "preprocessing": [_por_segundo()]})
    ensure_item_prototype(api, tid, rid, {
        "name": "Interfaz {#IFNAME}: velocidad", "key_": f"{prefijo}.if.velocidad[{{#IFNAME}}]", "type": SNMP,
        "snmp_oid": "get[1.3.6.1.2.1.31.1.1.1.15.{#SNMPINDEX}]", "value_type": UINT, "units": "bps",
        "delay": "1h", "history": "30d", "trends": "365d", "tags": tags,
        "preprocessing": [_mult(1000000), _descartar_sin_cambios("1d")]})
    ensure_trigger_prototype(api, tid, {
        "description": "{HOST.NAME}: interfaz {#IFNAME} sin enlace",
        "expression": f"last(/{tag_equipo}/{prefijo}.if.estado[{{#IFNAME}}])=2 and "
                      f"last(/{tag_equipo}/{prefijo}.if.estado[{{#IFNAME}}],#2)=1",
        "recovery_mode": 1,
        "recovery_expression": f"last(/{tag_equipo}/{prefijo}.if.estado[{{#IFNAME}}])=1",
        "priority": SEVERIDAD["average"], "manual_close": 1,
        "tags": _tags(alcance="red", equipo="{HOST.HOST}", interfaz="{#IFNAME}"),
        "comments": "La interfaz pasó de 'up' a 'down': cable, conector (humedad) o equipo vecino."})
    ensure_trigger_prototype(api, tid, {
        "description": "{HOST.NAME}: errores en la interfaz {#IFNAME}",
        "expression": f"min(/{tag_equipo}/{prefijo}.if.errin[{{#IFNAME}}],5m)>{{$IF.ERRORES.WARN}}",
        "priority": SEVERIDAD["warning"],
        "tags": _tags(alcance="red", equipo="{HOST.HOST}", interfaz="{#IFNAME}"),
        "comments": "Errores de recepción sostenidos: cable/conector dañado, dúplex o interferencia."})
    return rid


# ------------------------------------------------------------------ airMAX


def install_airmax(api: ZabbixAPI, groupid: str) -> dict:
    t = TPL_AIRMAX
    tid = ensure_template(
        api, t, groupid,
        "Radios Ubiquiti airMAX (airOS 6/8) por SNMP v2c: calidad del enlace inalámbrico "
        "(señal, ruido, SNR, CCQ, airMAX quality/capacity), estaciones asociadas, interfaces y "
        "sistema. Habilitar en airOS: Services -> SNMP Agent (comunidad = {$SNMP_COMMUNITY}). "
        "Usar junto con 'Lagunitas - Disponibilidad ICMP'.",
        macros=[
            {"macro": "{$SNMP_COMMUNITY}", "value": "public", "description": "Comunidad SNMP v2c"},
            {"macro": "{$AIRMAX.SENAL.WARN}", "value": "-75",
             "description": "Señal (dBm) promedio 10 min por debajo de la cual se advierte. Ideal: -50 a -65"},
            {"macro": "{$AIRMAX.SENAL.CRIT}", "value": "-82",
             "description": "Señal (dBm) crítica: enlace al borde de cortarse"},
            {"macro": "{$AIRMAX.RUIDO.WARN}", "value": "-85",
             "description": "Piso de ruido (dBm) por encima del cual hay interferencia. Normal: -90 a -100"},
            {"macro": "{$AIRMAX.SNR.WARN}", "value": "20",
             "description": "Relación señal/ruido (dB) mínima. >25 dB permite modulaciones altas"},
            {"macro": "{$AIRMAX.CCQ.WARN}", "value": "75", "description": "CCQ (%) mínimo aceptable"},
            {"macro": "{$AIRMAX.CALIDAD.WARN}", "value": "60", "description": "airMAX quality (%) mínima"},
            {"macro": "{$AIRMAX.CAPACIDAD.WARN}", "value": "40", "description": "airMAX capacity (%) mínima"},
            {"macro": "{$AIRMAX.CPU.WARN}", "value": "90", "description": "CPU (%) sostenida 5 min"},
            {"macro": "{$AIRMAX.MEMORIA.WARN}", "value": "90", "description": "Memoria (%) sostenida 5 min"},
            {"macro": "{$AIRMAX.TEMP.WARN}", "value": "75", "description": "Temperatura (°C)"},
            {"macro": "{$SNMP.SIN.DATOS}", "value": "5m", "description": "Tiempo sin respuesta SNMP"},
            {"macro": "{$IF.ERRORES.WARN}", "value": "2", "description": "Errores/s en una interfaz"},
            {"macro": "{$AIRMAX.IF.MATCHES}", "value": "^(eth|ath|wlan|br)[0-9]+$",
             "description": "Interfaces a descubrir"},
        ],
        tags=_tags(clase="red", objetivo="radio", fabricante="ubiquiti"),
    )
    vm_modo = ensure_valuemap(api, tid, "airMAX - Modo de radio",
                              {1: "Estación (SM)", 2: "Punto de acceso (AP)", 3: "AP repetidor", 4: "AP WDS"})
    vm_oper = ensure_valuemap(api, tid, "IF-MIB - Estado de interfaz",
                              {1: "up", 2: "down", 3: "testing", 4: "desconocido", 5: "dormant",
                               6: "no presente", 7: "capa inferior caída"})
    vm_snmp = ensure_valuemap(api, tid, "SNMP - Disponibilidad", {0: "Desconocido", 1: "Disponible", 2: "No disponible"})
    vm_sino = ensure_valuemap(api, tid, "Sí/No", {0: "No", 1: "Sí"})

    tg = {k: [{"tag": "componente", "value": v}] for k, v in
          (("sis", "sistema"), ("rad", "radio"), ("air", "airmax"), ("snmp", "snmp"), ("rend", "rendimiento"))}
    I = {}

    def item(spec):
        I[spec["key_"]] = ensure_item(api, tid, spec)
        return I[spec["key_"]]

    # --- sistema
    item(_snmp("Sistema: nombre (sysName)", "airmax.sistema.nombre", "1.3.6.1.2.1.1.5.0", CHAR, delay="1h",
               history="30d", tags=tg["sis"], pre=[_descartar_sin_cambios("1d")]))
    item(_snmp("Sistema: modelo", "airmax.sistema.modelo", "1.2.840.10036.3.1.2.1.3.5", CHAR, delay="1h",
               history="365d", tags=tg["sis"], pre=[_descartar_sin_cambios("1d")]))
    item(_snmp("Sistema: firmware airOS", "airmax.sistema.firmware", "1.2.840.10036.3.1.2.1.4.5", CHAR,
               delay="1h", history="365d", tags=tg["sis"], pre=[_descartar_sin_cambios("1d")]))
    item(_snmp("Sistema: uptime", "airmax.sistema.uptime", "1.3.6.1.2.1.1.3.0", UINT, units="uptime",
               tags=tg["sis"], pre=[_mult(0.01)]))
    item(_snmp("Sistema: uso de CPU", "airmax.cpu", f"{AIROS}.8.3.0", FLOAT, units="%", tags=tg["rend"],
               desc="ubntHostCpuLoad (airOS 8). En airOS 6 puede no estar disponible."))
    item(_snmp("Sistema: temperatura", "airmax.temperatura", f"{AIROS}.8.4.0", FLOAT, units="°C", delay=INTERVALO,
               tags=tg["rend"], desc="ubntHostTemperature (solo algunos modelos)."))
    item(_snmp("Memoria: total", "airmax.memoria.total", "1.3.6.1.4.1.10002.1.1.1.1.1.0", UINT, units="B",
               delay="1h", tags=tg["rend"], pre=[_mult(1024)]))
    item(_snmp("Memoria: libre", "airmax.memoria.libre", "1.3.6.1.4.1.10002.1.1.1.1.2.0", UINT, units="B",
               tags=tg["rend"], pre=[_mult(1024)]))
    item({"name": "Memoria: uso", "key_": "airmax.memoria.uso", "type": CALC, "value_type": FLOAT,
          "units": "%", "delay": INTERVALO, "history": "90d", "trends": "365d", "tags": tg["rend"],
          "params": "100*(1-last(//airmax.memoria.libre)/last(//airmax.memoria.total))"})
    item({"name": "SNMP: disponibilidad del agente", "key_": "zabbix[host,snmp,available]", "type": INTERNO,
          "value_type": UINT, "delay": INTERVALO, "history": "30d", "trends": "365d", "valuemapid": vm_snmp,
          "tags": tg["snmp"]})

    # --- radio (ubntRadioTable)
    item(_snmp("Radio: modo", "airmax.radio.modo", f"{AIROS}.1.1.2.1", UINT, delay=INTERVALO, vm=vm_modo,
               tags=tg["rad"], pre=[_descartar_sin_cambios()]))
    item(_snmp("Radio: frecuencia", "airmax.radio.frecuencia", f"{AIROS}.1.1.4.1", UINT, units="MHz",
               delay=INTERVALO, tags=tg["rad"]))
    item(_snmp("Radio: potencia de transmisión", "airmax.radio.potencia", f"{AIROS}.1.1.6.1", FLOAT,
               units="dBm", delay=INTERVALO, tags=tg["rad"]))
    item(_snmp("Radio: distancia configurada", "airmax.radio.distancia", f"{AIROS}.1.1.7.1", UINT, units="m",
               delay=INTERVALO, tags=tg["rad"]))
    item(_snmp("Radio: antena", "airmax.radio.antena", f"{AIROS}.1.1.9.1", CHAR, delay="1h", history="365d",
               tags=tg["rad"], pre=[_descartar_sin_cambios("1d")]))
    item(_snmp("Radio: DFS habilitado", "airmax.radio.dfs", f"{AIROS}.1.1.5.1", UINT, delay="1h", vm=vm_sino,
               tags=tg["rad"]))

    # --- estado inalámbrico (ubntWlStatTable)
    item(_snmp("Inalámbrico: SSID", "airmax.wl.ssid", f"{AIROS}.5.1.2.1", CHAR, delay="1h", history="365d",
               tags=tg["rad"], pre=[_descartar_sin_cambios("1d")]))
    item(_snmp("Inalámbrico: señal", "airmax.wl.senal", f"{AIROS}.5.1.5.1", FLOAT, units="dBm",
               tags=tg["rad"], desc="Potencia recibida. Excelente > -55, buena -55 a -65, "
                                    "aceptable -65 a -75, pobre < -75 dBm."))
    item(_snmp("Inalámbrico: RSSI", "airmax.wl.rssi", f"{AIROS}.5.1.6.1", FLOAT, tags=tg["rad"]))
    item(_snmp("Inalámbrico: piso de ruido", "airmax.wl.ruido", f"{AIROS}.5.1.8.1", FLOAT, units="dBm",
               tags=tg["rad"], desc="Ruido del canal. Normal: -90 a -100 dBm; más alto indica interferencia."))
    item(_snmp("Inalámbrico: CCQ", "airmax.wl.ccq", f"{AIROS}.5.1.7.1", FLOAT, units="%", tags=tg["rad"],
               desc="Client Connection Quality: % de transmisiones exitosas. >90 % es bueno."))
    item(_snmp("Inalámbrico: tasa TX", "airmax.wl.tx", f"{AIROS}.5.1.9.1", UINT, units="bps", tags=tg["rad"],
               pre=[_mult(1000)], desc="Tasa de modulación de transmisión (no es tráfico real)."))
    item(_snmp("Inalámbrico: tasa RX", "airmax.wl.rx", f"{AIROS}.5.1.10.1", UINT, units="bps",
               tags=tg["rad"], pre=[_mult(1000)]))
    item(_snmp("Inalámbrico: ancho de canal", "airmax.wl.canal", f"{AIROS}.5.1.14.1", UINT, units="MHz",
               delay=INTERVALO, tags=tg["rad"]))
    item(_snmp("Inalámbrico: estaciones asociadas", "airmax.wl.estaciones", f"{AIROS}.5.1.15.1", UINT,
               tags=tg["rad"]))
    item({"name": "Inalámbrico: SNR", "key_": "airmax.wl.snr", "type": CALC, "value_type": FLOAT,
          "units": "dB", "delay": INTERVALO, "history": "90d", "trends": "365d", "tags": tg["rad"],
          "params": "last(//airmax.wl.senal)-last(//airmax.wl.ruido)",
          "description": "Señal menos ruido. >30 dB excelente, 20-30 bueno, <15 dB enlace degradado."})

    # --- airMAX (ubntAirMaxTable)
    item(_snmp("airMAX: calidad", "airmax.airmax.calidad", f"{AIROS}.6.1.3.1", FLOAT, units="%",
               tags=tg["air"], desc="airMAX quality: estabilidad del enlace (TDMA)."))
    item(_snmp("airMAX: capacidad", "airmax.airmax.capacidad", f"{AIROS}.6.1.4.1", FLOAT, units="%",
               tags=tg["air"], desc="airMAX capacity: % de la capacidad teórica disponible."))

    # --- estaciones asociadas (ubntStaTable)
    sta = ensure_lld(api, tid, {
        "name": "Descubrimiento de estaciones asociadas", "key_": "airmax.sta.discovery", "type": SNMP,
        "snmp_oid": f"discovery[{{#STANOMBRE}},{AIROS}.7.1.2,{{#STAIP}},{AIROS}.7.1.10]",
        "delay": "10m", "lifetime": "1d",
        "description": "En un AP: cada cliente (SM) conectado. En una estación: el AP al que se asocia."})
    stags = [{"tag": "componente", "value": "estacion"}, {"tag": "estacion", "value": "{#STANOMBRE}"}]
    for key, nombre, col, units, mult, vtype in (
            ("senal", "señal", 3, "dBm", None, FLOAT), ("ruido", "ruido", 4, "dBm", None, FLOAT),
            ("ccq", "CCQ", 6, "%", None, FLOAT), ("distancia", "distancia", 5, "m", None, UINT),
            ("calidad", "airMAX calidad", 8, "%", None, FLOAT), ("capacidad", "airMAX capacidad", 9, "%", None, FLOAT),
            ("tx", "tasa TX", 11, "bps", 1000, UINT), ("rx", "tasa RX", 12, "bps", 1000, UINT),
            ("latencia", "latencia TX", 21, "ms", None, FLOAT)):
        ensure_item_prototype(api, tid, sta, {
            "name": f"Estación {{#STANOMBRE}}: {nombre}", "key_": f"airmax.sta.{key}[{{#SNMPINDEX}}]",
            "type": SNMP, "snmp_oid": f"get[{AIROS}.7.1.{col}.{{#SNMPINDEX}}]", "value_type": vtype,
            "units": units, "delay": INTERVALO,
            "history": "30d", "trends": "365d", "tags": stags,
            "preprocessing": [_mult(mult)] if mult else []})
    ensure_item_prototype(api, tid, sta, {
        "name": "Estación {#STANOMBRE}: tiempo conectada", "key_": "airmax.sta.conexion[{#SNMPINDEX}]",
        "type": SNMP, "snmp_oid": f"get[{AIROS}.7.1.15.{{#SNMPINDEX}}]", "value_type": UINT, "units": "uptime",
        "delay": INTERVALO, "history": "30d", "trends": "365d", "tags": stags, "preprocessing": [_mult(0.01)]})
    ensure_trigger_prototype(api, tid, {
        "description": "{HOST.NAME}: señal débil de la estación {#STANOMBRE}",
        "expression": f"avg(/{t}/airmax.sta.senal[{{#SNMPINDEX}}],10m)<{{$AIRMAX.SENAL.WARN}}",
        "priority": SEVERIDAD["warning"], "opdata": "Señal: {ITEM.LASTVALUE1}",
        "tags": _tags(alcance="radio", equipo="{HOST.HOST}", estacion="{#STANOMBRE}"),
        "comments": "La estación asociada recibe una señal pobre: revisar alineación, obstáculos "
                    "(vegetación) o potencia."})

    _interfaces(api, tid, "airmax", vm_oper, "{$AIRMAX.IF.MATCHES}", t)

    # --- triggers
    sin_datos = ensure_trigger(api, tid, {
        "description": "{HOST.NAME}: sin datos SNMP",
        "expression": f"nodata(/{t}/airmax.sistema.uptime,{{$SNMP.SIN.DATOS}})=1",
        "priority": SEVERIDAD["average"], "tags": _tags(alcance="snmp", equipo="{HOST.HOST}"),
        "comments": "El equipo no responde SNMP. Si responde al ping: revisar que el agente SNMP "
                    "de airOS esté habilitado, la comunidad y el firewall."})
    crit = ensure_trigger(api, tid, {
        "description": "{HOST.NAME}: señal crítica",
        "expression": f"avg(/{t}/airmax.wl.senal,10m)<{{$AIRMAX.SENAL.CRIT}}",
        "priority": SEVERIDAD["average"], "opdata": "Señal: {ITEM.LASTVALUE1}",
        "tags": _tags(alcance="radio", equipo="{HOST.HOST}"),
        "comments": "Señal promedio de 10 min por debajo de {$AIRMAX.SENAL.CRIT} dBm: el enlace está "
                    "al borde de cortarse. Revisar alineación, línea de vista y obstrucciones."})
    ensure_trigger(api, tid, {
        "description": "{HOST.NAME}: señal débil",
        "expression": f"avg(/{t}/airmax.wl.senal,10m)<{{$AIRMAX.SENAL.WARN}}",
        "priority": SEVERIDAD["warning"], "opdata": "Señal: {ITEM.LASTVALUE1}",
        "dependencies": [{"triggerid": crit}], "tags": _tags(alcance="radio", equipo="{HOST.HOST}")})
    for key, desc, expr, macro, sev, texto in (
            ("airmax.wl.ruido", "ruido alto en el canal", ">", "{$AIRMAX.RUIDO.WARN}", "warning",
             "Interferencia: evaluar cambio de frecuencia o ancho de canal (usar airView)."),
            ("airmax.wl.snr", "SNR bajo", "<", "{$AIRMAX.SNR.WARN}", "warning",
             "La relación señal/ruido limita la modulación: menor velocidad y más reintentos."),
            ("airmax.wl.ccq", "CCQ bajo", "<", "{$AIRMAX.CCQ.WARN}", "warning",
             "Muchas retransmisiones: interferencia, señal marginal o clientes lejanos."),
            ("airmax.airmax.calidad", "calidad airMAX baja", "<", "{$AIRMAX.CALIDAD.WARN}", "warning",
             "Enlace inestable según airMAX."),
            ("airmax.airmax.capacidad", "capacidad airMAX baja", "<", "{$AIRMAX.CAPACIDAD.WARN}", "info",
             "El enlace entrega una fracción baja de su capacidad teórica.")):
        ensure_trigger(api, tid, {
            "description": f"{{HOST.NAME}}: {desc}",
            "expression": f"avg(/{t}/{key},15m){expr}{macro}",
            "priority": SEVERIDAD[sev], "opdata": "Valor: {ITEM.LASTVALUE1}",
            "tags": _tags(alcance="radio", equipo="{HOST.HOST}"), "comments": texto})
    ensure_trigger(api, tid, {
        "description": "{HOST.NAME}: radio AP sin estaciones asociadas",
        "expression": f"max(/{t}/airmax.wl.estaciones,5m)=0 and last(/{t}/airmax.radio.modo)>=2",
        "priority": SEVERIDAD["average"], "tags": _tags(alcance="radio", equipo="{HOST.HOST}"),
        "dependencies": [{"triggerid": sin_datos}],
        "comments": "El AP no tiene clientes conectados: el enlace con la(s) estación(es) remota(s) cayó."})
    for key, label, macro in (("airmax.cpu", "CPU", "{$AIRMAX.CPU.WARN}"),
                              ("airmax.memoria.uso", "memoria", "{$AIRMAX.MEMORIA.WARN}")):
        ensure_trigger(api, tid, {
            "description": f"{{HOST.NAME}}: uso de {label} alto",
            "expression": f"min(/{t}/{key},5m)>{macro}",
            "priority": SEVERIDAD["warning"], "tags": _tags(alcance="rendimiento", equipo="{HOST.HOST}")})
    ensure_trigger(api, tid, {
        "description": "{HOST.NAME}: temperatura alta",
        "expression": f"avg(/{t}/airmax.temperatura,10m)>{{$AIRMAX.TEMP.WARN}}",
        "priority": SEVERIDAD["warning"], "tags": _tags(alcance="rendimiento", equipo="{HOST.HOST}")})
    ensure_trigger(api, tid, {
        "description": "{HOST.NAME}: el equipo se reinició",
        "expression": f"last(/{t}/airmax.sistema.uptime)<600", "priority": SEVERIDAD["info"],
        "manual_close": 1, "tags": _tags(alcance="sistema", equipo="{HOST.HOST}"),
        "comments": "Uptime menor a 10 min: corte de energía (batería/solar) o reinicio."})
    ensure_trigger(api, tid, {
        "description": "{HOST.NAME}: cambió el firmware",
        "expression": f"last(/{t}/airmax.sistema.firmware,#1)<>last(/{t}/airmax.sistema.firmware,#2)",
        "priority": SEVERIDAD["info"], "manual_close": 1, "tags": _tags(alcance="sistema", equipo="{HOST.HOST}")})
    ensure_trigger(api, tid, {
        "description": "{HOST.NAME}: cambió la frecuencia de radio",
        "expression": f"change(/{t}/airmax.radio.frecuencia)<>0", "priority": SEVERIDAD["info"],
        "manual_close": 1, "tags": _tags(alcance="radio", equipo="{HOST.HOST}"),
        "comments": "Cambio de canal (manual o automático por DFS)."})

    # --- dashboard de detalle
    pages = [
        {"name": "Enlace", "widgets": [
            W.gauge("Señal", I["airmax.wl.senal"], (0, 0, 18, 5), -95, -40,
                    [(-95, ROJO), (-80, NARANJA), (-72, AMARILLO), (-65, VERDE)], decimals=0),
            W.gauge("SNR", I["airmax.wl.snr"], (18, 0, 18, 5), 0, 60,
                    [(0, ROJO), (15, AMARILLO), (25, VERDE)], decimals=0),
            W.gauge("CCQ", I["airmax.wl.ccq"], (36, 0, 18, 5), 0, 100,
                    [(0, ROJO), (70, AMARILLO), (85, VERDE)], decimals=0),
            W.gauge("Capacidad airMAX", I["airmax.airmax.capacidad"], (54, 0, 18, 5), 0, 100,
                    [(0, ROJO), (40, AMARILLO), (60, VERDE)], decimals=0),
            W.item_value("Modo", I["airmax.radio.modo"], (0, 5, 12, 3), show=(1, 2)),
            W.item_value("Frecuencia", I["airmax.radio.frecuencia"], (12, 5, 12, 3), show=(1, 2)),
            W.item_value("Ancho de canal", I["airmax.wl.canal"], (24, 5, 12, 3), show=(1, 2)),
            W.item_value("Potencia TX", I["airmax.radio.potencia"], (36, 5, 12, 3), show=(1, 2)),
            W.item_value("Distancia", I["airmax.radio.distancia"], (48, 5, 12, 3), show=(1, 2)),
            W.item_value("Estaciones", I["airmax.wl.estaciones"], (60, 5, 12, 3), show=(1, 2)),
            W.svggraph("Señal y ruido", (0, 8, 36, 6), [
                {"itemids": [I["airmax.wl.senal"]], "color": AZUL, "label": "Señal"},
                {"itemids": [I["airmax.wl.ruido"]], "color": ROJO, "label": "Ruido"}]),
            W.svggraph("CCQ y airMAX", (36, 8, 36, 6), [
                {"itemids": [I["airmax.wl.ccq"]], "color": VERDE, "label": "CCQ"},
                {"itemids": [I["airmax.airmax.calidad"]], "color": AZUL, "label": "Calidad"},
                {"itemids": [I["airmax.airmax.capacidad"]], "color": NARANJA, "label": "Capacidad"}],
                lefty_min=0),
            W.svggraph("Tasas de modulación TX/RX", (0, 14, 36, 6), [
                {"itemids": [I["airmax.wl.tx"]], "color": ROJO, "label": "TX"},
                {"itemids": [I["airmax.wl.rx"]], "color": AZUL, "label": "RX"}], lefty_min=0),
            W.svggraph("Tráfico por interfaz", (36, 14, 36, 6), [
                {"items": ["Interfaz *: tráfico entrante"], "color": AZUL, "label": "Entrante"},
                {"items": ["Interfaz *: tráfico saliente"], "color": ROJO, "label": "Saliente"}],
                lefty_min=0),
        ]},
        {"name": "Estaciones y sistema", "widgets": [
            W.svggraph("Señal por estación", (0, 0, 36, 6),
                       [{"items": ["Estación *: señal"], "color": AZUL}]),
            W.svggraph("CCQ por estación", (36, 0, 36, 6),
                       [{"items": ["Estación *: CCQ"], "color": VERDE}], lefty_min=0),
            W.item_value("Modelo", I["airmax.sistema.modelo"], (0, 6, 18, 3), show=(1, 2)),
            W.item_value("Firmware", I["airmax.sistema.firmware"], (18, 6, 18, 3), show=(1, 2)),
            W.item_value("Uptime", I["airmax.sistema.uptime"], (36, 6, 18, 3), show=(1, 2)),
            W.item_value("SSID", I["airmax.wl.ssid"], (54, 6, 18, 3), show=(1, 2)),
            W.svggraph("CPU y memoria", (0, 9, 36, 6), [
                {"itemids": [I["airmax.cpu"]], "color": ROJO, "label": "CPU"},
                {"itemids": [I["airmax.memoria.uso"]], "color": AZUL, "label": "Memoria"}], lefty_min=0),
            W.svggraph("Temperatura", (36, 9, 36, 6),
                       [{"itemids": [I["airmax.temperatura"]], "color": NARANJA}]),
        ]},
    ]
    ensure_template_dashboard(api, tid, "Detalle de radio airMAX", pages)
    return {"templateid": tid, "items": I}


# ----------------------------------------------------------------- Mikrotik


def install_mikrotik(api: ZabbixAPI, groupid: str) -> dict:
    t = TPL_MIKROTIK
    tid = ensure_template(
        api, t, groupid,
        "Routers Mikrotik (RouterOS) por SNMP v2c: CPU, memoria, temperatura, voltaje de "
        "alimentación, leases DHCP, interfaces y enlace PPPoE a Internet. Habilitar con: "
        "/snmp set enabled=yes ; /snmp community add name=<comunidad> addresses=<IP Zabbix>. "
        "Usar junto con 'Lagunitas - Disponibilidad ICMP'.",
        macros=[
            {"macro": "{$SNMP_COMMUNITY}", "value": "public", "description": "Comunidad SNMP v2c"},
            {"macro": "{$MIKROTIK.CPU.WARN}", "value": "85", "description": "CPU (%) sostenida 5 min"},
            {"macro": "{$MIKROTIK.MEMORIA.WARN}", "value": "90", "description": "Memoria (%) sostenida 5 min"},
            {"macro": "{$MIKROTIK.TEMP.WARN}", "value": "65", "description": "Temperatura de placa (°C)"},
            {"macro": "{$MIKROTIK.VOLTAJE.WARN}", "value": "12.0",
             "description": "Voltaje (V) de advertencia. Batería VRLA 12 V: 12,0 V ≈ 50 % de carga"},
            {"macro": "{$MIKROTIK.VOLTAJE.CRIT}", "value": "11.6",
             "description": "Voltaje (V) crítico: descarga profunda, corte inminente"},
            {"macro": "{$MIKROTIK.VOLTAJE.MAX}", "value": "14.8",
             "description": "Voltaje (V) máximo: sobrecarga del regulador solar"},
            {"macro": "{$MIKROTIK.WAN.IFNAME}", "value": "^pppoe-out[0-9]+$",
             "description": "Interfaz de salida a Internet (PPPoE con la Cooperativa)"},
            {"macro": "{$MIKROTIK.IF.MATCHES}", "value": "^(ether|sfp|wlan|bridge|pppoe|vlan|lte)",
             "description": "Interfaces a descubrir"},
            {"macro": "{$SNMP.SIN.DATOS}", "value": "5m", "description": "Tiempo sin respuesta SNMP"},
            {"macro": "{$IF.ERRORES.WARN}", "value": "2", "description": "Errores/s en una interfaz"},
        ],
        tags=_tags(clase="red", objetivo="router", fabricante="mikrotik"),
    )
    vm_oper = ensure_valuemap(api, tid, "IF-MIB - Estado de interfaz",
                              {1: "up", 2: "down", 3: "testing", 4: "desconocido", 5: "dormant",
                               6: "no presente", 7: "capa inferior caída"})
    vm_snmp = ensure_valuemap(api, tid, "SNMP - Disponibilidad", {0: "Desconocido", 1: "Disponible", 2: "No disponible"})
    tg = {k: [{"tag": "componente", "value": v}] for k, v in
          (("sis", "sistema"), ("rend", "rendimiento"), ("ene", "energia"), ("snmp", "snmp"), ("cli", "clientes"))}
    I = {}

    def item(spec):
        I[spec["key_"]] = ensure_item(api, tid, spec)
        return I[spec["key_"]]

    item(_snmp("Sistema: nombre (sysName)", "mikrotik.sistema.nombre", "1.3.6.1.2.1.1.5.0", CHAR, delay="1h",
               history="30d", tags=tg["sis"], pre=[_descartar_sin_cambios("1d")]))
    item(_snmp("Sistema: modelo", "mikrotik.sistema.modelo", "1.3.6.1.2.1.1.1.0", CHAR, delay="1h",
               history="365d", tags=tg["sis"], pre=[_descartar_sin_cambios("1d")]))
    item(_snmp("Sistema: número de serie", "mikrotik.sistema.serie", f"{MTK}.7.3.0", CHAR, delay="1h",
               history="365d", tags=tg["sis"], pre=[_descartar_sin_cambios("1d")]))
    item(_snmp("Sistema: firmware (RouterBOOT)", "mikrotik.sistema.firmware", f"{MTK}.7.4.0", CHAR,
               delay="1h", history="365d", tags=tg["sis"], pre=[_descartar_sin_cambios("1d")]))
    item(_snmp("Sistema: versión de RouterOS", "mikrotik.sistema.routeros", f"{MTK}.4.4.0", CHAR,
               delay="1h", history="365d", tags=tg["sis"], pre=[_descartar_sin_cambios("1d")]))
    item(_snmp("Sistema: uptime", "mikrotik.sistema.uptime", "1.3.6.1.2.1.1.3.0", UINT, units="uptime",
               tags=tg["sis"], pre=[_mult(0.01)]))
    item({"name": "Sistema: uso de CPU", "key_": "mikrotik.cpu", "type": SNMP,
          "snmp_oid": "walk[1.3.6.1.2.1.25.3.3.1.2]", "value_type": FLOAT, "units": "%", "delay": INTERVALO,
          "history": "90d", "trends": "365d", "tags": tg["rend"],
          "description": "Promedio de hrProcessorLoad de todos los núcleos.",
          "preprocessing": [{"type": 21, "error_handler": 0, "error_handler_params": "", "params":
                             "var v = value.split('\\n').map(function (l) { var m = l.match(/(-?\\d+)\\s*$/); "
                             "return m ? parseInt(m[1], 10) : null; }).filter(function (x) { return x !== null; });\n"
                             "if (!v.length) { throw 'sin datos de CPU'; }\n"
                             "return v.reduce(function (a, b) { return a + b; }, 0) / v.length;"}]})
    item(_snmp("Memoria: total", "mikrotik.memoria.total", "1.3.6.1.2.1.25.2.3.1.5.65536", UINT, units="B",
               delay="1h", tags=tg["rend"], pre=[_mult(1024)]))
    item(_snmp("Memoria: usada", "mikrotik.memoria.usada", "1.3.6.1.2.1.25.2.3.1.6.65536", UINT, units="B",
               tags=tg["rend"], pre=[_mult(1024)]))
    item({"name": "Memoria: uso", "key_": "mikrotik.memoria.uso", "type": CALC, "value_type": FLOAT,
          "units": "%", "delay": INTERVALO, "history": "90d", "trends": "365d", "tags": tg["rend"],
          "params": "100*last(//mikrotik.memoria.usada)/last(//mikrotik.memoria.total)"})
    item(_snmp("Energía: temperatura de placa", "mikrotik.temperatura", f"{MTK}.3.10.0", FLOAT, units="°C",
               delay=INTERVALO, tags=tg["ene"], pre=[_mult(0.1)],
               desc="mtxrHlTemperature (décimas de °C). No todos los modelos tienen sensor."))
    item(_snmp("Energía: temperatura de CPU", "mikrotik.temperatura.cpu", f"{MTK}.3.11.0", FLOAT, units="°C",
               delay=INTERVALO, tags=tg["ene"], pre=[_mult(0.1)]))
    item(_snmp("Energía: voltaje de alimentación", "mikrotik.voltaje", f"{MTK}.3.8.0", FLOAT, units="V",
               delay=INTERVALO, tags=tg["ene"], pre=[_mult(0.1)],
               desc="mtxrHlVoltage. En nodos solares refleja el estado de la batería de 12 V: "
                    "12,7 V ≈ 100 %, 12,2 V ≈ 50 %, <11,8 V descarga profunda."))
    item(_snmp("Clientes: leases DHCP activos", "mikrotik.dhcp.clientes", f"{MTK}.6.1.0", UINT,
               tags=tg["cli"], desc="Dispositivos con IP asignada por el Mikrotik (aprox. usuarios conectados)."))
    item({"name": "SNMP: disponibilidad del agente", "key_": "zabbix[host,snmp,available]", "type": INTERNO,
          "value_type": UINT, "delay": INTERVALO, "history": "30d", "trends": "365d", "valuemapid": vm_snmp,
          "tags": tg["snmp"]})

    _interfaces(api, tid, "mikrotik", vm_oper, "{$MIKROTIK.IF.MATCHES}", t)

    # Enlace a Internet: regla aparte filtrada por la interfaz WAN (PPPoE).
    wan = ensure_lld(api, tid, {
        "name": "Descubrimiento del enlace a Internet (WAN)", "key_": "mikrotik.wan.discovery", "type": SNMP,
        "snmp_oid": "discovery[{#IFNAME},1.3.6.1.2.1.31.1.1.1.1]", "delay": "10m", "lifetime": "30d",
        "filter": {"evaltype": 0, "conditions": [
            {"macro": "{#IFNAME}", "value": "{$MIKROTIK.WAN.IFNAME}", "operator": 8}]}})
    ensure_item_prototype(api, tid, wan, {
        "name": "Internet ({#IFNAME}): estado", "key_": "mikrotik.wan.estado[{#IFNAME}]", "type": SNMP,
        "snmp_oid": "get[1.3.6.1.2.1.2.2.1.8.{#SNMPINDEX}]", "value_type": UINT, "delay": INTERVALO,
        "history": "90d", "trends": "365d", "valuemapid": vm_oper,
        "tags": [{"tag": "componente", "value": "internet"}]})
    ensure_trigger_prototype(api, tid, {
        "description": "{HOST.NAME}: sin enlace a Internet ({#IFNAME})",
        "expression": f"last(/{t}/mikrotik.wan.estado[{{#IFNAME}}])<>1 or "
                      f"nodata(/{t}/mikrotik.wan.estado[{{#IFNAME}}],5m)=1",
        "priority": SEVERIDAD["disaster"],
        "tags": _tags(alcance="internet", equipo="{HOST.HOST}"),
        "comments": "La sesión PPPoE con la Cooperativa de Alpa Corral está caída: toda la red "
                    "comunitaria queda sin Internet (la red interna puede seguir funcionando)."})

    sin_datos = ensure_trigger(api, tid, {
        "description": "{HOST.NAME}: sin datos SNMP",
        "expression": f"nodata(/{t}/mikrotik.sistema.uptime,{{$SNMP.SIN.DATOS}})=1",
        "priority": SEVERIDAD["average"], "tags": _tags(alcance="snmp", equipo="{HOST.HOST}"),
        "comments": "El router no responde SNMP: verificar /snmp (enabled, comunidad, addresses) "
                    "y el firewall (UDP 161 desde la IP del servidor Zabbix)."})
    crit = ensure_trigger(api, tid, {
        "description": "{HOST.NAME}: voltaje crítico",
        "expression": f"avg(/{t}/mikrotik.voltaje,5m)<{{$MIKROTIK.VOLTAJE.CRIT}}",
        "priority": SEVERIDAD["high"], "opdata": "Voltaje: {ITEM.LASTVALUE1}",
        "tags": _tags(alcance="energia", equipo="{HOST.HOST}"),
        "comments": "Batería en descarga profunda: el nodo se apagará. Revisar panel solar, "
                    "regulador de carga y batería."})
    ensure_trigger(api, tid, {
        "description": "{HOST.NAME}: voltaje bajo",
        "expression": f"avg(/{t}/mikrotik.voltaje,10m)<{{$MIKROTIK.VOLTAJE.WARN}}",
        "priority": SEVERIDAD["warning"], "opdata": "Voltaje: {ITEM.LASTVALUE1}",
        "dependencies": [{"triggerid": crit}], "tags": _tags(alcance="energia", equipo="{HOST.HOST}"),
        "comments": "La batería está por debajo del 50 %: días nublados o panel sucio/sombreado."})
    ensure_trigger(api, tid, {
        "description": "{HOST.NAME}: voltaje excesivo",
        "expression": f"avg(/{t}/mikrotik.voltaje,10m)>{{$MIKROTIK.VOLTAJE.MAX}}",
        "priority": SEVERIDAD["average"], "tags": _tags(alcance="energia", equipo="{HOST.HOST}"),
        "comments": "Sobretensión: posible falla del regulador de carga."})
    for key, label, macro in (("mikrotik.cpu", "CPU", "{$MIKROTIK.CPU.WARN}"),
                              ("mikrotik.memoria.uso", "memoria", "{$MIKROTIK.MEMORIA.WARN}")):
        ensure_trigger(api, tid, {
            "description": f"{{HOST.NAME}}: uso de {label} alto",
            "expression": f"min(/{t}/{key},5m)>{macro}",
            "priority": SEVERIDAD["warning"], "tags": _tags(alcance="rendimiento", equipo="{HOST.HOST}")})
    ensure_trigger(api, tid, {
        "description": "{HOST.NAME}: temperatura alta",
        "expression": f"avg(/{t}/mikrotik.temperatura,10m)>{{$MIKROTIK.TEMP.WARN}}",
        "priority": SEVERIDAD["warning"], "tags": _tags(alcance="energia", equipo="{HOST.HOST}")})
    ensure_trigger(api, tid, {
        "description": "{HOST.NAME}: el router se reinició",
        "expression": f"last(/{t}/mikrotik.sistema.uptime)<600", "priority": SEVERIDAD["info"],
        "manual_close": 1, "tags": _tags(alcance="sistema", equipo="{HOST.HOST}")})
    ensure_trigger(api, tid, {
        "description": "{HOST.NAME}: cambió la versión de RouterOS",
        "expression": f"last(/{t}/mikrotik.sistema.routeros,#1)<>last(/{t}/mikrotik.sistema.routeros,#2)",
        "priority": SEVERIDAD["info"], "manual_close": 1, "tags": _tags(alcance="sistema", equipo="{HOST.HOST}")})
    ensure_trigger(api, tid, {
        "description": "{HOST.NAME}: sin clientes DHCP",
        "expression": f"max(/{t}/mikrotik.dhcp.clientes,30m)=0",
        "priority": SEVERIDAD["warning"], "dependencies": [{"triggerid": sin_datos}],
        "tags": _tags(alcance="clientes", equipo="{HOST.HOST}"),
        "comments": "Ningún dispositivo tiene IP asignada en 30 min: posible caída de la red de "
                    "distribución o del servidor DHCP."})

    pages = [
        {"name": "Router", "widgets": [
            W.gauge("Voltaje", I["mikrotik.voltaje"], (0, 0, 18, 5), 10, 15,
                    [(10, ROJO), (11.6, NARANJA), (12.0, AMARILLO), (12.4, VERDE), (14.8, ROJO)], decimals=1),
            W.gauge("CPU", I["mikrotik.cpu"], (18, 0, 18, 5), 0, 100,
                    [(0, VERDE), (60, AMARILLO), (85, ROJO)], decimals=0),
            W.gauge("Memoria", I["mikrotik.memoria.uso"], (36, 0, 18, 5), 0, 100,
                    [(0, VERDE), (70, AMARILLO), (90, ROJO)], decimals=0),
            W.gauge("Temperatura", I["mikrotik.temperatura"], (54, 0, 18, 5), 0, 90,
                    [(0, VERDE), (55, AMARILLO), (65, ROJO)], decimals=0),
            W.item_value("Clientes DHCP", I["mikrotik.dhcp.clientes"], (0, 5, 18, 3), show=(1, 2)),
            W.item_value("RouterOS", I["mikrotik.sistema.routeros"], (18, 5, 18, 3), show=(1, 2)),
            W.item_value("Modelo", I["mikrotik.sistema.modelo"], (36, 5, 18, 3), show=(1, 2)),
            W.item_value("Uptime", I["mikrotik.sistema.uptime"], (54, 5, 18, 3), show=(1, 2)),
            W.svggraph("Voltaje de alimentación (batería)", (0, 8, 36, 6),
                       [{"itemids": [I["mikrotik.voltaje"]], "color": NARANJA}]),
            W.svggraph("Clientes DHCP", (36, 8, 36, 6),
                       [{"itemids": [I["mikrotik.dhcp.clientes"]], "color": VERDE, "stairs": True}], lefty_min=0),
            W.svggraph("Tráfico por interfaz", (0, 14, 72, 7), [
                {"items": ["Interfaz *: tráfico entrante"], "color": AZUL, "label": "Entrante"},
                {"items": ["Interfaz *: tráfico saliente"], "color": ROJO, "label": "Saliente"}], lefty_min=0),
        ]},
    ]
    ensure_template_dashboard(api, tid, "Detalle del router Mikrotik", pages)
    return {"templateid": tid, "items": I}


def install_all(api: ZabbixAPI, groupid: str) -> dict:
    return {TPL_AIRMAX: install_airmax(api, groupid), TPL_MIKROTIK: install_mikrotik(api, groupid)}
