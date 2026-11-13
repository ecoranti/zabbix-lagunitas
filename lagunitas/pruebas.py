"""Menú interactivo de pruebas de validación del LAB: tirar abajo y levantar equipos
simulados y ver qué problemas abre Zabbix (causa raíz única, dependientes sin alerta).

Interfaz de terminal con curses: se navega con las flechas y los problemas abiertos
se refrescan solos en el panel inferior.
"""
from __future__ import annotations

import curses
import sys
import threading
import time

from . import lab
from .model import SITIO_GRUPO

SEVERIDAD = ["No clasif.", "Info", "Advertencia", "Media", "Alta", "Desastre"]
REFRESCO_ZABBIX = 10  # segundos entre consultas de problemas
REFRESCO_DOCKER = 3   # segundos entre lecturas del estado de los contenedores
TECLAS = ("↑↓ mover   Enter tirar abajo/levantar (con dependientes)   s solo ese equipo   "
          "t levantar todo   q salir")


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


def _hace(segundos: int) -> str:
    d, resto = divmod(segundos, 86400)
    h, resto = divmod(resto, 3600)
    m, s = divmod(resto, 60)
    return f"{d} d {h} h" if d else f"{h} h {m} min" if h else f"{m} min {s:02d} s"


class _Problemas(threading.Thread):
    """Consulta los problemas de Zabbix en segundo plano para no trabar la interfaz."""

    def __init__(self, api):
        super().__init__(daemon=True)
        self.api, self.lista, self.error, self.hora = api, [], None, None
        self.ya = threading.Event()

    def run(self) -> None:
        while True:
            try:
                self.lista, self.error = _problemas(self.api), None
            except Exception as exc:  # Zabbix reiniciándose: se reintenta en el próximo ciclo
                self.error = str(exc)
            self.hora = time.strftime("%H:%M:%S")
            self.ya.wait(REFRESCO_ZABBIX)
            self.ya.clear()


