"""Pruebas de validación guiadas del LAB, de extremo a extremo.

Cada prueba aplica una falla, sigue en vivo los problemas que abre Zabbix y los avisos
que manda por Telegram (leídos de la API: event.get y alert.get), restaura el equipo y
muestra un resumen con los tiempos medidos, listo para el informe o la presentación.

  1  Degradación por SNMP: señal débil (Walter), interferencia (Mesada) y batería baja
     (Gateway Mikrotik). Alertas Warning entre los 6 y 11 min; cierre automático.
  2  Caída troncal: se detiene la torre Unión de los Ríos y los 18 equipos que dependen
     de ella. Una única alerta High y una única notificación.
  3  Telegram: caída del Nodo Kika. Un aviso al grupo de operadores y el aviso de
     resuelto como respuesta a ese mensaje.
  4  Latencia alta: 300 ms de retardo en las respuestas de Mesada (tc netem). Alerta
     Warning en ~3 min y cierre ~3 min después de quitarla.

aplicar() y restaurar() son las mismas acciones que dispara el menú interactivo.
"""
from __future__ import annotations

import select
import sys
import time

from . import lab
from .hosts import ensure_hostgroup
from .model import ACCION_DEGRADACION, ACCION_NOMBRE, SITIO_GRUPO

SEVERIDAD = ["No clasif.", "Info", "Advertencia", "Media", "Alta", "Desastre"]
POLL = 5  # segundos entre consultas a Zabbix
ESTADO_AVISO = {"0": "pendiente", "1": "enviado", "2": "FALLÓ"}

PRUEBAS = {
    1: {"titulo": "Degradación por SNMP",
        "escenarios": [("Walter", "senal-debil"), ("Mesada", "interferencia"),
                       ("Gateway_Mikrotik", "bateria-baja")],
        "espera": 15 * 60, "cierre": 20 * 60},
    2: {"titulo": "Caída troncal", "equipo": "Union_de_los_Rios", "espera": 5 * 60, "cierre": 5 * 60},
    3: {"titulo": "Notificación por Telegram", "equipo": "Nodo_Kika", "espera": 5 * 60, "cierre": 5 * 60},
    4: {"titulo": "Latencia alta", "latencia": "Mesada", "espera": 10 * 60, "cierre": 10 * 60},
}
OBSERVAR_TRAS_ALERTA = 60  # caídas: segundos extra para confirmar que no se abre ninguna otra alerta


def equipos_de(p: dict) -> list[str]:
    if "escenarios" in p:
        return [h for h, _ in p["escenarios"]]
    return [p.get("equipo") or p["latencia"]]


def activa(p: dict, estados: dict[str, str], fallas: dict[str, dict]) -> bool:
    """Si la falla de la prueba está aplicada (según los contenedores y sus marcas)."""
    if "escenarios" in p:
        return any(fallas.get(h, {}).get("escenario") == esc for h, esc in p["escenarios"])
    if "latencia" in p:
        return bool(fallas.get(p["latencia"], {}).get("latencia"))
    return estados.get(p["equipo"]) != "running"


def aplicar(inv: dict, p: dict) -> None:
    if "escenarios" in p:
        for h, esc in p["escenarios"]:
            lab.escenario(inv, h, esc, log=lambda *_: None)
    elif "latencia" in p:
        lab.latencia(inv, p["latencia"], lab.LATENCIA_PRUEBA, log=lambda *_: None)
    else:
        lab.caida(inv, p["equipo"], log=lambda *_: None)


def restaurar(inv: dict, p: dict) -> None:
    if "escenarios" in p:
        for h, _ in p["escenarios"]:
            lab.escenario(inv, h, "normal", log=lambda *_: None)
    elif "latencia" in p:
        lab.latencia(inv, p["latencia"], 0, log=lambda *_: None)
    else:
        lab.recuperar(inv, p["equipo"], log=lambda *_: None)


def _mmss(seg: float | None) -> str:
    if seg is None:
        return "—"
    seg = int(round(seg))
    return f"{seg // 60}:{seg % 60:02d}"


