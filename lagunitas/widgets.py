"""Constructores de widgets para dashboards de Zabbix 7.0 (API dashboard.*).

La grilla de dashboards en 7.0 tiene 72 columnas; la altura se mide en filas.
Cada campo se expresa como {"type", "name", "value"} con los tipos de la API:
0 entero, 1 texto, 2 grupo de hosts, 3 host, 4 item, 8 mapa, 9 servicio, 10 SLA.
"""
from __future__ import annotations

from .model import REFRESCO_WIDGETS

INT, STR, GROUP, HOST, ITEM, MAP, SERVICE, SLA = 0, 1, 2, 3, 4, 8, 9, 10


def f(name: str, value, ftype: int = STR) -> dict:
    return {"type": ftype, "name": name, "value": str(value)}


def _thresholds(thresholds) -> list[dict]:
    out = []
    for i, (valor, color) in enumerate(thresholds or []):
        out += [f(f"thresholds.{i}.color", color), f(f"thresholds.{i}.threshold", valor)]
    return out


def widget(wtype: str, name: str, pos: tuple[int, int, int, int], fields: list[dict],
           view_mode: int = 0) -> dict:
    x, y, w, h = pos
    # rf_rate: refresco del widget en segundos (valores válidos: 10, 30, 60, 120, 600, 900).
    return {"type": wtype, "name": name, "x": x, "y": y, "width": w, "height": h,
            "view_mode": view_mode, "fields": fields + [f("rf_rate", REFRESCO_WIDGETS, INT)]}


def _override(ref: str | None) -> list[dict]:
    return [f("override_hostid._reference", f"{ref}._hostid")] if ref else []


def item_value(name, itemid, pos, thresholds=None, decimals=None, override=None,
               desc=None, aggregate=None, show=(1, 2, 3), value_size=None):
    fields = [f("itemid.0", itemid, ITEM)] + [f(f"show.{i}", s, INT) for i, s in enumerate(show)]
    if desc:
        fields.append(f("description", desc))
    if decimals is not None:
        fields.append(f("decimal_places", decimals, INT))
    if value_size:
        fields.append(f("value_size", value_size, INT))
    if aggregate:  # (función, período) ej. (3, "now-24h") -> promedio 24 h
        func, desde = aggregate
        fields += [f("aggregate_function", func, INT), f("time_period.from", desde), f("time_period.to", "now")]
    return widget("item", name, pos, fields + _thresholds(thresholds) + _override(override))


def gauge(name, itemid, pos, vmin, vmax, thresholds, decimals=None, override=None):
    fields = [f("itemid.0", itemid, ITEM), f("min", vmin), f("max", vmax),
              f("th_show_arc", 1, INT), f("th_show_labels", 1, INT)]
    fields += [f(f"show.{i}", s, INT) for i, s in enumerate((1, 2, 3, 4, 5))]
    if decimals is not None:
        fields.append(f("decimal_places", decimals, INT))
    return widget("gauge", name, pos, fields + _thresholds(thresholds) + _override(override))


def svggraph(name, pos, datasets, override=None, lefty_min=None, units=None, legend=True):
    """datasets: lista de dicts con 'itemids' (y 'color') o 'hosts'+'items' (patrones)."""
    fields: list[dict] = []
    for i, ds in enumerate(datasets):
        p = f"ds.{i}"
        color = ds.get("color", "1E88E5")
        if "itemids" in ds:
            # Lista de ítems: en 7.0 el color es por ítem (ds.N.color.M). Un color
            # único en ds.N.color se lee como arreglo y queda "#1" (trazo invisible).
            fields.append(f(f"{p}.dataset_type", 0, INT))
            for j, iid in enumerate(ds["itemids"]):
                fields += [f(f"{p}.itemids.{j}", iid, ITEM), f(f"{p}.color.{j}", color)]
        else:
            fields += [f(f"{p}.dataset_type", 1, INT), f(f"{p}.color", color)]
            for j, h in enumerate(ds.get("hosts", [])):
                fields.append(f(f"{p}.hosts.{j}", h))
            for j, it in enumerate(ds["items"]):
                fields.append(f(f"{p}.items.{j}", it))
        fields += [f(f"{p}.fill", ds.get("fill", 2), INT),
                   f(f"{p}.width", ds.get("width", 2), INT),
                   f(f"{p}.transparency", ds.get("transparency", 5), INT)]
        if ds.get("label"):
            fields.append(f(f"{p}.data_set_label", ds["label"]))
        if ds.get("aggregate"):
            func, interval = ds["aggregate"]
            fields += [f(f"{p}.aggregate_function", func, INT), f(f"{p}.aggregate_interval", interval)]
        if ds.get("stairs"):
            fields.append(f(f"{p}.type", 2, INT))
    if lefty_min is not None:
        fields.append(f("lefty_min", lefty_min))
    if units:
        fields += [f("lefty_units", 1, INT), f("lefty_static_units", units)]
    if legend:
        fields += [f("legend", 1, INT), f("legend_statistic", 1, INT)]
    return widget("svggraph", name, pos, fields + _override(override))


