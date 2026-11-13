"""Menú interactivo de pruebas del LAB: dispara y deshace todas las fallas simuladas (caídas,
escenarios SNMP, latencia y las pruebas de validación documentadas) y muestra en vivo los
problemas que abre Zabbix y los avisos que salen por Telegram.

Interfaz de terminal con curses: se navega con las flechas y el panel inferior se refresca solo.
"""
from __future__ import annotations

import curses
import sys
import threading
import time

from . import lab, validacion
from .model import ACCION_DEGRADACION, ACCION_NOMBRE, SITIO_GRUPO
from .validacion import ESTADO_AVISO, PRUEBAS, SEVERIDAD

REFRESCO_ZABBIX = 10  # segundos entre consultas de problemas y avisos
REFRESCO_DOCKER = 3   # segundos entre lecturas del estado de los contenedores
REFRESCO_FALLAS = 30  # segundos entre lecturas de las marcas de escenario y latencia
AVISOS_RECIENTES = 30 * 60
TECLAS = ["↑↓ mover   Enter tirar abajo/levantar   s ídem solo ese equipo   e escenario SNMP   "
          "l latencia", "1-4 prueba documentada (activar/deshacer)   t restaurar todo   q salir"]


def _problemas(api) -> list[dict]:
    """Problemas abiertos del grupo de la red, con el host que los origina."""
    from .hosts import ensure_hostgroup
    probs = api.call("problem.get", {"groupids": [ensure_hostgroup(api, SITIO_GRUPO)],
                                     "output": ["objectid", "name", "severity", "clock"],
                                     "recent": False, "sortfield": ["eventid"], "sortorder": "DESC"})
    if not probs:
        return []
    trig = api.call("trigger.get", {"triggerids": list({p["objectid"] for p in probs}),
                                    "output": ["triggerid"], "selectHosts": ["host"]})
    hosts = {t["triggerid"]: t["hosts"][0]["host"] for t in trig if t["hosts"]}
    return [dict(p, host=hosts.get(p["objectid"], "?")) for p in probs]


def _avisos(api) -> list[dict]:
    """Avisos de Telegram (y demás medios) de las acciones de la red en la última media hora."""
    acciones = [a["actionid"] for a in api.call("action.get", {
        "filter": {"name": [ACCION_NOMBRE, ACCION_DEGRADACION]}, "output": ["actionid"]})]
    if not acciones:
        return []
    return api.call("alert.get", {"actionids": acciones, "time_from": int(time.time()) - AVISOS_RECIENTES,
                                  "output": ["clock", "status", "subject", "error"],
                                  "sortfield": "clock", "sortorder": "DESC", "limit": 10})


def _hace(segundos: int) -> str:
    d, resto = divmod(segundos, 86400)
    h, resto = divmod(resto, 3600)
    m, s = divmod(resto, 60)
    return f"{d} d {h} h" if d else f"{h} h {m} min" if h else f"{m} min {s:02d} s"


class _Zabbix(threading.Thread):
    """Consulta problemas y avisos en segundo plano para no trabar la interfaz."""

    def __init__(self, api):
        super().__init__(daemon=True)
        self.api, self.problemas, self.avisos, self.error, self.hora = api, [], [], None, None
        self.ya = threading.Event()

    def run(self) -> None:
        while True:
            try:
                self.problemas, self.avisos, self.error = _problemas(self.api), _avisos(self.api), None
            except Exception as exc:  # Zabbix reiniciándose: se reintenta en el próximo ciclo
                self.error = str(exc)
            self.hora = time.strftime("%H:%M:%S")
            self.ya.wait(REFRESCO_ZABBIX)
            self.ya.clear()