class _Seguimiento:
    """Problemas y avisos de Telegram de los equipos de la prueba desde su inicio (así no
    se cuentan problemas ajenos, como los del AP UniFi real)."""

    def __init__(self, api, t0: float, hosts: list[str], log):
        self.api, self.t0, self.log = api, int(t0), log
        self.t_restaura: float | None = None
        self.hostids = [h["hostid"] for h in api.call("host.get", {
            "groupids": [ensure_hostgroup(api, SITIO_GRUPO)], "filter": {"host": hosts}, "output": ["hostid"]})]
        self.acciones = [a["actionid"] for a in api.call("action.get", {
            "filter": {"name": [ACCION_NOMBRE, ACCION_DEGRADACION]}, "output": ["actionid"]})]
        self.eventos: dict[str, dict] = {}
        self._vistos: set[tuple] = set()

    def actualizar(self) -> None:
        evs = self.api.call("event.get", {
            "source": 0, "object": 0, "value": 1, "time_from": self.t0, "hostids": self.hostids,
            "output": ["eventid", "clock", "name", "severity", "r_eventid"], "selectHosts": ["host"]})
        rids = [e["r_eventid"] for e in evs if e["r_eventid"] != "0"]
        rec = {r["eventid"]: int(r["clock"]) for r in self.api.call(
            "event.get", {"eventids": rids, "output": ["eventid", "clock"]})} if rids else {}
        avisos = self.api.call("alert.get", {
            "actionids": self.acciones, "time_from": self.t0, "sortfield": "clock", "sortorder": "ASC",
            "output": ["eventid", "p_eventid", "clock", "status", "error"]}) if self.acciones else []
        for e in evs:
            d = self.eventos.setdefault(e["eventid"], {
                "host": e["hosts"][0]["host"] if e["hosts"] else "?", "nombre": e["name"],
                "sev": int(e["severity"]), "abre": int(e["clock"]), "cierra": None,
                "aviso": None, "aviso_cierre": None})
            d["cierra"] = rec.get(e["r_eventid"])
        for a in avisos:
            problema = a["p_eventid"] if a["p_eventid"] != "0" else a["eventid"]
            d = self.eventos.get(problema)
            if d is None:
                continue
            campo = "aviso_cierre" if a["p_eventid"] != "0" else "aviso"
            if d[campo] is None or d[campo]["status"] != "1":  # el primero; el recordatorio no cuenta
                d[campo] = {"clock": int(a["clock"]), "status": a["status"], "error": a["error"]}
        self._novedades()

    def _rel(self, clock: int, desde_restauracion: bool = False) -> str:
        base = self.t_restaura if desde_restauracion and self.t_restaura else self.t0
        return f"+{_mmss(clock - base)}" + (" desde la restauración" if desde_restauracion else "")

    def _novedades(self) -> None:
        for eid, d in sorted(self.eventos.items(), key=lambda x: x[1]["abre"]):
            for clave, texto in (
                    ("abre", lambda: f"PROBLEMA [{SEVERIDAD[d['sev']]}] {d['nombre']}  ({self._rel(d['abre'])})"),
                    ("aviso", lambda: f"  Telegram: aviso {ESTADO_AVISO[d['aviso']['status']]}  "
                                      f"({self._rel(d['aviso']['clock'])}) {d['aviso']['error']}"),
                    ("cierra", lambda: f"RESUELTO  {d['nombre']}  ({self._rel(d['cierra'], True)})"),
                    ("aviso_cierre", lambda: f"  Telegram: aviso de resuelto "
                                             f"{ESTADO_AVISO[d['aviso_cierre']['status']]}  "
                                             f"({self._rel(d['aviso_cierre']['clock'], True)}) "
                                             f"{d['aviso_cierre']['error']}")):
                valor = d[clave]
                estado = valor["status"] if isinstance(valor, dict) else None
                if valor is not None and (eid, clave, estado) not in self._vistos and estado != "0":
                    self._vistos.add((eid, clave, estado))
                    self.log(f"  {time.strftime('%H:%M:%S')}  {texto()}")

    def todos_resueltos(self) -> bool:
        return bool(self.eventos) and all(
            d["cierra"] and (d["aviso"] is None or (d["aviso_cierre"] and d["aviso_cierre"]["status"] != "0"))
            for d in self.eventos.values())


def _esperar(seg: _Seguimiento, hasta: float, listo, log, enter: bool = False) -> None:
    """Consulta Zabbix cada POLL s hasta que listo() sea verdadero, se cumpla el plazo o,
    si enter=True, se presione Enter."""
    ultimo = 0.0
    while time.time() < hasta:
        try:
            seg.actualizar()
        except Exception as exc:  # Zabbix reiniciándose: se reintenta
            log(f"  (error consultando Zabbix: {exc})")
        if listo():
            return
        if time.time() - ultimo > 60:
            ultimo = time.time()
            log(f"  {time.strftime('%H:%M:%S')}  esperando... (+{_mmss(time.time() - seg.t0)})"
                + ("  Enter para restaurar ya" if enter else ""))
        if enter and sys.stdin.isatty():
            if select.select([sys.stdin], [], [], POLL)[0]:
                sys.stdin.readline()
                return
        else:
            time.sleep(POLL)
    log("  se cumplió el tiempo máximo de espera")


