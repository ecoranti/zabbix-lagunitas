#!/usr/bin/env python3
"""
Crea triggers de alerta en Zabbix:
  - "Nodo caido: <host>" para cada uno de los 9 nodos simulados (icmpping=0 en las
    ultimas 2 mediciones consecutivas).
  - "AP caido (ping)" para el AP real, mismo criterio.
  - "AP - CPU alta" y "AP - Memoria alta" para el AP real (umbral > 85%).

Usa las mismas credenciales / URL que ya vienen usando los scripts anteriores
(create_ap_monitoring.py, create_ping_items.py, etc.) - copialas de ahi si hace
falta ajustar algo.
"""
import requests

# --- Ajustar si hace falta (mismos valores que en los scripts anteriores) ---
ZABBIX_URL = "http://localhost:8090/api_jsonrpc.php"
ZABBIX_USER = "Admin"
ZABBIX_PASSWORD = "zabbix"
# -----------------------------------------------------------------------

HEADERS = {"Content-Type": "application/json-rpc"}


SIMULATED_HOSTS = [
    "Union_de_los_Rios", "Rodeo_del_Padre", "Ex_Aserradero", "El_Carrizal", "Escuela_Rural",
    "Nodo_Kika", "Nodo_CheoMaricel", "Nodo_AlePatricio", "Nodo_Franco", "Mesada",
    "Nodo_JuanCarlos", "Cerro_Blanco", "Nodo_MartinDonJulio",
    "Kika", "CheoMaricel", "AlePatricio", "Franco", "Esther", "JuanCarlos",
    "FabianLucianaLasGuindas", "Walter", "Gladys", "EulaliaDomingo", "Martin", "DonJulio",
]
AP_HOST = "AP-U7-Pro-Wall"  # nombre TECNICO del host (no el visible name)

SEVERITY = {
    "not_classified": 0,
    "information": 1,
    "warning": 2,
    "average": 3,
    "high": 4,
    "disaster": 5,
}


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

    # Trigger de "nodo caido" para cada simulado
    for host in SIMULATED_HOSTS:
        params = {
            "description": f"Nodo caido: {host}",
            "expression": f"min(/{host}/icmpping,#2)=0",
            "priority": SEVERITY["high"],
            "manual_close": "1",
        }
        try:
            call("trigger.create", params, auth=token)
            print(f"Trigger creado: Nodo caido: {host}")
        except RuntimeError as e:
            print(f"[SKIP] {host}: {e}")

    # Triggers del AP
    ap_triggers = [
        {
            "description": "AP caido (ping)",
            "expression": f"min(/{AP_HOST}/icmpping,#2)=0",
            "priority": SEVERITY["high"],
        },
        {
            "description": "AP - CPU alta",
            "expression": f"last(/{AP_HOST}/ap.cpu.util)>85",
            "priority": SEVERITY["warning"],
        },
        {
            "description": "AP - Memoria alta",
            "expression": f"last(/{AP_HOST}/ap.mem.util)>85",
            "priority": SEVERITY["warning"],
        },
    ]
    for t in ap_triggers:
        t["manual_close"] = "1"
        try:
            call("trigger.create", t, auth=token)
            print(f"Trigger creado: {t['description']}")
        except RuntimeError as e:
            print(f"[SKIP] {t['description']}: {e}")

    print("Listo.")


if __name__ == "__main__":
    main()
