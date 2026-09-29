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

def item_id(host, key):
    hosts = call("host.get", {"filter": {"host": [host]}}, token)
    if not hosts:
        raise RuntimeError(f"Host no encontrado: {host}")
    items = call("item.get", {"hostids": hosts[0]["hostid"], "filter": {"key_": key}}, token)
    if not items:
        raise RuntimeError(f"Item no encontrado: {host} / {key}")
    return items[0]["itemid"]

def ensure_graph(name, gitems):
    existing = call("graph.get", {"filter": {"name": [name]}}, token)
    if existing:
        print(f"Grafico ya existe: {name}")
        return
    call("graph.create", {
        "name": name,
        "width": 900,
        "height": 250,
        "gitems": gitems,
    }, token)
    print(f"Grafico creado: {name}")

# Grafico 1: CPU y memoria del AP real
ensure_graph("AP - CPU y Memoria", [
    {"itemid": item_id("AP-U7-Pro-Wall", "ap.cpu.util"), "color": "E53935", "sortorder": 0},
    {"itemid": item_id("AP-U7-Pro-Wall", "ap.mem.util"), "color": "1E88E5", "sortorder": 1},
])

# Grafico 2: latencia de ping de los 9 nodos simulados
nodos = ["Torre-1", "Torre-2", "Torre-3", "Torre-4", "Nodo-A", "Nodo-B", "Casa-1", "Casa-2", "Escuela"]
palette = ["E53935","1E88E5","43A047","FB8C00","8E24AA","00ACC1","FDD835","6D4C41","546E7A"]
gitems = [
    {"itemid": item_id(n, "icmppingsec"), "color": c, "sortorder": i}
    for i, (n, c) in enumerate(zip(nodos, palette))
]
ensure_graph("Nodos simulados - Latencia (ping)", gitems)

print("Listo.")
