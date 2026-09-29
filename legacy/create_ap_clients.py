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

hosts = call("host.get", {"filter": {"host": ["AP-U7-Pro-Wall"]}}, token)
host_id = hosts[0]["hostid"]

CLIENTS_URL = (
    f"https://{UNIFI_HOST}:{UNIFI_PORT}/proxy/network/integration/v1/"
    f"sites/{SITE_ID}/clients"
)

master_key = "ap.clients.raw"
existing_master = call("item.get", {"hostids": host_id, "filter": {"key_": master_key}}, token)
if existing_master:
    master_id = existing_master[0]["itemid"]
    print("Item maestro ya existe")
else:
    master_id = call("item.create", {
        "hostid": host_id,
        "name": "AP - Clientes conectados (raw JSON)",
        "key_": master_key,
        "type": 19,           # HTTP agent
        "value_type": 4,      # Text
        "url": CLIENTS_URL,
        "request_method": 0,  # GET
        "headers": [
            {"name": "X-API-KEY", "value": UNIFI_API_KEY},
            {"name": "Accept", "value": "application/json"},
        ],
        "verify_peer": 0,
        "verify_host": 0,
        "timeout": "5s",
        "delay": "60s",
        "history": "7d",
        "trends": "0",
    }, token)["itemids"][0]
    print("Item maestro creado")

count_key = "ap.clients.count"
existing_count = call("item.get", {"hostids": host_id, "filter": {"key_": count_key}}, token)
if existing_count:
    print("Item de conteo ya existe")
else:
    call("item.create", {
        "hostid": host_id,
        "name": "AP - Clientes conectados",
        "key_": count_key,
        "type": 18,            # Dependent item
        "master_itemid": master_id,
        "value_type": 3,       # Numeric unsigned
        "units": "clientes",
        "delay": "0",
        "history": "7d",
        "trends": "90d",
        "preprocessing": [{
            "type": 12,         # JSONPath
            "params": f'$.data[?(@.uplinkDeviceId=="{DEVICE_ID}")].length()',
            "error_handler": 0,
            "error_handler_params": "",
        }],
    }, token)
    print("Item de conteo creado")

print("Listo.")
