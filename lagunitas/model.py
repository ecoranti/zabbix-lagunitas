"""Convenciones del proyecto: roles, estados, perfiles de monitoreo y nombres."""

SITIO_GRUPO = "Las Lagunitas"
TEMPLATE_GRUPO = "Templates/Las Lagunitas"

TPL_ICMP = "Lagunitas - Disponibilidad ICMP"
TPL_UNIFI = "Lagunitas - AP UniFi por API"
TPL_AIRMAX = "Lagunitas - Ubiquiti airMAX por SNMP"
TPL_MIKROTIK = "Lagunitas - Mikrotik por SNMP"

# Trigger "equipo sin respuesta" de cada template de disponibilidad: es el que
# se usa para dependencias padre -> hijo, enlaces del mapa y servicios.
TRIGGER_CAIDA = {
    TPL_ICMP: "{HOST.NAME}: sin respuesta (ICMP)",
    TPL_UNIFI: "{HOST.NAME}: AP fuera de línea según UniFi",
}

MAPA_NOMBRE = "Las Lagunitas - Topología"
DASHBOARD_NOMBRE = "Las Lagunitas - Centro de monitoreo"
SERVICIO_RAIZ = "Red Las Lagunitas"
SLA_NOMBRE = "Las Lagunitas - Disponibilidad mensual"
GRUPO_USUARIOS = "Operadores Las Lagunitas"
ACCION_NOMBRE = "Las Lagunitas - Notificar caídas"

ROLES = {
    "gateway": {"grupo": "Las Lagunitas/Gateway", "etiqueta": "Gateway",
                "iconos": ["Router_(64)", "Router_(48)"],
                "servicio": "Salida a Internet"},
    "torre": {"grupo": "Las Lagunitas/Torres", "etiqueta": "Torre",
              "iconos": ["Satellite_antenna_(64)", "Satellite_antenna_(48)"],
              "servicio": "Backbone (torres)"},
    "nodo": {"grupo": "Las Lagunitas/Nodos", "etiqueta": "Nodo intermedio",
             "iconos": ["Switch_(48)", "Switch_(64)"],
             "servicio": "Nodos intermedios"},
    "hogar": {"grupo": "Las Lagunitas/Hogares e instituciones", "etiqueta": "Hogar",
              "iconos": ["House_(48)", "House_(64)"],
              "servicio": "Hogares e instituciones"},
    "institucion": {"grupo": "Las Lagunitas/Hogares e instituciones", "etiqueta": "Institución",
                    "iconos": ["House_(64)", "House_(48)"],
                    "servicio": "Hogares e instituciones"},
    "ap": {"grupo": "Las Lagunitas/Access points", "etiqueta": "Access point",
           "iconos": ["Hub_(48)", "Hub_(64)"],
           "servicio": "Access points"},
}

ESTADOS = {
    # drawtype de enlaces en mapas de Zabbix: 0 línea, 2 línea gruesa, 3 punteada, 4 discontinua
    "operativo": {"monitoreado": True, "drawtype": 0, "color": "2E7D32", "texto": "Operativo"},
    "en_proceso": {"monitoreado": False, "drawtype": 4, "color": "F9A825", "texto": "En proceso"},
    "sin_configurar": {"monitoreado": False, "drawtype": 3, "color": "9E9E9E", "texto": "Sin configurar"},
}

# Perfil -> template(s) a vincular e interfaz requerida.
#   interfaz: 1 = agent (solo como destino de IP para checks simples), 2 = SNMP
PERFILES = {
    "icmp": {"templates": [TPL_ICMP], "interfaz": 1},
    "unifi_api": {"templates": [TPL_UNIFI], "interfaz": 1},
    # Radios Ubiquiti airMAX (PowerBeam, LiteBeam, NanoStation, NanoLoco) y routers
    # Mikrotik, por SNMP v2c. Se combinan con "icmp" (disponibilidad).
    "airos_snmp": {"templates": [TPL_AIRMAX], "interfaz": 2},
    "mikrotik_snmp": {"templates": [TPL_MIKROTIK], "interfaz": 2},
}

# Función del equipo dentro del sitio (informativa + perfil de simulación en el LAB).
FUNCIONES = {"ap", "sm", "ptp", "router", "switch", "otro"}

SEVERIDAD = {"info": 1, "warning": 2, "average": 3, "high": 4, "disaster": 5}
