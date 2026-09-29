#!/usr/bin/env python3
"""Elimina los 9 hosts simulados genericos, reemplazados por los 25 elementos
reales de la Red Las Lagunitas (torres, nodos, hogares)."""
import requests

ZABBIX_URL = "http://localhost:8090/api_jsonrpc.php"
ZABBIX_USER = "Admin"
ZABBIX_PASSWORD = "zabbix"
HEADERS = {"Content-Type": "application/json-rpc"}

OLD_HOSTS = ["Torre-1", "Torre-2", "Torre-3", "Torre-4",
             "Nodo-A", "Nodo-B", "Casa-1", "Casa-2", "Escuela"]

def call(method, params, auth=None):
    payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    headers = dict(HEADERS)
    if auth:
        headers["Authorization"] = f"Bearer {auth}"
    r = requests.post(ZABBIX_URL, json=payload, headers=headers)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"{method} -> {data['error']}")
    return data["result"]

def main():
    token = call("user.login", {"username": ZABBIX_USER, "password": ZABBIX_PASSWORD})
    ids = []
    for nombre in OLD_HOSTS:
        found = call("host.get", {"filter": {"host": [nombre]}}, token)
        if found:
            ids.append(found[0]["hostid"])
        else:
            print(f"No existe (ya borrado?): {nombre}")
    if ids:
        call("host.delete", ids, token)
        print(f"Eliminados {len(ids)} hosts (items y triggers asociados se borran en cascada).")
    else:
        print("Nada para borrar.")

if __name__ == "__main__":
    main()
