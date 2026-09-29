#!/usr/bin/env python3
"""
Crea los 25 hosts de la topologia real (5 torres, 8 nodos, 12 hogares), con
una interfaz tipo Agent apuntando a su IP en 10.50.0.0/24. La interfaz solo
se usa como target del chequeo ICMP (icmpping) de create_ping_items.py; no
hace falta agente Zabbix corriendo en el contenedor.
"""
import requests

ZABBIX_URL = "http://localhost:8090/api_jsonrpc.php"
ZABBIX_USER = "Admin"
ZABBIX_PASSWORD = "zabbix"
HEADERS = {"Content-Type": "application/json-rpc"}

GROUP_NAME = "Red Las Lagunitas - Simulados"

# (nombre_tecnico, IP, operativo)
ELEMENTOS = [
    ("Union_de_los_Rios", "10.50.0.11", True),
    ("Rodeo_del_Padre",   "10.50.0.12", True),
    ("Ex_Aserradero",     "10.50.0.13", True),
    ("El_Carrizal",       "10.50.0.14", True),
    ("Escuela_Rural",     "10.50.0.15", True),
    ("Nodo_Kika",         "10.50.0.21", True),
    ("Nodo_CheoMaricel",  "10.50.0.22", True),
    ("Nodo_AlePatricio",  "10.50.0.23", True),
    ("Nodo_Franco",       "10.50.0.24", False),
    ("Mesada",            "10.50.0.25", True),
    ("Nodo_JuanCarlos",   "10.50.0.26", False),
    ("Cerro_Blanco",      "10.50.0.27", False),
    ("Nodo_MartinDonJulio","10.50.0.28", False),
    ("Kika",              "10.50.0.31", True),
    ("CheoMaricel",       "10.50.0.32", True),
    ("AlePatricio",       "10.50.0.33", True),
    ("Franco",            "10.50.0.34", False),
    ("Esther",            "10.50.0.35", True),
    ("JuanCarlos",        "10.50.0.36", False),
    ("FabianLucianaLasGuindas", "10.50.0.37", False),
    ("Walter",            "10.50.0.38", False),
    ("Gladys",            "10.50.0.39", False),
    ("EulaliaDomingo",    "10.50.0.40", False),
    ("Martin",            "10.50.0.41", False),
    ("DonJulio",          "10.50.0.42", False),
]

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
    print("Login OK")

    existing_group = call("hostgroup.get", {"filter": {"name": [GROUP_NAME]}}, token)
    if existing_group:
        group_id = existing_group[0]["groupid"]
    else:
        group_id = call("hostgroup.create", {"name": GROUP_NAME}, token)["groupids"][0]
        print(f"Grupo creado: {GROUP_NAME} (id {group_id})")

    for nombre, ip, operativo in ELEMENTOS:
        existing = call("host.get", {"filter": {"host": [nombre]}}, token)
        if existing:
            print(f"Host ya existe, salteado: {nombre}")
            continue
        call("host.create", {
            "host": nombre,
            "name": nombre.replace("_", " "),
            "groups": [{"groupid": group_id}],
            "interfaces": [{
                "type": 1, "main": 1, "useip": 1,
                "ip": ip, "dns": "", "port": "10050",
            }],
            "status": 0,
        }, token)
        estado = "operativo" if operativo else "en proceso / sin configurar"
        print(f"Host creado: {nombre} ({ip}) - {estado}")

    print("Listo.")

if __name__ == "__main__":
    main()
