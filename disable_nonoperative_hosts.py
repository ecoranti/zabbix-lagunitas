#!/usr/bin/env python3
"""
Deshabilita los hosts que corresponden a ramas no operativas del diagrama.
Según el diagrama, solo operan:
- Torres: Unión_de_los_Ríos, Rodeo_del_Padre, El_Carrizal, Ex_Aserradero
- Nodos: Nodo_Kika, Nodo_CheoMaricel, Nodo_AlePatricio
- Hogares: Kika, CheoMaricel, AlePatricio, Escuela_Rural, Esther
"""
import requests

ZABBIX_URL = "http://localhost:8090/api_jsonrpc.php"
ZABBIX_USER = "Admin"
ZABBIX_PASSWORD = "zabbix"
HEADERS = {"Content-Type": "application/json-rpc"}

# Hosts que NO deben estar operativos (ramas en proceso/sin configurar)
HOSTS_TO_DISABLE = [
    "Franco",
    "JuanCarlos",
    "FabianLucianaLasGuindas",
    "Walter",
    "Gladys",
    "EulaliaDomingo",
    "Martin",
    "DonJulio",
    "Nodo_Franco",
    "Nodo_JuanCarlos",
    "Nodo_MartinDonJulio",
    "Cerro_Blanco",
]

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

# Deshabilitar cada host
for host_name in HOSTS_TO_DISABLE:
    hosts = call("host.get", {
        "filter": {"host": [host_name]},
    }, token)

    if not hosts:
        print(f"⚠️  Host no encontrado: {host_name}")
        continue

    host_id = hosts[0]["hostid"]

    # Deshabilitar (status = 1 means disabled)
    call("host.update", {
        "hostid": host_id,
        "status": 1,  # 0 = monitored, 1 = unmonitored
    }, token)

    print(f"✅ Deshabilitado: {host_name}")

print("\nListo. Hosts no operativos deshabilitados.")
