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

# Desabilitar el host "Zabbix server"
hosts = call("host.get", {"filter": {"host": ["Zabbix server"]}}, token)
if hosts:
    host_id = hosts[0]["hostid"]
    call("host.update", {"hostid": host_id, "status": 1}, token)
    print("✅ Host 'Zabbix server' deshabilitado")