def problems(name, pos, groupids=(), severities=(), override=None, show_lines=25,
             show_tags=1, reference=None):
    fields = [f(f"groupids.{i}", g, GROUP) for i, g in enumerate(groupids)]
    fields += [f(f"severities.{i}", s, INT) for i, s in enumerate(severities)]
    fields += [f("show_lines", show_lines, INT), f("show_tags", show_tags, INT),
               f("show_opdata", 1, INT), f("highlight_row", 1, INT)]
    if reference:
        fields.append(f("reference", reference))
    return widget("problems", name, pos, fields + _override(override))


def lagunitas_red(name, pos, groupids, show_disabled=True):
    """Widget del módulo propio 'Red Las Lagunitas' (zabbix/modules/lagunitas-red)."""
    fields = [f(f"groupids.{i}", g, GROUP) for i, g in enumerate(groupids)]
    fields.append(f("show_disabled", 1 if show_disabled else 0, INT))
    return widget("lagunitas_red", name, pos, fields)


def problems_by_severity(name, pos, groupids=(), layout_vertical=False):
    fields = [f(f"groupids.{i}", g, GROUP) for i, g in enumerate(groupids)]
    fields += [f("show_type", 1, INT),  # 1 = totales por severidad
               f("layout", 1 if layout_vertical else 0, INT)]
    return widget("problemsbysv", name, pos, fields)


def mapa(name, sysmapid, pos, reference=None):
    fields = [f("sysmapid.0", sysmapid, MAP)]
    if reference:
        fields.append(f("reference", reference))
    return widget("map", name, pos, fields)


def host_navigator(name, pos, groupids, reference, group_by_tag=None, show_lines=100):
    fields = [f(f"groupids.{i}", g, GROUP) for i, g in enumerate(groupids)]
    fields += [f("reference", reference), f("status", 0, INT),  # 0 = solo habilitados
               f("problems", 1, INT),  # 1 = mostrar problemas no suprimidos
               f("show_lines", show_lines, INT)]
    if group_by_tag:
        # attribute 1 = agrupar por valor de tag
        fields += [f("group_by.0.attribute", 1, INT), f("group_by.0.tag_name", group_by_tag)]
    return widget("hostnavigator", name, pos, fields)


def honeycomb(name, pos, groupids, items, reference, thresholds, label_mapped=True):
    fields = [f(f"groupids.{i}", g, GROUP) for i, g in enumerate(groupids)]
    fields += [f(f"items.{i}", it) for i, it in enumerate(items)]
    fields += [f("reference", reference),
               f("primary_label_type", 0, INT), f("primary_label", "{HOST.NAME}"),
               # Tamaño fijo (% de la celda) para que todos los nombres se vean iguales.
               f("primary_label_size_type", 1, INT), f("primary_label_size", 20, INT),
               f("secondary_label_size_type", 1, INT), f("secondary_label_size", 30, INT),
               f("secondary_label_bold", 1, INT),
               f("secondary_label_type", 1, INT),  # 1 = valor del item
               f("secondary_label_decimal_places", 0, INT),
               f("interpolation", 0, INT)]
    return widget("honeycomb", name, pos, fields + _thresholds(thresholds))


def tophosts(name, pos, groupids, columns, order_column, show_lines=30, reference=None):
    """columns: lista de dicts {name, data(1 item|2 host name), item, display, min, max, ...}."""
    fields = [f(f"groupids.{i}", g, GROUP) for i, g in enumerate(groupids)]
    for i, c in enumerate(columns):
        p = f"columns.{i}"
        fields += [f(f"{p}.name", c["name"]), f(f"{p}.data", c["data"], INT),
                   f(f"{p}.aggregate_function", c.get("aggregate_function", 0), INT),
                   f(f"{p}.decimal_places", c.get("decimals", 2), INT),
                   f(f"{p}.base_color", c.get("base_color", ""))]
        if c["data"] == 1:
            fields += [f(f"{p}.item", c["item"]), f(f"{p}.display", c.get("display", 1), INT),
                       f(f"{p}.history", 1, INT)]
            if "min" in c:
                fields += [f(f"{p}.min", c["min"]), f(f"{p}.max", c["max"])]
            for j, (valor, color) in enumerate(c.get("thresholds", [])):
                fields += [f(f"{p}.thresholds.{j}.color", color), f(f"{p}.thresholds.{j}.threshold", valor)]
    fields += [f("column", order_column, INT), f("order", 3, INT),  # 3 = bottom N (peores primero)
               f("show_lines", show_lines, INT)]
    if reference:
        fields.append(f("reference", reference))
    return widget("tophosts", name, pos, fields)


def sla_report(name, pos, slaid, serviceid=None, show_periods=6):
    fields = [f("slaid.0", slaid, SLA), f("show_periods", show_periods, INT)]
    if serviceid:
        fields.append(f("serviceid.0", serviceid, SERVICE))
    return widget("slareport", name, pos, fields)


def item_history(name, pos, columns, override=None, show_lines=15):
    """columns: lista de (nombre, itemid)."""
    fields = []
    for i, (nombre, itemid) in enumerate(columns):
        fields += [f(f"columns.{i}.name", nombre), f(f"columns.{i}.itemid", itemid, ITEM)]
    fields += [f("show_lines", show_lines, INT)]
    return widget("itemhistory", name, pos, fields + _override(override))


def url(name, pos, link):
    return widget("url", name, pos, [f("url", link)])
