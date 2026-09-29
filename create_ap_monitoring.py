#!/usr/bin/env python3
import os
import requests

ZABBIX_API_URL = "http://localhost:8090/api_jsonrpc.php"
ZABBIX_USER = "Admin"
ZABBIX_PASS = "zabbix"

UNIFI_HOST = "192.168.1.52"
UNIFI_PORT = 11443
UNIFI_API_KEY = os.environ["UNIFI_API_KEY"]  # exportar antes de correr: export UNIFI_API_KEY=...
SITE_ID = "88f7af54-98f8-306a-a1c7-c9349722b1f6"
DEVICE_ID = "afd2ff68-17b3-3b64-8473-8eebfbe60d12"

headers = {"Content-Type": "application/json-rpc"}

def call(method, params, auth=None):
    payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    if auth:
        headers["Authorization"] = f"Bearer {auth}"
    r = requests.post(ZABBIX_API_URL, json=payload, headers=headers)
    data = r.json()
    if "error" in data:
        raise RuntimeError(data["error"])
    return data["result"]

token = call("user.login", {"username": ZABBIX_USER, "password": ZABBIX_PASS})

# 1. Grupo para dispositivos reales (separado de los simulados)
group_name = "Dispositivos Reales"
existing_group = call("hostgroup.get", {"filter": {"name": [group_name]}}, token)
if existing_group:
    group_id = existing_group[0]["groupid"]
else:
    group_id = call("hostgroup.create", {"name": group_name}, token)["groupids"][0]
    print(f"Grupo creado: {group_name} (id {group_id})")

# 2. Host, sin interfaz (los items HTTP agent no la necesitan)
host_name = "AP-U7-Pro-Wall"
existing_host = call("host.get", {"filter": {"host": [host_name]}}, token)
if existing_host:
    host_id = existing_host[0]["hostid"]
    print(f"Host ya existe: {host_name} (id {host_id})")
else:
    host_id = call("host.create", {
        "host": host_name,
        "name": "AP U7 Pro Wall (real)",
        "groups": [{"groupid": group_id}],
        "interfaces": [],
    }, token)["hostids"][0]
    print(f"Host creado: {host_name} (id {host_id})")

STATS_URL = (
    f"https://{UNIFI_HOST}:{UNIFI_PORT}/proxy/network/integration/v1/"
    f"sites/{SITE_ID}/devices/{DEVICE_ID}/statistics/latest"
)

# 3. Item maestro: trae el JSON crudo
master_key = "ap.stats.raw"
existing_master = call("item.get", {"hostids": host_id, "filter": {"key_": master_key}}, token)
if existing_master:
    master_id = existing_master[0]["itemid"]
    print(f"Item maestro ya existe (id {master_id})")
else:
    master_id = call("item.create", {
        "hostid": host_id,
        "name": "AP - Estadisticas (raw JSON)",
        "key_": master_key,
        "type": 19,           # HTTP agent
        "value_type": 4,      # Text
        "url": STATS_URL,
        "request_method": 0,  # GET
        "headers": [
            {"name": "X-API-KEY", "value": UNIFI_API_KEY},
            {"name": "Accept", "value": "application/json"}],
        "verify_peer": 0,
        "verify_host": 0,
        "timeout": "5s",
        "delay": "60s",
        "history": "7d",
        "trends": "0",
    }, token)["itemids"][0]
    print(f"Item maestro creado (id {master_id})")

# 4. Items dependientes: separan el JSON en metricas individuales
dependent_items = [
    ("ap.uptime",              "AP - Uptime",              "$.uptimeSec",                         "s"),
    ("ap.cpu.util",            "AP - Uso de CPU",          "$.cpuUtilizationPct",                 "%"),
    ("ap.mem.util",            "AP - Uso de memoria",      "$.memoryUtilizationPct",               "%"),
    ("ap.load1",               "AP - Load average (1min)", "$.loadAverage1Min",                    ""),
    ("ap.uplink.tx",           "AP - Uplink TX",           "$.uplink.txRateBps",                   "bps"),
    ("ap.uplink.rx",           "AP - Uplink RX",           "$.uplink.rxRateBps",                   "bps"),
    ("ap.radio.24ghz.retries", "AP - Retries radio 2.4GHz","$.interfaces.radios[0].txRetriesPct",  "%"),
    ("ap.radio.5ghz.retries",  "AP - Retries radio 5GHz",  "$.interfaces.radios[1].txRetriesPct",  "%"),
    ("ap.radio.6ghz.retries",  "AP - Retries radio 6GHz",  "$.interfaces.radios[2].txRetriesPct",  "%"),
]

for key, name, jsonpath, units in dependent_items:
    existing = call("item.get", {"hostids": host_id, "filter": {"key_": key}}, token)
    if existing:
        print(f"Item ya existe: {key}")
        continue
    call("item.create", {
        "hostid": host_id,
        "name": name,
        "key_": key,
        "type": 18,            # Dependent item
        "master_itemid": master_id,
        "value_type": 0,       # Float
        "units": units,
        "delay": "0",
        "history": "7d",
        "trends": "90d",
        "preprocessing": [{
            "type": 12,         # JSONPath
            "params": jsonpath,
            "error_handler": 0,
            "error_handler_params": "",
        }],
    }, token)
    print(f"Item creado: {key}")

print("Listo. Verificar en Zabbix: host 'AP-U7-Pro-Wall' -> Latest data.")
