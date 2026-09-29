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


def ensure_telegram(api: ZabbixAPI, log=print) -> None:
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        log("  Telegram: sin TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID en .env (se omite)")
        return
    mt = api.call("mediatype.get", {"filter": {"name": ["Telegram"]}, "output": ["mediatypeid"],
                                    "selectParameters": "extend"})
    if not mt:
        log("  [aviso] no existe el media type 'Telegram' en este Zabbix")
        return
    mt = mt[0]
    params = [{"name": p["name"], "value": token if p["name"] == "api_token" else p["value"]}
              for p in mt["parameters"]]
    api.call("mediatype.update", {"mediatypeid": mt["mediatypeid"], "status": 0, "parameters": params})
    admin = api.call("user.get", {"filter": {"username": ["Admin"]}, "output": ["userid"],
                                  "selectMedias": ["mediatypeid", "sendto", "active", "severity", "period"]})[0]
    medias = [m for m in admin["medias"] if m["mediatypeid"] != mt["mediatypeid"]]
    medias.append({"mediatypeid": mt["mediatypeid"], "sendto": chat, "active": 0,
                   "severity": 56, "period": "1-7,00:00-24:00"})  # 56 = average + high + disaster
    api.call("user.update", {"userid": admin["userid"], "medias": medias})
    log("  Telegram: media type habilitado y asignado al usuario Admin")


def ensure_alerting(api: ZabbixAPI, groups: dict[str, str], log=print) -> None:
    ug = ensure_usergroup(api, groups[SITIO_GRUPO])
    ensure_action(api, groups[SITIO_GRUPO], ug)
    log(f"  grupo '{GRUPO_USUARIOS}' y acción '{ACCION_NOMBRE}' (severidad >= Average)")
    ensure_telegram(api, log)