class _Menu:
    def __init__(self, scr, inv: dict, equipos: list[dict], api):
        self.scr, self.inv, self.equipos = scr, inv, equipos
        self.sel, self.estados, self.leido = 0, {}, 0.0
        self.mensaje = "Elegí un equipo con las flechas."
        self.zbx = _Problemas(api) if api else None
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

    def _leer_estados(self, forzar: bool = False) -> None:
        if forzar or time.time() - self.leido > REFRESCO_DOCKER:
            self.estados = {n: c["State"] for n, c in lab._contenedores().items()}
            self.leido = time.time()

    def _arrastra(self, host: str) -> list[str]:
        return [h for h in lab.descendientes(self.inv, host) if h in self.estados]

    def caidos(self) -> list[str]:
        return [e["host"] for e in self.equipos if self.estados.get(e["host"]) != "running"]

    # ------------------------------------------------------------ dibujo
    def dibujar(self) -> None:
        s, alto = self.scr, self.scr.getmaxyx()[0]
        s.erase()
        verde, rojo, gris = curses.color_pair(1), curses.color_pair(2), curses.color_pair(3)
        self._escribir(0, 1, "Pruebas de validación — Red Las Lagunitas (LAB)", curses.A_BOLD)
        self._escribir(1, 1, TECLAS, gris)
        self._escribir(3, 1, f"   {'Equipo':<26} {'IP':<12} {'Estado':<10} Arrastra", curses.A_UNDERLINE)
        afectados = set(self._arrastra(self.equipos[self.sel]["host"]))
        for i, e in enumerate(self.equipos):
            y = 4 + i
            arriba = self.estados.get(e["host"]) == "running"
            elegido = i == self.sel
            marca = "▶" if elegido else "↳" if e["host"] in afectados else " "
            fila = f" {marca} {e['host']:<26} {e['ip']:<12} "
            attr = curses.A_REVERSE if elegido else 0
            self._escribir(y, 1, fila, attr)
            self._escribir(y, 1 + len(fila), f"{'en línea' if arriba else 'CAÍDO':<10}",
                           attr | (verde if arriba else rojo | curses.A_BOLD))
            self._escribir(y, 12 + len(fila), str(len(self._arrastra(e["host"]))), attr)
        y = 5 + len(self.equipos)
        self._escribir(y, 1, self.mensaje, curses.A_BOLD)
        y += 2
        if not self.zbx:
            self._escribir(y, 1, "Zabbix: sin conexión a la API (revisá .env); no se muestran problemas.", gris)
        else:
            z = self.zbx
            titulo = (f"Problemas abiertos en Zabbix: {len(z.lista)}   (actualizado {z.hora}, "
                      f"cada {REFRESCO_ZABBIX} s)" if z.hora else "Problemas abiertos en Zabbix: consultando...")
            self._escribir(y, 1, titulo, curses.A_UNDERLINE)
            if z.error:
                y += 1
                self._escribir(y, 1, f"error: {z.error}", rojo)
            for p in z.lista:
                y += 1
                if y >= alto - 1:
                    self._escribir(alto - 1, 3, "…", gris)
                    break
                sev = int(p["severity"])
                self._escribir(y, 3, f"{SEVERIDAD[sev]:<11}", rojo if sev >= 4 else 0)
                self._escribir(y, 15, f"{p['host']:<22} {p['name']}  "
                                      f"(hace {_hace(int(time.time()) - int(p['clock']))})")
        s.refresh()

    # ------------------------------------------------------------ acciones
    def _accion(self, solo: bool) -> None:
        host = self.equipos[self.sel]["host"]
        caer = self.estados.get(host) == "running"
        n = 0 if solo else len(self._arrastra(host))
        self.mensaje = (f"{'Tirando abajo' if caer else 'Levantando'} {host}"
                        + (f" y {n} equipos aguas abajo" if n else "") + "...")
        self.dibujar()
        (lab.caida if caer else lab.recuperar)(self.inv, host, solo, log=lambda *_: None)
        self._leer_estados(forzar=True)
        self.mensaje = (f"{host} caído" + (f" (+{n} sin camino)" if n else "")
                        + ": Zabbix abre el problema en ~90 s." if caer else
                        f"{host} levantado: el problema se resuelve en ~30-60 s.")
        if self.zbx:
            self.zbx.ya.set()  # consultar ya, sin esperar el próximo ciclo

    def _levantar_todo(self) -> None:
        self.mensaje = "Levantando todos los equipos..."
        self.dibujar()
        lab.levantar(self.inv, log=lambda *_: None)
        self._leer_estados(forzar=True)
        self.mensaje = "Todos los equipos levantados."
        if self.zbx:
            self.zbx.ya.set()

    def bucle(self) -> bool:
        """Devuelve True si al salir hay que levantar los equipos caídos."""
        while True:
            self._leer_estados()
            self.dibujar()
            k = self.scr.getch()  # timeout de 1 s: sigue refrescando sin teclas
            if k in (curses.KEY_UP, ord("k")):
                self.sel = (self.sel - 1) % len(self.equipos)
            elif k in (curses.KEY_DOWN, ord("j")):
                self.sel = (self.sel + 1) % len(self.equipos)
            elif k in (curses.KEY_ENTER, 10, 13, ord(" ")):
                self._accion(solo=False)
            elif k in (ord("s"), ord("S")):
                self._accion(solo=True)
            elif k in (ord("t"), ord("T")):
                self._levantar_todo()
            elif k in (ord("q"), ord("Q")):
                if not self.caidos():
                    return False
                self.mensaje = f"Quedan {len(self.caidos())} equipos caídos. ¿Levantarlos antes de salir? (s/n)"
                self.dibujar()
                self.scr.timeout(-1)
                while (r := self.scr.getch()) not in (ord("s"), ord("S"), ord("n"), ord("N"), 10, 13):
                    pass
                return r not in (ord("n"), ord("N"))


def _iniciar(scr, inv: dict, equipos: list[dict], api) -> bool:
    curses.curs_set(0)
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN, -1)
    curses.init_pair(2, curses.COLOR_RED, -1)
    curses.init_pair(3, 8 if curses.COLORS > 8 else curses.COLOR_WHITE, -1)
    scr.keypad(True)
    scr.timeout(1000)
    return _Menu(scr, inv, equipos, api).bucle()


def menu(inv: dict, api, log=print) -> None:
    if not sys.stdin.isatty():
        raise SystemExit("El menú de pruebas necesita una terminal interactiva.")
    equipos = [e for e in lab.simulables(inv) if e["host"] in lab._contenedores()]
    if not equipos:
        raise SystemExit("No hay equipos simulados. Primero: bin/lagunitas lab levantar")
    try:
        levantar = curses.wrapper(_iniciar, inv, equipos, api)
    except KeyboardInterrupt:
        levantar = False
    if levantar:
        lab.levantar(inv, log)
