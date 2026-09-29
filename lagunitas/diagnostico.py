"""Diagnóstico previo a integrar equipos: SNMP (airMAX / Mikrotik) y API de UniFi.

Las pruebas se ejecutan compartiendo la red del contenedor zabbix-server
(docker --network container:<server>), es decir, con exactamente la misma
conectividad que tendrá Zabbix al monitorear el equipo.
"""
from __future__ import annotations

import json
import os
import subprocess

from .config import ROOT

IMAGEN_TOOLS = "lagunitas/snmptools"

# (nombre, OID, formato)
PRUEBAS = {
    "sistema": [
        ("Nombre (sysName)", "1.3.6.1.2.1.1.5.0", None),
        ("Descripción (sysDescr)", "1.3.6.1.2.1.1.1.0", None),
        ("Uptime", "1.3.6.1.2.1.1.3.0", None),
    ],
    "airmax": [
        ("Modelo", "1.2.840.10036.3.1.2.1.3.5", None),
        ("Firmware airOS", "1.2.840.10036.3.1.2.1.4.5", None),
        ("Modo (1=SM, 2=AP)", "1.3.6.1.4.1.41112.1.4.1.1.2.1", None),
        ("Frecuencia (MHz)", "1.3.6.1.4.1.41112.1.4.1.1.4.1", None),
        ("SSID", "1.3.6.1.4.1.41112.1.4.5.1.2.1", None),
        ("Señal (dBm)", "1.3.6.1.4.1.41112.1.4.5.1.5.1", None),
        ("Ruido (dBm)", "1.3.6.1.4.1.41112.1.4.5.1.8.1", None),
        ("CCQ (%)", "1.3.6.1.4.1.41112.1.4.5.1.7.1", None),
        ("airMAX calidad (%)", "1.3.6.1.4.1.41112.1.4.6.1.3.1", None),
        ("airMAX capacidad (%)", "1.3.6.1.4.1.41112.1.4.6.1.4.1", None),
        ("Estaciones asociadas", "1.3.6.1.4.1.41112.1.4.5.1.15.1", None),
        ("CPU (%) [airOS 8]", "1.3.6.1.4.1.41112.1.4.8.3.0", None),
    ],
    "mikrotik": [
        ("RouterOS", "1.3.6.1.4.1.14988.1.1.4.4.0", None),
        ("Número de serie", "1.3.6.1.4.1.14988.1.1.7.3.0", None),
        ("Voltaje (décimas de V)", "1.3.6.1.4.1.14988.1.1.3.8.0", None),
        ("Temperatura (décimas de °C)", "1.3.6.1.4.1.14988.1.1.3.10.0", None),
        ("Leases DHCP activos", "1.3.6.1.4.1.14988.1.1.6.1.0", None),
        ("Carga CPU núcleo 1 (%)", "1.3.6.1.2.1.25.3.3.1.2.1", None),
    ],
}


def _server() -> str:
    out = subprocess.run(["docker", "ps", "--filter", "name=zabbix-server", "--format", "{{.Names}}"],
                         capture_output=True, text=True).stdout.split()
    if not out:
        raise SystemExit("No encontré el contenedor zabbix-server en ejecución (docker compose up -d).")
    return out[0]


def _asegurar_tools() -> None:
    if subprocess.run(["docker", "image", "inspect", IMAGEN_TOOLS], capture_output=True).returncode != 0:
        subprocess.run(["docker", "build", "-q", "-t", IMAGEN_TOOLS, "-"], input="FROM alpine:3.20\n"
                       "RUN apk add --no-cache net-snmp-tools curl\n", text=True, capture_output=True, check=True)


def _snmpget(server: str, ip: str, comunidad: str, oids: list[str]) -> dict[str, str]:
    r = subprocess.run(["docker", "run", "--rm", "--network", f"container:{server}", IMAGEN_TOOLS,
                        "snmpget", "-v2c", "-c", comunidad, "-t", "3", "-r", "1", "-On", ip, *oids],
                       capture_output=True, text=True)
    valores = {}
    for linea in r.stdout.splitlines():
        if " = " in linea:
            oid, val = linea.split(" = ", 1)
            valores[oid.lstrip(".")] = val
    if not valores and r.stderr:
        valores["_error"] = r.stderr.strip()
    return valores


