"""Simulador del laboratorio: un contenedor Alpine por equipo operativo del inventario.

Cada contenedor solo responde ICMP en su IP fija de la red Docker 'lagunitas_net'.
Se crean con restart=unless-stopped (sobreviven a reinicios de Colima/Docker) y
sin --rm, así que simular una caída es 'docker stop' y recuperarla 'docker start'.
"""
from __future__ import annotations

import ipaddress
import json
import subprocess

RED = "lagunitas_net"
SUBRED = "10.50.0.0/24"
IMAGEN = "alpine:3.20"
LABEL = "ar.lagunitas.lab=1"


def _docker(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=check)


def _en_subred(ip: str) -> bool:
    return ipaddress.ip_address(ip) in ipaddress.ip_network(SUBRED)


def simulables(inv: dict, todos: bool = False) -> list[dict]:
    """Elementos que se simulan con contenedor (los que tienen IP de la red de LAB)."""
    return [e for e in inv["elementos"]
            if _en_subred(str(e["ip"])) and (todos or e["estado"] == "operativo")]


def _contenedores() -> dict[str, dict]:
    out = _docker("ps", "-a", "--format", "{{json .}}").stdout.splitlines()
    res = {}
    for line in out:
        c = json.loads(line)
        res[c["Names"]] = c
    return res


def ensure_red(log=print) -> None:
    if _docker("network", "inspect", RED, check=False).returncode != 0:
        _docker("network", "create", "--subnet", SUBRED, RED)
        log(f"  red {RED} ({SUBRED}) creada")


def levantar(inv: dict, log=print) -> None:
    ensure_red(log)
    existentes = _contenedores()
    deseados = {e["host"]: e for e in simulables(inv)}
    for nombre, e in deseados.items():
        c = existentes.get(nombre)
        if c and LABEL.split("=")[0] not in c.get("Labels", ""):
            _docker("rm", "-f", nombre)  # contenedor de la versión v1 (--rm, sin restart)
            c = None
        if c is None:
            _docker("run", "-d", "--name", nombre, "--hostname", nombre, "--network", RED,
                    "--ip", str(e["ip"]), "--restart", "unless-stopped", "--label", LABEL,
                    "--label", f"ar.lagunitas.rol={e['rol']}", "--memory", "16m", IMAGEN,
                    "sleep", "infinity")
            log(f"  creado     {nombre:<26} {e['ip']}")
        elif not c["State"] == "running":
            _docker("start", nombre)
            log(f"  iniciado   {nombre:<26} {e['ip']}")
    # Equipos que dejaron de estar operativos en el inventario.
    for nombre, c in existentes.items():
        if LABEL.split("=")[0] in c.get("Labels", "") and nombre not in deseados:
            _docker("rm", "-f", nombre)
            log(f"  eliminado  {nombre} (ya no está operativo en el inventario)")
    log(f"  {len(deseados)} equipos simulados en {RED}")


def apagar(log=print) -> None:
    for nombre, c in _contenedores().items():
        if LABEL.split("=")[0] in c.get("Labels", "") and c["State"] == "running":
            _docker("stop", "-t", "1", nombre)
            log(f"  detenido   {nombre}")


def descendientes(inv: dict, nombre: str) -> list[str]:
    """Equipos que dependen (directa o indirectamente) del dado, según el inventario."""
    hijos: dict[str, list[str]] = {}
    for e in inv["elementos"]:
        if e.get("padre"):
            hijos.setdefault(e["padre"], []).append(e["host"])
    out, pila = [], list(hijos.get(nombre, []))
    while pila:
        h = pila.pop(0)
        if h not in out:
            out.append(h)
            pila.extend(hijos.get(h, []))
    return out


def _afectados(inv: dict, nombre: str, solo: bool) -> list[str]:
    if nombre not in inv["por_host"]:
        raise SystemExit(f"'{nombre}' no está en el inventario")
    existentes = _contenedores()
    # En la red real, si cae un equipo sus descendientes pierden el camino: en el LAB
    # se simula deteniendo también sus contenedores (salvo --solo).
    return [h for h in [nombre] + ([] if solo else descendientes(inv, nombre)) if h in existentes]


def caida(inv: dict, nombre: str, solo: bool = False, log=print) -> None:
    afectados = _afectados(inv, nombre, solo)
    for h in afectados:
        _docker("stop", "-t", "1", h)
    log(f"  {nombre} detenido" + (f" (+{len(afectados) - 1} equipos aguas abajo sin camino: "
                                  f"{', '.join(afectados[1:])})" if len(afectados) > 1 else ""))
    log("  Zabbix lo detecta en ~90 s: una sola alerta (la de la causa raíz); los equipos aguas "
        "abajo quedan 'Sin servicio' sin generar alertas propias.")


def recuperar(inv: dict, nombre: str, solo: bool = False, log=print) -> None:
    afectados = _afectados(inv, nombre, solo)
    for h in afectados:
        _docker("start", h)
    log(f"  {', '.join(afectados)} iniciado(s): el problema se resuelve solo en ~30-60 s")


def estado(inv: dict, log=print) -> None:
    existentes = _contenedores()
    for e in simulables(inv, todos=True):
        c = existentes.get(e["host"])
        cont = c["State"] if c else "sin contenedor"
        log(f"  {e['host']:<26} {e['ip']:<12} inventario={e['estado']:<15} contenedor={cont}")
