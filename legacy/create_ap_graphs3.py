#!/usr/bin/env python3
import requests

ZABBIX_API_URL = "http://localhost:8090/api_jsonrpc.php"
ZABBIX_USER = "Admin"
ZABBIX_PASS = "zabbix"

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
items = call("item.get", {"hostids": hosts[0]["hostid"], "filter": {"key_": "ap.clients.count"}}, token)
itemid = items[0]["itemid"]

name = "AP UniFi - Clientes conectados"
existing = call("graph.get", {"filter": {"name": [name]}}, token)
if existing:
    print("Grafico ya existe")
else:
    call("graph.create", {
        "name": name, "width": 900, "height": 250,
        "gitems": [{"itemid": itemid, "color": "00897B", "sortorder": 0}],
    }, token)
    print("Grafico creado")
