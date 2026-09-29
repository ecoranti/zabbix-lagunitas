#!/usr/bin/env python3
"""
Reconstruye el mapa 'Topologia Red Las Lagunitas' (mismo sysmapid, mismo
widget del dashboard) con los 25 elementos reales + el AP, y sus 25 enlaces.
"""
import requests

ZABBIX_URL = "http://localhost:8090/api_jsonrpc.php"
ZABBIX_USER = "Admin"
ZABBIX_PASSWORD = "zabbix"
HEADERS = {"Content-Type": "application/json-rpc"}

MAP_NAME = "Topología Red Las Lagunitas"

ICON_TORRE = 145
ICON_NODO = 155
ICON_AP = 39
ICON_HOGAR_NAME = "Workstation_(48)"  # se resuelve por nombre, ver mas abajo

# (nombre_tecnico, tipo, x, y)
ELEMENTOS = [
    ("Union_de_los_Rios", "torre", 150, 340),
    ("Rodeo_del_Padre",   "torre", 380, 340),
    ("Ex_Aserradero",     "torre", 150, 560),
    ("El_Carrizal",       "torre", 420, 560),
    ("Escuela_Rural",     "torre", 780, 260),
    ("Nodo_Kika",         "nodo",  130, 160),
    ("Nodo_CheoMaricel",  "nodo",  320, 160),
    ("Nodo_AlePatricio",  "nodo",  520, 180),
    ("Nodo_Franco",       "nodo",  680, 140),
    ("Mesada",            "nodo",  600, 400),
    ("Nodo_JuanCarlos",   "nodo",  750, 620),
    ("Cerro_Blanco",      "nodo",  180, 760),
    ("Nodo_MartinDonJulio","nodo", 550, 760),
    ("Kika",              "hogar",  80, 60),
    ("CheoMaricel",       "hogar", 320, 60),
    ("AlePatricio",       "hogar", 520, 60),
    ("Franco",            "hogar", 700, 40),
    ("Esther",            "hogar", 900, 180),
    ("JuanCarlos",        "hogar", 950, 560),
    ("FabianLucianaLasGuindas", "hogar", 950, 680),
    ("Walter",            "hogar", 420, 720),
    ("Gladys",            "hogar",  60, 900),
    ("EulaliaDomingo",    "hogar", 260, 900),
    ("Martin",            "hogar", 500, 900),
    ("DonJulio",          "hogar", 700, 900),
    ("AP-U7-Pro-Wall",    "ap",    150, 150),
]

# (elemento1, elemento2, estado)
ENLACES = [
    ("Union_de_los_Rios", "Rodeo_del_Padre", "operativo"),
    ("Union_de_los_Rios", "Ex_Aserradero", "operativo"),
    ("Ex_Aserradero", "El_Carrizal", "operativo"),
    ("Union_de_los_Rios", "Nodo_Kika", "operativo"),
    ("Nodo_Kika", "Kika", "operativo"),
    ("Union_de_los_Rios", "Nodo_CheoMaricel", "operativo"),
    ("Nodo_CheoMaricel", "CheoMaricel", "operativo"),
    ("Rodeo_del_Padre", "Nodo_AlePatricio", "operativo"),
    ("Nodo_AlePatricio", "AlePatricio", "operativo"),
    ("Nodo_AlePatricio", "Nodo_Franco", "en_proceso"),
    ("Nodo_Franco", "Franco", "sin_configurar"),
    ("El_Carrizal", "Mesada", "operativo"),
    ("Mesada", "Escuela_Rural", "operativo"),
    ("Escuela_Rural", "Esther", "operativo"),
    ("El_Carrizal", "Nodo_JuanCarlos", "en_proceso"),
    ("Nodo_JuanCarlos", "JuanCarlos", "sin_configurar"),
    ("Nodo_JuanCarlos", "FabianLucianaLasGuindas", "sin_configurar"),
    ("El_Carrizal", "Walter", "en_proceso"),
    ("Ex_Aserradero", "Cerro_Blanco", "en_proceso"),
    ("Cerro_Blanco", "Gladys", "sin_configurar"),
    ("Cerro_Blanco", "EulaliaDomingo", "sin_configurar"),
    ("El_Carrizal", "Nodo_MartinDonJulio", "en_proceso"),
    ("Nodo_MartinDonJulio", "Martin", "sin_configurar"),
    ("Nodo_MartinDonJulio", "DonJulio", "sin_configurar"),
    ("Union_de_los_Rios", "AP-U7-Pro-Wall", "operativo"),
]

