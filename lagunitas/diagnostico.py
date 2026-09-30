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


# ---------------------------------------------------------------- Telegram

def _telegram(metodo: str, datos: dict | None = None) -> dict:
    """Llama a la API de bots de Telegram con el token de .env (el token nunca se imprime)."""
    import requests
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("Falta TELEGRAM_BOT_TOKEN en .env (ver docs/manual-administracion.md, Notificaciones)")
    r = requests.post(f"https://api.telegram.org/bot{token}/{metodo}", json=datos or {}, timeout=15)
    cuerpo = r.json()
    if not cuerpo.get("ok"):
        raise SystemExit(f"Telegram rechazó la llamada: {cuerpo.get('description', r.status_code)}")
    return cuerpo["result"]


def telegram_chat_id(log=print) -> None:
    """Lista los chats que le escribieron al bot (para completar TELEGRAM_CHAT_ID)."""
    bot = _telegram("getMe")
    log(f"  Bot: @{bot['username']} ({bot['first_name']})")
    chats = {}
    for u in _telegram("getUpdates"):
        msg = u.get("message") or u.get("channel_post") or u.get("my_chat_member") or {}
        chat = msg.get("chat")
        if chat:
            chats[chat["id"]] = chat
    if not chats:
        log("  Ningún chat todavía: escribile cualquier mensaje al bot (o agregalo a un grupo y escribí\n"
            "  algo en el grupo) y volvé a correr este comando.")
        return
    for cid, c in chats.items():
        nombre = c.get("title") or " ".join(x for x in (c.get("first_name"), c.get("last_name")) if x)
        log(f"  TELEGRAM_CHAT_ID={cid}    ({c['type']}: {nombre})")


def probar_telegram(log=print) -> None:
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not chat:
        raise SystemExit("Falta TELEGRAM_CHAT_ID en .env: obtenelo con bin/lagunitas telegram-chat-id")
    _telegram("sendMessage", {"chat_id": chat, "text":
              "✅ Prueba de notificaciones — Monitoreo Red Las Lagunitas.\n"
              "Si ves este mensaje, Zabbix puede avisarte por Telegram."})
    log(f"  Mensaje de prueba enviado al chat {chat}")
    seguridad_telegram(chat, log)


def seguridad_telegram(chat: str, log=print) -> None:
    """Chequea que el bot sea de solo envío (ver Guía de implementación, Seguridad del bot)."""
    me = _telegram("getMe")
    webhook = _telegram("getWebhookInfo").get("url", "")
    comandos = _telegram("getMyCommands")
    miembro = _telegram("getChatMember", {"chat_id": chat, "user_id": me["id"]})
    tipo = _telegram("getChat", {"chat_id": chat})["type"]
    checks = [
        (not webhook, "sin webhook: nada recibe ni procesa mensajes entrantes",
         f"hay un webhook configurado ({webhook}): eliminarlo si no es propio"),
        (not me.get("can_join_groups"), "nadie puede agregar el bot a otros grupos",
         "cualquiera puede agregar el bot a sus grupos: BotFather -> /setjoingroups -> Disable"),
        (not me.get("can_read_all_group_messages"), "modo privacidad activo (no lee el grupo)",
         "el bot lee todos los mensajes del grupo: BotFather -> /setprivacy -> Enable"),
        (not comandos and not me.get("supports_inline_queries"), "sin comandos ni modo inline",
         "el bot publica comandos o modo inline: quitarlos (/deletecommands, /setinline)"),
        (miembro["status"] == "member", "en el grupo es miembro sin permisos de administrador",
         f"en el grupo es '{miembro['status']}': quitarle los permisos de administrador"),
        (tipo in ("group", "supergroup"), f"destino: {tipo}",
         "el destino es un chat privado: para operadores conviene un grupo"),
    ]
    log("  Seguridad del bot:")
    for ok, bien, mal in checks:
        log(f"    {'OK ' if ok else 'REVISAR'} {bien if ok else mal}")
