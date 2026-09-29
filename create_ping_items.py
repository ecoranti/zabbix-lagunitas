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

nodos = [
    "Union_de_los_Rios", "Rodeo_del_Padre", "Ex_Aserradero", "El_Carrizal", "Escuela_Rural",
    "Nodo_Kika", "Nodo_CheoMaricel", "Nodo_AlePatricio", "Nodo_Franco", "Mesada",
    "Nodo_JuanCarlos", "Cerro_Blanco", "Nodo_MartinDonJulio",
    "Kika", "CheoMaricel", "AlePatricio", "Franco", "Esther", "JuanCarlos",
    "FabianLucianaLasGuindas", "Walter", "Gladys", "EulaliaDomingo", "Martin", "DonJulio",
]

for nombre in nodos:
    hosts = call("host.get", {
        "filter": {"host": [nombre]},
        "selectInterfaces": ["interfaceid"],
    }, token)
    if not hosts:
        print(f"Host no encontrado, salteado: {nombre}")
        continue
    host_id = hosts[0]["hostid"]
    interfaces = hosts[0]["interfaces"]
    if not interfaces:
        print(f"Host sin interfaz, salteado: {nombre}")
        continue
    interface_id = interfaces[0]["interfaceid"]

    items = [
        ("icmpping", "Disponibilidad (ping)", 3, ""),        # 0/1, unsigned
        ("icmppingsec", "Tiempo de respuesta (ping)", 0, "s"),  # float
    ]
    for item_key, name, value_type, units in items:
        existing = call("item.get", {"hostids": host_id, "filter": {"key_": item_key}}, token)
        if existing:
            print(f"Item ya existe: {nombre} / {item_key}")
            continue
        call("item.create", {
            "hostid": host_id,
            "interfaceid": interface_id,
            "name": name,
            "key_": item_key,
            "type": 3,            # Simple check
            "value_type": value_type,
            "units": units,
            "delay": "30s",
            "history": "7d",
            "trends": "90d",
        }, token)
        print(f"Item creado: {nombre} / {item_key}")

print("Listo.")