def _resumen(n: int, seg: _Seguimiento, extra: str, log) -> None:
    p = PRUEBAS[n]
    log(f"\n=== Resumen · Prueba {n} · {p['titulo']} ===")
    log(f"  Falla aplicada {time.strftime('%H:%M:%S', time.localtime(seg.t0))}"
        + (f" · restaurado {time.strftime('%H:%M:%S', time.localtime(seg.t_restaura))}"
           if seg.t_restaura else "") + (f" · {extra}" if extra else ""))
    log(f"  {'Gravedad':<11} {'Problema':<52} {'Abre':>6} {'Telegram':>14} {'Cierra':>7} {'Telegram':>14}")
    for d in sorted(seg.eventos.values(), key=lambda x: x["abre"]):
        def tg(a, base):
            return "—" if a is None else f"{_mmss(a['clock'] - base)} {ESTADO_AVISO[a['status']]}"
        base_cierre = seg.t_restaura or seg.t0
        log(f"  {SEVERIDAD[d['sev']]:<11} {d['nombre'][:52]:<52} {_mmss(d['abre'] - seg.t0):>6} "
            f"{tg(d['aviso'], seg.t0):>14} {_mmss(d['cierra'] - base_cierre if d['cierra'] else None):>7} "
            f"{tg(d['aviso_cierre'], base_cierre):>14}")
    evs = list(seg.eventos.values())
    if not evs:
        log("  No se abrió ningún problema.")
        return
    abre = [d["abre"] - seg.t0 for d in evs]
    avisos = [d for d in evs if d["aviso"]]
    fallidos = [d for d in evs if (d["aviso"] and d["aviso"]["status"] == "2")
                or (d["aviso_cierre"] and d["aviso_cierre"]["status"] == "2")]
    cierres = [d["cierra"] - seg.t_restaura for d in evs if d["cierra"] and seg.t_restaura]
    log(f"\n  {len(evs)} alerta(s) ({', '.join(sorted({SEVERIDAD[d['sev']] for d in evs}))}), abiertas entre "
        f"{_mmss(min(abre))} y {_mmss(max(abre))} min tras la falla.")
    if avisos:
        primero = min(d["aviso"]["clock"] for d in avisos) - seg.t0
        log(f"  {len(avisos)} aviso(s) por Telegram; el primero a los {primero} s de la falla.")
    if cierres:
        log(f"  Cierre automático entre {_mmss(min(cierres))} y {_mmss(max(cierres))} min tras restaurar"
            + (f" ({len(cierres)}/{len(evs)} cerradas)." if len(cierres) < len(evs) else "."))
    if fallidos:
        log(f"  ATENCIÓN: {len(fallidos)} aviso(s) de Telegram fallaron (ver Reports → Action log).")


def correr(inv: dict, api, n: int, log=print) -> None:
    if n not in PRUEBAS:
        raise SystemExit(f"Prueba desconocida: {n}. Disponibles: {', '.join(map(str, PRUEBAS))}")
    p = PRUEBAS[n]
    estados = {k: c["State"] for k, c in lab._contenedores().items()}
    equipos = equipos_de(p)
    abajo = [h for h in equipos if estados.get(h) != "running"]
    if abajo:
        raise SystemExit(f"{', '.join(abajo)} no está en línea. Primero: bin/lagunitas lab levantar")
    log(f"=== Prueba {n} · {p['titulo']} ===")

    observados = equipos + (lab.descendientes(inv, p["equipo"]) if "equipo" in p else [])
    t0 = time.time()
    seg = _Seguimiento(api, t0, observados, log)
    restaurado = False

    def restaurar() -> None:
        nonlocal restaurado
        if restaurado:
            return
        restaurado = True
        seg.t_restaura = time.time()
        restaurar(inv, p)
        log(f"  {time.strftime('%H:%M:%S')}  " + (
            "valores normales restaurados" if "escenarios" in p else
            f"latencia de {p['latencia']} quitada" if "latencia" in p else
            f"{p['equipo']} y sus dependientes levantados"))

    extra = ""
    avisado = lambda: any(d["aviso"] and d["aviso"]["status"] != "0" for d in seg.eventos.values())
    try:
        if "escenarios" in p:
            aplicar(inv, p)
            for h, esc in p["escenarios"]:
                log(f"  {time.strftime('%H:%M:%S')}  escenario '{esc}' aplicado en {h}")
            log(f"  Los triggers usan promedios de 10 y 15 min: las alertas tardan entre 6 y 11 min.")
            _esperar(seg, t0 + p["espera"], lambda: False, log, enter=True)
        elif "latencia" in p:
            aplicar(inv, p)
            extra = f"{lab.LATENCIA_PRUEBA} ms de retardo en {p['latencia']}"
            log(f"  {time.strftime('%H:%M:%S')}  {extra}. El trigger usa el promedio de 5 min: ~3 min.")
            _esperar(seg, t0 + p["espera"], avisado, log)
        else:
            caidos = lab._afectados(inv, p["equipo"], False)
            aplicar(inv, p)
            extra = f"{len(caidos)} equipos detenidos"
            log(f"  {time.strftime('%H:%M:%S')}  {p['equipo']} detenido ({extra})")
            _esperar(seg, t0 + p["espera"], avisado, log)
            if avisado():
                log(f"  observando {OBSERVAR_TRAS_ALERTA} s más para confirmar que no se abre ninguna otra alerta...")
                _esperar(seg, time.time() + OBSERVAR_TRAS_ALERTA, lambda: False, log)
        restaurar()
        _esperar(seg, seg.t_restaura + p["cierre"], seg.todos_resueltos, log)
    except KeyboardInterrupt:
        log("\n  interrumpida: restaurando...")
        restaurar()
    _resumen(n, seg, extra, log)