ESTILO = {
    "operativo":      {"drawtype": 0, "color": "00CC00"},
    "en_proceso":     {"drawtype": 3, "color": "FF9900"},
    "sin_configurar": {"drawtype": 2, "color": "999999"},
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

    maps = call("map.get", {"filter": {"name": [MAP_NAME]}}, token)
    if not maps:
        raise RuntimeError(f"No encontre el mapa '{MAP_NAME}'")
    sysmapid = maps[0]["sysmapid"]
    print(f"Mapa: {MAP_NAME} (id {sysmapid})")

    icon_hogar = call("image.get", {"filter": {"name": [ICON_HOGAR_NAME]}}, token)
    if not icon_hogar:
        raise RuntimeError(
            f"No encontre el icono '{ICON_HOGAR_NAME}'. Corré "
            "image.get({'output':['imageid','name']}) y decime el nombre correcto."
        )
    icon_hogar_id = icon_hogar[0]["imageid"]
    icon_by_tipo = {"torre": ICON_TORRE, "nodo": ICON_NODO, "hogar": icon_hogar_id, "ap": ICON_AP}

    nombres_hosts = [n for n, _, _, _ in ELEMENTOS]
    hosts = call("host.get", {"filter": {"host": nombres_hosts}}, token)
    host_by_name = {h["host"]: h["hostid"] for h in hosts}
    faltantes = [n for n in nombres_hosts if n not in host_by_name]
    if faltantes:
        raise RuntimeError(f"Hosts no encontrados en Zabbix: {faltantes}")

    trig_names = [
        ("AP caido (ping)" if tipo == "ap" else f"Nodo caido: {n}")
        for n, tipo, _, _ in ELEMENTOS
    ]
    triggers = call("trigger.get", {"filter": {"description": trig_names}, "output": ["triggerid", "description"]}, token)
    trig_by_desc = {t["description"]: t["triggerid"] for t in triggers}

    selements = []
    selementid_by_name = {}
    for i, (nombre, tipo, x, y) in enumerate(ELEMENTOS, start=1):
        label = "AP U7 Pro Wall" if tipo == "ap" else nombre.replace("_", " ")
        selements.append({
            "selementid": str(i),
            "elementtype": 0,
            "iconid_off": str(icon_by_tipo[tipo]),
            "label": label,
            "label_location": -1,
            "x": x, "y": y,
            "elements": [{"hostid": host_by_name[nombre]}],
        })
        selementid_by_name[nombre] = str(i)

    links = []
    for e1, e2, estado in ENLACES:
        estilo = ESTILO[estado]
        link = {
            "selementid1": selementid_by_name[e1],
            "selementid2": selementid_by_name[e2],
            "drawtype": estilo["drawtype"],
            "color": estilo["color"],
            "linktriggers": [],
        }
        if estado == "operativo":
            trig_desc = "AP caido (ping)" if e2 == "AP-U7-Pro-Wall" else f"Nodo caido: {e2}"
            triggerid = trig_by_desc.get(trig_desc)
            if triggerid:
                link["linktriggers"] = [{"triggerid": triggerid, "drawtype": 0, "color": "DC0000"}]
        links.append(link)

    call("map.update", {
        "sysmapid": sysmapid,
        "width": 1050,
        "height": 980,
        "selements": selements,
        "links": links,
    }, token)
    print(f"Mapa actualizado: {len(selements)} elementos, {len(links)} enlaces.")


if __name__ == "__main__":
    main()
