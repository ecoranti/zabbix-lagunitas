#!/usr/bin/env python3
import requests

ZABBIX_URL = "http://localhost:8090/api_jsonrpc.php"
ZABBIX_USER = "Admin"
ZABBIX_PASSWORD = "zabbix"
HEADERS = {"Content-Type": "application/json-rpc"}

def call(method, params, auth=None):
    payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    headers = dict(HEADERS)
    if auth:
        headers["Authorization"] = f"Bearer {auth}"
    r = requests.post(ZABBIX_URL, json=payload, headers=headers)
    data = r.json()
    if "error" in data:
        raise RuntimeError(data["error"])
    return data["result"]

token = call("user.login", {"username": ZABBIX_USER, "password": ZABBIX_PASSWORD})

OLD_TRIGGER_IDS = ["25235", "25234", "25233", "25232"]  # Escuela, Casa-2, Casa-1, Nodo-B
for tid in OLD_TRIGGER_IDS:
    call("trigger.update", {"triggerid": tid, "manual_close": "1"}, token)
print("manual_close habilitado en los 4 triggers viejos.")

OLD_EVENT_IDS = ["2815", "2814", "2813", "2812"]
call("event.acknowledge", {"eventids": OLD_EVENT_IDS, "action": 1}, token)
print(f"Eventos residuales cerrados: {OLD_EVENT_IDS}")
