#!/usr/bin/env python3
import requests, json

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

# 1) Borrar los 5 hosts duplicados/huerfanos (nombre tecnico con espacios,
#    sin contenedor real detras, generaban alertas fantasma).
DUP_IDS = ["10683", "10684", "10685", "10686", "10687"]
call("host.delete", DUP_IDS, token)
print(f"Hosts duplicados eliminados: {DUP_IDS}")

# 2) Cerrar los 4 eventos residuales de hosts ya borrados (Escuela, Casa-1,
#    Casa-2, Nodo-B) para que no queden colgados en Problems.
OLD_EVENT_IDS = ["2815", "2814", "2813", "2812"]
call("event.acknowledge", {
    "eventids": OLD_EVENT_IDS,
    "action": 1,  # close problem
}, token)
print(f"Eventos residuales cerrados: {OLD_EVENT_IDS}")

print("Listo.")
