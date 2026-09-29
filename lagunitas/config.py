"""Carga de configuración (.env) y del inventario de la red, con validación."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from .model import ESTADOS, PERFILES, ROLES

ROOT = Path(__file__).resolve().parent.parent


def load_env(path: Path = ROOT / ".env") -> None:
    """Carga KEY=VALUE de un archivo .env sin pisar variables ya exportadas."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


@dataclass
class Settings:
    url: str
    token: str | None
    user: str | None
    password: str | None
    verify_tls: bool
    inventory: Path
    timezone: str


def settings() -> Settings:
    load_env()
    inventory = Path(os.environ.get("LAGUNITAS_INVENTORY", "config/inventory.lab.yaml"))
    if not inventory.is_absolute():
        inventory = ROOT / inventory
    return Settings(
        url=os.environ.get("ZABBIX_URL", "http://localhost:8090/api_jsonrpc.php"),
        token=os.environ.get("ZABBIX_API_TOKEN") or None,
        user=os.environ.get("ZABBIX_USER") or None,
        password=os.environ.get("ZABBIX_PASSWORD") or None,
        verify_tls=os.environ.get("ZABBIX_VERIFY_TLS", "true").lower() != "false",
        inventory=inventory,
        timezone=os.environ.get("PHP_TZ", "America/Argentina/Cordoba"),
    )


class InventoryError(ValueError):
    pass


def load_inventory(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    elementos = data.get("elementos") or []
    errores: list[str] = []
    hosts: dict[str, dict] = {}
    ips: dict[str, str] = {}

    for e in elementos:
        h = e.get("host")
        if not h or " " in h:
            errores.append(f"host inválido: {h!r}")
            continue
        if h in hosts:
            errores.append(f"host duplicado: {h}")
        hosts[h] = e
        e.setdefault("nombre", h)
        e.setdefault("padre", None)
        e.setdefault("perfiles", ["icmp"])
        e.setdefault("equipo", "")
        e.setdefault("macros", {})
        if e.get("rol") not in ROLES:
            errores.append(f"{h}: rol desconocido {e.get('rol')!r} (válidos: {', '.join(ROLES)})")
        if e.get("estado") not in ESTADOS:
            errores.append(f"{h}: estado desconocido {e.get('estado')!r} (válidos: {', '.join(ESTADOS)})")
        for p in e["perfiles"]:
            if p not in PERFILES:
                errores.append(f"{h}: perfil desconocido {p!r} (válidos: {', '.join(PERFILES)})")
        ip = str(e.get("ip", ""))
        if not ip:
            errores.append(f"{h}: falta ip")
        elif ip in ips:
            errores.append(f"{h}: ip {ip} repetida (ya usada por {ips[ip]})")
        ips[ip] = h
        if not (isinstance(e.get("mapa"), list) and len(e["mapa"]) == 2):
            errores.append(f"{h}: 'mapa' debe ser [x, y]")

    for h, e in hosts.items():
        padre = e.get("padre")
        if padre and padre not in hosts:
            errores.append(f"{h}: padre {padre!r} no existe en el inventario")
        # detección de ciclos padre -> hijo
        visto, actual = {h}, padre
        while actual:
            if actual in visto:
                errores.append(f"{h}: ciclo en la cadena de padres")
                break
            visto.add(actual)
            actual = hosts.get(actual, {}).get("padre")

    for a, b in data.get("enlaces_extra") or []:
        if a not in hosts or b not in hosts:
            errores.append(f"enlace_extra {a}-{b}: elemento inexistente")

    if errores:
        raise InventoryError("Inventario inválido:\n  - " + "\n  - ".join(errores))

    data["elementos"] = elementos
    data["por_host"] = hosts
    return data
