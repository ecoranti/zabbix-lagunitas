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
    items = call("item.get", {"hostids": hosts[0]["hostid"], "filter": {"key_": key}}, token)
    return items[0]["itemid"]

def ensure_graph(name, gitems):
    existing = call("graph.get", {"filter": {"name": [name]}}, token)
    if existing:
        print(f"Grafico ya existe: {name}")
        return
    call("graph.create", {"name": name, "width": 900, "height": 250, "gitems": gitems}, token)
    print(f"Grafico creado: {name}")

HOST = "AP-U7-Pro-Wall"

ensure_graph("AP UniFi - Uplink RX-TX", [
    {"itemid": item_id(HOST, "ap.uplink.rx"), "color": "1E88E5", "sortorder": 0},
    {"itemid": item_id(HOST, "ap.uplink.tx"), "color": "E53935", "sortorder": 1},
])

ensure_graph("AP UniFi - Retries por radio", [
    {"itemid": item_id(HOST, "ap.radio.24ghz.retries"), "color": "8E24AA", "sortorder": 0},
    {"itemid": item_id(HOST, "ap.radio.5ghz.retries"),  "color": "43A047", "sortorder": 1},
    {"itemid": item_id(HOST, "ap.radio.6ghz.retries"),  "color": "FB8C00", "sortorder": 2},
])

ensure_graph("AP UniFi - Load average", [
    {"itemid": item_id(HOST, "ap.load1"), "color": "546E7A", "sortorder": 0},
])

print("Listo.")
