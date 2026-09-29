#!/usr/bin/env python3
"""
Elimina items de ICMP ping de hosts deshabilitados para reducir carga del servidor.
"""
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

# Login
token = call("user.login", {"username": ZABBIX_USER, "password": ZABBIX_PASSWORD})

# Obtener todos los hosts deshabilitados (status = 1)
disabled_hosts = call("host.get", {
    "filter": {"status": [1]},
    "selectItems": ["itemid", "key_"],
}, token)

total_deleted = 0

for host in disabled_hosts:
    host_name = host["host"]
    items = host.get("items", [])

    # Contar items de ICMP en este host
    icmp_items = [item for item in items if item["key_"].startswith("icmp")]

    if icmp_items:
        print(f"Host deshabilitado {host_name}: {len(icmp_items)} items ICMP")

        # Eliminar cada item ICMP
        for item in icmp_items:
            call("item.delete", [item["itemid"]], token)
            total_deleted += 1

print(f"\n✅ Items ICMP eliminados: {total_deleted}")
print("Carga del servidor Zabbix reducida.")
