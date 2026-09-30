"""Mapa de topología generado desde el inventario (convenciones del esquema de campo)."""
from __future__ import annotations

from .model import ESTADOS, MAPA_NOMBRE, ROLES
from .zbx import ZabbixAPI

ANCHO, ALTO = 1000, 1010
URL_DETALLE = "zabbix.php?action=host.dashboard.view&hostid={HOST.ID}"
URL_PROBLEMAS = "zabbix.php?action=problem.view&hostids%5B%5D={HOST.ID}&filter_set=1"


def _iconos(api: ZabbixAPI) -> dict[str, str]:
    nombres = sorted({n for r in ROLES.values() for n in r["iconos"]})
    imgs = {i["name"]: i["imageid"] for i in
            api.call("image.get", {"filter": {"name": nombres}, "output": ["imageid", "name"]})}
    out = {}
    for rol, meta in ROLES.items():
        elegido = next((imgs[n] for n in meta["iconos"] if n in imgs), None)
        if not elegido:
            raise RuntimeError(f"No hay ícono disponible para el rol {rol}: {meta['iconos']}")
        out[rol] = elegido
    return out


def _leyenda() -> tuple[list[dict], list[dict]]:
    x0, y0 = 20, 945
    shapes = [
        {"type": 0, "x": 0, "y": 0, "width": ANCHO, "height": 34, "text": "Red Comunitaria y Científica Las Lagunitas — Topología",
         "font": 9, "font_size": 14, "font_color": "FFFFFF", "text_halign": 0, "text_valign": 0,
         "border_type": 0, "background_color": "1F3A5F", "zindex": 0},
        {"type": 0, "x": x0 - 10, "y": y0 - 10, "width": 970, "height": 70, "text": "",
         "border_type": 1, "border_width": 1, "border_color": "9E9E9E", "background_color": "", "zindex": 0},
    ]
    lines = []
    for i, (estado, meta) in enumerate(ESTADOS.items()):
        x = x0 + i * 220
        # Las líneas decorativas usan otra codificación: 1 sólida, 2 punteada, 3 discontinua.
        tipo = {0: 1, 2: 1, 3: 2, 4: 3}[meta["drawtype"]]
        lines.append({"x1": x, "y1": y0 + 12, "x2": x + 60, "y2": y0 + 12, "line_type": tipo,
                      "line_width": 2, "line_color": meta["color"], "zindex": 1})
        shapes.append({"type": 0, "x": x + 68, "y": y0 + 2, "width": 140, "height": 20,
                       "text": meta["texto"], "font_size": 10, "text_halign": 1, "border_type": 0,
                       "background_color": "", "zindex": 1})
    shapes.append({"type": 0, "x": x0 + 660, "y": y0 - 4, "width": 300, "height": 56,
                   "text": "Ícono/enlace rojo = equipo caído\nGris = tramo aún no monitoreado\n"
                           "Clic en un equipo -> Detalle del equipo",
                   "font_size": 9, "text_halign": 1, "border_type": 0, "background_color": "", "zindex": 1})
    return shapes, lines


def ensure_map(api: ZabbixAPI, inv: dict, hostids: dict[str, str], caidas: dict[str, str], log=print) -> str:
    iconos = _iconos(api)
    selements, sid = [], {}
    for i, e in enumerate(inv["elementos"], start=1):
        x, y = e["mapa"]
        sid[e["host"]] = str(i)
        selements.append({
            "selementid": str(i), "elementtype": 0, "elements": [{"hostid": hostids[e["host"]]}],
            "iconid_off": iconos[e["rol"]], "label": "{HOST.NAME}", "label_location": 0,
            "x": x, "y": y + 40,
            "urls": [{"name": "Detalle del equipo", "url": URL_DETALLE},
                     {"name": "Problemas del equipo", "url": URL_PROBLEMAS}],
        })

    links = []
    # El mapa muestra sitios: si el padre es un dispositivo secundario, el enlace
    # se dibuja desde su sitio.
    sitio = {e["host"]: e["elemento"] for e in inv["todos"]}
    pares = [(sitio[e["padre"]], e["host"]) for e in inv["elementos"]
             if e.get("padre") and sitio[e["padre"]] != e["host"]]
    pares += [tuple(p) for p in inv.get("enlaces_extra") or []]
    for padre, hijo in pares:
        estado = ESTADOS[inv["por_host"][hijo]["estado"]]
        link = {"selementid1": sid[padre], "selementid2": sid[hijo], "drawtype": estado["drawtype"],
                "color": estado["color"], "linktriggers": []}
        if estado["monitoreado"] and hijo in caidas:
            # El tramo se pinta de rojo (línea gruesa) cuando cae el equipo del extremo.
            link["linktriggers"] = [{"triggerid": caidas[hijo], "drawtype": 2, "color": "E53935"}]
        links.append(link)

    shapes, lines = _leyenda()
    params = {"name": MAPA_NOMBRE, "width": ANCHO, "height": ALTO, "selements": selements,
              "links": links, "shapes": shapes, "lines": lines,
              "label_type": 0, "label_location": 0, "highlight": 1, "expandproblem": 1,
              "markelements": 1, "show_unack": 0, "severity_min": 2, "private": 0}
    found = api.call("map.get", {"filter": {"name": [MAPA_NOMBRE]}, "output": ["sysmapid"]})
    if found:
        mid = found[0]["sysmapid"]
        api.call("map.update", {"sysmapid": mid, **params})
    else:
        mid = api.call("map.create", params)["sysmapids"][0]
    log(f"  mapa '{MAPA_NOMBRE}': {len(selements)} equipos, {len(links)} enlaces")
    return mid
