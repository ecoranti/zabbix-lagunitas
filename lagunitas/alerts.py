"""Notificaciones: grupo de operadores, acción de alerta y (opcional) Telegram."""
from __future__ import annotations

import os

from .model import ACCION_NOMBRE, GRUPO_USUARIOS, SITIO_GRUPO
from .zbx import ZabbixAPI

COND_GRUPO, COND_SEVERIDAD, COND_SUPRIMIDO = 0, 4, 16
OP_IGUAL, OP_MAYOR_IGUAL, OP_NO = 0, 5, 11


def ensure_usergroup(api: ZabbixAPI, groupid: str) -> str:
    params = {"hostgroup_rights": [{"id": groupid, "permission": 2}],  # 2 = lectura
              "users": [{"userid": u["userid"]} for u in
                        api.call("user.get", {"filter": {"username": ["Admin"]}, "output": ["userid"]})]}
    found = api.call("usergroup.get", {"filter": {"name": [GRUPO_USUARIOS]}, "output": ["usrgrpid"]})
    if found:
        gid = found[0]["usrgrpid"]
        api.call("usergroup.update", {"usrgrpid": gid, **params})
        return gid
    return api.call("usergroup.create", {"name": GRUPO_USUARIOS, **params})["usrgrpids"][0]


def ensure_action(api: ZabbixAPI, hostgroupid: str, usrgrpid: str, severidad_min: int = 3) -> str:
    params = {
        "status": 0, "esc_period": "30m", "pause_symptoms": 1, "pause_suppressed": 1,
        "notify_if_canceled": 1,
        "filter": {"evaltype": 0, "conditions": [
            {"conditiontype": COND_GRUPO, "operator": OP_IGUAL, "value": hostgroupid},
            {"conditiontype": COND_SEVERIDAD, "operator": OP_MAYOR_IGUAL, "value": str(severidad_min)},
            {"conditiontype": COND_SUPRIMIDO, "operator": OP_NO},
        ]},
        # Aviso inmediato y recordatorio a los 30 min si el problema sigue abierto.
        "operations": [
            {"operationtype": 0, "esc_step_from": 1, "esc_step_to": 2,
             "opmessage": {"default_msg": 1, "mediatypeid": "0"},
             "opmessage_grp": [{"usrgrpid": usrgrpid}]},
        ],
        "recovery_operations": [{"operationtype": 11, "opmessage": {"default_msg": 1}}],
        "update_operations": [{"operationtype": 12, "opmessage": {"default_msg": 1}}],
    }
    found = api.call("action.get", {"filter": {"name": [ACCION_NOMBRE]}, "output": ["actionid"]})
    if found:
        aid = found[0]["actionid"]
        api.call("action.update", {"actionid": aid, **params})
        return aid
    return api.call("action.create", {"name": ACCION_NOMBRE, "eventsource": 0, **params})["actionids"][0]


# Mensajes en español (texto plano: el script de Zabbix escapa el texto según el modo de formato,
# así que HTML/Markdown no aportan negritas y Markdown falla con guiones bajos en los nombres).
PLANTILLAS_TELEGRAM = [
    {"eventsource": 0, "recovery": 0, "subject": "🔴 {EVENT.SEVERITY}: {EVENT.NAME}",
     "message": "Equipo: {HOST.NAME} ({HOST.IP})\nInicio: {EVENT.DATE} {EVENT.TIME}\n"
                "Dato: {EVENT.OPDATA}\nRed Las Lagunitas · evento {EVENT.ID}"},
    {"eventsource": 0, "recovery": 1, "subject": "✅ Resuelto: {EVENT.NAME}",
     "message": "Equipo: {HOST.NAME}\nDuración: {EVENT.DURATION}\n"
                "Resuelto: {EVENT.RECOVERY.DATE} {EVENT.RECOVERY.TIME}"},
    {"eventsource": 0, "recovery": 2, "subject": "💬 Actualización: {EVENT.NAME}",
     "message": "{USER.FULLNAME} {EVENT.UPDATE.ACTION} ({EVENT.UPDATE.DATE} {EVENT.UPDATE.TIME})\n"
                "{EVENT.UPDATE.MESSAGE}\nEstado actual: {EVENT.STATUS}"},
]


def ensure_telegram(api: ZabbixAPI, log=print) -> None:
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        log("  Telegram: sin TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID en .env (se omite)")
        return
    # En 7.0 los parámetros del webhook vienen con output=extend (no hay selectParameters).
    mt = api.call("mediatype.get", {"filter": {"name": ["Telegram"]}, "output": "extend",
                                    "selectMessageTemplates": "extend"})
    if not mt:
        log("  [aviso] no existe el media type 'Telegram' en este Zabbix")
        return
    mt = mt[0]
    valores = {"api_token": token, "api_parse_mode": ""}
    params = [{"name": p["name"], "value": valores.get(p["name"], p["value"])} for p in mt["parameters"]]
    plantillas = [{k: t[k] for k in ("eventsource", "recovery", "subject", "message")}
                  for t in mt["message_templates"] if t["eventsource"] != "0"] + PLANTILLAS_TELEGRAM
    api.call("mediatype.update", {"mediatypeid": mt["mediatypeid"], "status": 0, "parameters": params,
                                  "message_templates": plantillas})
    admin = api.call("user.get", {"filter": {"username": ["Admin"]}, "output": ["userid"],
                                  "selectMedias": ["mediatypeid", "sendto", "active", "severity", "period"]})[0]
    medias = [m for m in admin["medias"] if m["mediatypeid"] != mt["mediatypeid"]]
    medias.append({"mediatypeid": mt["mediatypeid"], "sendto": chat, "active": 0,
                   "severity": 56, "period": "1-7,00:00-24:00"})  # 56 = average + high + disaster
    api.call("user.update", {"userid": admin["userid"], "medias": medias})
    log(f"  Telegram: media type habilitado (mensajes en español) y asignado al usuario Admin (chat {chat})")


def ensure_alerting(api: ZabbixAPI, groups: dict[str, str], log=print) -> None:
    ug = ensure_usergroup(api, groups[SITIO_GRUPO])
    ensure_action(api, groups[SITIO_GRUPO], ug)
    log(f"  grupo '{GRUPO_USUARIOS}' y acción '{ACCION_NOMBRE}' (severidad >= Average)")
    ensure_telegram(api, log)
