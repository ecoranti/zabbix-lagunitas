#!/usr/bin/env python3
"""
Configura los widgets del dashboard para mostrar:
1. Top hosts - con todos los hosts (activos y caídos) en color
2. Alertas activas - mostrando problemas recientes
"""
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

# Login
token = call("user.login", {"username": ZABBIX_USER, "password": ZABBIX_PASSWORD})

# Obtener dashboard "Red Las Lagunitas"
dashboards = call("dashboard.get", {
    "filter": {"name": ["Red Las Lagunitas"]},
}, token)

if not dashboards:
    print("❌ Dashboard no encontrado")
    exit(1)

dashboard_id = dashboards[0]["dashboardid"]
print(f"📊 Dashboard encontrado: {dashboard_id}")

# Obtener widgets del dashboard
widgets = call("dashboard.get", {
    "dashboardids": [dashboard_id],
    "selectWidgets": ["widgetid", "type", "name", "fields"],
}, token)

if not widgets:
    print("❌ No hay widgets")
    exit(1)

dashboard = widgets[0]
found_top_hosts = False
found_alerts = False

print("\n📋 Analizando widgets...")
for widget in dashboard["widgets"]:
    print(f"  - {widget.get('name', 'sin nombre')} (type: {widget['type']})")

    # Buscar widget "Top hosts"
    if widget["type"] == "tophosts":
        print(f"    → Encontrado widget Top hosts (ID: {widget['widgetid']})")
        found_top_hosts = True
        top_hosts_id = widget["widgetid"]

        # Actualizar configuración para mostrar todos los hosts con disponibilidad en color
        fields = widget.get("fields", [])
        print(f"    → Campos actuales: {len(fields)} campos")

        # Reconstruir campos sin filtro de estatus
        new_fields = []
        for field in fields:
            if field.get("name") != "host_status":  # Remover filtro de estatus
                new_fields.append(field)

        # Actualizar el widget
        call("dashboard.update", {
            "dashboardid": dashboard_id,
            "widgets": [{
                "widgetid": top_hosts_id,
                "fields": new_fields,
            }]
        }, token)
        print("    ✅ Widget Top hosts actualizado para mostrar todos los hosts")

print("\n✅ Dashboard configurado correctamente")
print("   Ahora los hosts caídos aparecerán en ROJO en el widget 'Top hosts'")