def probar_snmp(ip: str, comunidad: str | None = None, log=print) -> bool:
    comunidad = comunidad or os.environ.get("SNMP_COMMUNITY") or "public"
    _asegurar_tools()
    server = _server()
    log(f"Probando SNMP v2c en {ip} (comunidad '{comunidad}') desde la red de {server}...\n")
    ok = True
    tipo = None
    for grupo in ("sistema", "airmax", "mikrotik"):
        pruebas = PRUEBAS[grupo]
        valores = _snmpget(server, ip, comunidad, [oid for _, oid, _ in pruebas])
        if "_error" in valores:
            log(f"  ERROR: {valores['_error']}")
            log("  -> Verificar: SNMP habilitado en el equipo, comunidad, firewall (UDP 161) y ruta.")
            return False
        presentes = [(n, valores.get(oid, "")) for n, oid, _ in pruebas]
        validos = [(n, v) for n, v in presentes if v and "No Such" not in v]
        if grupo == "sistema":
            log("Sistema:")
        elif validos:
            tipo = grupo
            log(f"\nMétricas {('Ubiquiti airMAX' if grupo == 'airmax' else 'Mikrotik')}:")
        else:
            continue
        for n, v in presentes:
            marca = "✔" if v and "No Such" not in v else "✘"
            log(f"  {marca} {n:<30} {v.split(': ', 1)[-1] if v else 'sin respuesta'}")
            if grupo == "sistema" and marca == "✘":
                ok = False
    perfil = {"airmax": "airos_snmp", "mikrotik": "mikrotik_snmp"}.get(tipo)
    log("\nResultado: " + (f"equipo compatible. Usar perfiles: [icmp, {perfil}]" if ok and perfil else
                            "responde SNMP pero no se reconoció como airMAX ni Mikrotik: usar [icmp]" if ok else
                            "el equipo no respondió a todas las consultas básicas de SNMP"))
    return ok


def unifi_ids(host: str, puerto: str, api_key: str | None = None, log=print) -> None:
    """Lista sites y dispositivos de un controlador UniFi (API de integración)."""
    api_key = api_key or os.environ.get("UNIFI_API_KEY")
    if not api_key:
        raise SystemExit("Definí UNIFI_API_KEY en .env (UniFi Network -> Integrations -> Create API Key)")
    _asegurar_tools()
    server = _server()
    base = f"https://{host}:{puerto}/proxy/network/integration/v1"

    def get(path):
        r = subprocess.run(["docker", "run", "--rm", "--network", f"container:{server}", IMAGEN_TOOLS,
                            "curl", "-sk", "-m", "10", "-H", f"X-API-KEY: {api_key}",
                            "-H", "Accept: application/json", "-w", "\n%{http_code}", base + path],
                           capture_output=True, text=True)
        cuerpo, _, codigo = r.stdout.rpartition("\n")
        if codigo != "200":
            raise SystemExit(f"GET {path} -> HTTP {codigo or 'sin conexión'} {r.stderr.strip()}\n"
                             "Verificar IP/puerto del controlador (UniFi OS Server puede cambiar de puerto "
                             "al reiniciarse: lsof -nP -iTCP -sTCP:LISTEN) y la API key.")
        return json.loads(cuerpo)

    for site in get("/sites?limit=50").get("data", []):
        log(f"Site: {site.get('name')}   {{$UNIFI.SITE.ID}} = {site.get('id')}")
        for d in get(f"/sites/{site['id']}/devices?limit=200").get("data", []):
            log(f"  - {d.get('name', '?'):<28} modelo={d.get('model', '?'):<16} ip={d.get('ipAddress', '?'):<15} "
                f"estado={d.get('state', '?'):<8} {{$UNIFI.DEVICE.ID}} = {d.get('id')}")
    log(f"\nMacros del host en el inventario: {{$UNIFI.HOST}}: {host}  {{$UNIFI.PORT}}: \"{puerto}\"")


__all__ = ["probar_snmp", "unifi_ids", "ROOT"]