class _Menu:
    def __init__(self, scr, inv: dict, equipos: list[dict], api):
        self.scr, self.inv, self.equipos = scr, inv, equipos
        self.sel, self.estados, self.fallas, self.leido, self.leido_fallas = 0, {}, {}, 0.0, 0.0
        self.mensaje = "Elegí un equipo con las flechas o una prueba documentada con 1-4."
        self.zbx = _Zabbix(api) if api else None
        if self.zbx:
            self.zbx.start()

    # ------------------------------------------------------------ helpers
    def _escribir(self, y: int, x: int, texto: str, attr: int = 0) -> None:
        alto, ancho = self.scr.getmaxyx()
        if 0 <= y < alto and x < ancho:
            try:
                self.scr.addnstr(y, x, texto, ancho - x - 1, attr)
            except curses.error:
                pass

    def _leer(self, forzar: bool = False) -> None:
        if forzar or time.time() - self.leido > REFRESCO_DOCKER:
            self.estados = {n: c["State"] for n, c in lab._contenedores().items()}
            self.leido = time.time()
        if forzar or time.time() - self.leido_fallas > REFRESCO_FALLAS:
            self.fallas = lab.fallas([e["host"] for e in self.equipos if self.estados.get(e["host"]) == "running"])
            self.leido_fallas = time.time()

    def _arrastra(self, host: str) -> list[str]:
        return [h for h in lab.descendientes(self.inv, host) if h in self.estados]

    def caidos(self) -> list[str]:
        return [e["host"] for e in self.equipos if self.estados.get(e["host"]) != "running"]

    def con_falla(self) -> list[str]:
        return [h for h, f in self.fallas.items() if f["latencia"] or f["escenario"]]

    def _falla(self, host: str) -> str:
        f = self.fallas.get(host) or {}
        partes = ([f["escenario"]] if f.get("escenario") else []) + \
                 ([f"+{f['latencia']} ms"] if f.get("latencia") else [])
        return " ".join(partes)

    def _hecho(self) -> None:
        self._leer(forzar=True)
        if self.zbx:
            self.zbx.ya.set()  # consultar ya, sin esperar el próximo ciclo

    def _trabajando(self, texto: str) -> None:
        self.mensaje = texto
        self.dibujar()

    # ------------------------------------------------------------ dibujo
    def dibujar(self) -> None:
        s, alto = self.scr, self.scr.getmaxyx()[0]
        s.erase()
        verde, rojo, gris, amarillo = (curses.color_pair(i) for i in (1, 2, 3, 4))
        self._escribir(0, 1, "Pruebas de validación — Red Las Lagunitas (LAB)", curses.A_BOLD)
        for i, t in enumerate(TECLAS):
            self._escribir(1 + i, 1, t, gris)
        x = 1
        for n, p in PRUEBAS.items():
            on = validacion.activa(p, self.estados, self.fallas)
            texto = f" {n} {p['titulo']}{' ●' if on else ''} "
            self._escribir(4, x, texto, (amarillo | curses.A_REVERSE) if on else curses.A_BOLD)
            x += len(texto) + 1
        self._escribir(6, 1, f"   {'Equipo':<24} {'IP':<12} {'Estado':<9} {'Falla simulada':<16} Arrastra",
                       curses.A_UNDERLINE)
        afectados = set(self._arrastra(self.equipos[self.sel]["host"]))
        for i, e in enumerate(self.equipos):
            y = 7 + i
            arriba = self.estados.get(e["host"]) == "running"
            elegido = i == self.sel
            marca = "▶" if elegido else "↳" if e["host"] in afectados else " "
            attr = curses.A_REVERSE if elegido else 0
            fila = f" {marca} {e['host']:<24} {e['ip']:<12} "
            self._escribir(y, 1, fila, attr)
            x = 1 + len(fila)
            self._escribir(y, x, f"{'en línea' if arriba else 'CAÍDO':<9} ",
                           attr | (verde if arriba else rojo | curses.A_BOLD))
            self._escribir(y, x + 10, f"{self._falla(e['host']):<16} ", attr | amarillo | curses.A_BOLD)
            self._escribir(y, x + 27, str(len(self._arrastra(e["host"]))), attr)
        y = 8 + len(self.equipos)
        self._escribir(y, 1, self.mensaje, curses.A_BOLD)
        y += 2
        if not self.zbx:
            self._escribir(y, 1, "Zabbix: sin conexión a la API (revisá .env); no se muestran problemas ni avisos.", gris)
            s.refresh()
            return
        z = self.zbx
        if not z.hora:
            self._escribir(y, 1, "Consultando Zabbix...", gris)
            s.refresh()
            return
        if z.error:
            self._escribir(y, 1, f"error consultando Zabbix: {z.error}", rojo)
            y += 1
        resto = max(alto - y - 3, 2)
        n_prob = min(len(z.problemas), max(resto - min(len(z.avisos), resto // 2), 1))
        self._escribir(y, 1, f"Problemas abiertos en Zabbix: {len(z.problemas)}   (actualizado {z.hora})",
                       curses.A_UNDERLINE)
        for p in z.problemas[:n_prob]:
            y += 1
            sev = int(p["severity"])
            self._escribir(y, 3, f"{SEVERIDAD[sev]:<11}", rojo if sev >= 4 else amarillo if sev >= 2 else 0)
            self._escribir(y, 15, f"{p['host']:<22} {p['name']}  (hace {_hace(int(time.time()) - int(p['clock']))})")
        if len(z.problemas) > n_prob:
            y += 1
            self._escribir(y, 3, f"… y {len(z.problemas) - n_prob} más", gris)
        y += 2
        self._escribir(y, 1, "Avisos de Telegram (última media hora)", curses.A_UNDERLINE)
        if not z.avisos:
            self._escribir(y + 1, 3, "ninguno", gris)
        for a in z.avisos:
            y += 1
            if y >= alto - 1:
                break
            st = ESTADO_AVISO[a["status"]]
            self._escribir(y, 3, f"{time.strftime('%H:%M:%S', time.localtime(int(a['clock'])))}  {st:<9}",
                           rojo if a["status"] == "2" else verde if a["status"] == "1" else gris)
            self._escribir(y, 25, a["subject"] + (f"  ({a['error'][:40]})" if a["error"] else ""))
        s.refresh()

    # ------------------------------------------------------------ acciones
    def _caida(self, solo: bool) -> None:
        host = self.equipos[self.sel]["host"]
        caer = self.estados.get(host) == "running"
        n = 0 if solo else len(self._arrastra(host))
        self._trabajando(f"{'Tirando abajo' if caer else 'Levantando'} {host}"
                         + (f" y {n} equipos aguas abajo" if n else "") + "...")
        (lab.caida if caer else lab.recuperar)(self.inv, host, solo, log=lambda *_: None)
        self._hecho()
        self.mensaje = (f"{host} caído" + (f" (+{n} sin camino)" if n else "")
                        + ": Zabbix abre el problema en ~90 s." if caer else
                        f"{host} levantado: el problema se resuelve en ~30-60 s.")

    def _elegir(self, pregunta: str, opciones: list[str]) -> str | None:
        """Muestra opciones numeradas en la línea de mensaje y espera un número (otra tecla cancela)."""
        self.mensaje = pregunta + "   " + "   ".join(f"{i} {o}" for i, o in enumerate(opciones))
        self.dibujar()
        self.scr.timeout(-1)
        k = self.scr.getch()
        self.scr.timeout(1000)
        if ord("0") <= k < ord("0") + min(len(opciones), 10):
            return opciones[k - ord("0")]
        self.mensaje = "Cancelado."
        return None

    def _escenario(self) -> None:
        host = self.equipos[self.sel]["host"]
        perfil = lab.perfil_simulado(self.inv["por_host"][host])
        if perfil == "icmp":
            self.mensaje = f"{host} solo responde ping: no tiene agente SNMP simulado (probá con l, latencia)."
            return
        if self.estados.get(host) != "running":
            self.mensaje = f"{host} está caído: levantalo primero."
            return
        esc = self._elegir(f"Escenario para {host}:", ["normal"] + [n for n, (perfiles, _) in lab.ESCENARIOS.items()
                                                                    if perfil in perfiles])
        if esc is None:
            return
        self._trabajando(f"Aplicando '{esc}' en {host}...")
        lab.escenario(self.inv, host, esc, log=lambda *_: None)
        self._hecho()
        self.mensaje = (f"{host}: valores normales restaurados; los problemas se cierran en minutos."
                        if esc == "normal" else
                        f"{host}: '{esc}' aplicado. Las alertas tardan 6-15 min (promedios de 10 y 15 min).")

    def _latencia(self) -> None:
        host = self.equipos[self.sel]["host"]
        if self.estados.get(host) != "running":
            self.mensaje = f"{host} está caído: levantalo primero."
            return
        poner = not (self.fallas.get(host) or {}).get("latencia")
        self._trabajando(f"{'Agregando' if poner else 'Quitando'} latencia en {host}...")
        lab.latencia(self.inv, host, lab.LATENCIA_PRUEBA if poner else 0, log=lambda *_: None)
        self._hecho()
        self.mensaje = (f"{host}: +{lab.LATENCIA_PRUEBA} ms. «Latencia alta» se abre en ~3 min (promedio de 5 min)."
                        if poner else f"{host}: latencia normal; el problema se cierra en ~3 min.")

    def _prueba(self, n: int) -> None:
        p = PRUEBAS[n]
        on = validacion.activa(p, self.estados, self.fallas)
        if not on and any(self.estados.get(h) != "running" for h in validacion.equipos_de(p)):
            self.mensaje = f"Prueba {n}: hay equipos de la prueba caídos; levantalos primero (t)."
            return
        self._trabajando(f"Prueba {n} · {p['titulo']}: {'deshaciendo' if on else 'activando'}...")
        (validacion.restaurar if on else validacion.aplicar)(self.inv, p)
        self._hecho()
        if on:
            self.mensaje = f"Prueba {n} deshecha: mirá cómo se cierran los problemas y llegan los avisos de resuelto."
        else:
            espera = {1: "6-11 min", 2: "~90 s", 3: "~90 s", 4: "~3 min"}.get(n, "unos minutos")
            self.mensaje = f"Prueba {n} activa: la alerta llega en {espera}. Volvé a apretar {n} para deshacerla."

    def restaurar_todo(self) -> None:
        self._trabajando("Restaurando todo...")
        if self.caidos():
            lab.levantar(self.inv, log=lambda *_: None)
            self._leer(forzar=True)
        for host in self.con_falla():
            f = self.fallas[host]
            if f["latencia"]:
                lab.latencia(self.inv, host, 0, log=lambda *_: None)
            if f["escenario"]:
                lab.escenario(self.inv, host, "normal", log=lambda *_: None)
        self._hecho()
        self.mensaje = "Todo restaurado: equipos en línea, sin escenarios ni latencia."

    def bucle(self) -> None:
        """Atiende las teclas hasta salir; al salir ofrece restaurar lo que quedó caído o con falla."""
        while True:
            self._leer()
            self.dibujar()
            k = self.scr.getch()  # timeout de 1 s: sigue refrescando sin teclas
            if k in (curses.KEY_UP, ord("k")):
                self.sel = (self.sel - 1) % len(self.equipos)
            elif k in (curses.KEY_DOWN, ord("j")):
                self.sel = (self.sel + 1) % len(self.equipos)
            elif k in (curses.KEY_ENTER, 10, 13, ord(" ")):
                self._caida(solo=False)
            elif k in (ord("s"), ord("S")):
                self._caida(solo=True)
            elif k in (ord("e"), ord("E")):
                self._escenario()
            elif k in (ord("l"), ord("L")):
                self._latencia()
            elif ord("1") <= k <= ord("9") and k - ord("0") in PRUEBAS:
                self._prueba(k - ord("0"))
            elif k in (ord("t"), ord("T")):
                self.restaurar_todo()
            elif k in (ord("q"), ord("Q")):
                self._leer(forzar=True)
                pendientes = len(self.caidos()) + len(self.con_falla())
                if not pendientes:
                    return
                self.mensaje = (f"Quedan {len(self.caidos())} equipos caídos y {len(self.con_falla())} con falla "
                                "simulada. ¿Restaurar todo antes de salir? (s/n)")
                self.dibujar()
                self.scr.timeout(-1)
                while (r := self.scr.getch()) not in (ord("s"), ord("S"), ord("n"), ord("N"), 10, 13):
                    pass
                if r not in (ord("n"), ord("N")):
                    self.restaurar_todo()
                return


def _iniciar(scr, inv: dict, equipos: list[dict], api) -> None:
    curses.curs_set(0)
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN, -1)
    curses.init_pair(2, curses.COLOR_RED, -1)
    curses.init_pair(3, 8 if curses.COLORS > 8 else curses.COLOR_WHITE, -1)
    curses.init_pair(4, curses.COLOR_YELLOW, -1)
    scr.keypad(True)
    scr.timeout(1000)
    _Menu(scr, inv, equipos, api).bucle()


def menu(inv: dict, api, log=print) -> None:
    if not sys.stdin.isatty():
        raise SystemExit("El menú de pruebas necesita una terminal interactiva.")
    equipos = [e for e in lab.simulables(inv) if e["host"] in lab._contenedores()]
    if not equipos:
        raise SystemExit("No hay equipos simulados. Primero: bin/lagunitas lab levantar")
    try:
        curses.wrapper(_iniciar, inv, equipos, api)
    except KeyboardInterrupt:
        pass
