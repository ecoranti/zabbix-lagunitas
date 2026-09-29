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
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"{method} -> {data['error']}")
    return data["result"]

token = call("user.login", {"username": ZABBIX_USER, "password": ZABBIX_PASSWORD})
maps = call("map.get", {
    "output": "extend",
    "selectSelements": "extend",
    "selectLinks": "extend",
}, token)
print(json.dumps(maps, indent=2))
