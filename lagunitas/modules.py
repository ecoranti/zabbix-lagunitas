"""Registro y habilitación de los módulos propios del frontend (zabbix/modules/*)."""
from __future__ import annotations

import json

from .config import ROOT
from .zbx import ZabbixAPI

MODULES_DIR = ROOT / "zabbix" / "modules"


def ensure_modules(api: ZabbixAPI, log=print) -> None:
    """Equivale a Administration -> General -> Modules -> "Scan directory" + habilitar.

    Requiere que cada carpeta esté montada en /usr/share/zabbix/modules/<carpeta>
    del contenedor web (ver docker-compose.yml).
    """
    for manifest in sorted(MODULES_DIR.glob("*/manifest.json")):
        meta = json.loads(manifest.read_text(encoding="utf-8"))
        rel = f"modules/{manifest.parent.name}"
        found = api.call("module.get", {"filter": {"relative_path": [rel]}, "output": ["moduleid", "status"]})
        if found:
            if found[0]["status"] != "1":
                api.call("module.update", {"moduleid": found[0]["moduleid"], "status": 1})
            accion = "habilitado"
        else:
            api.call("module.create", {"id": meta["id"], "relative_path": rel, "status": 1})
            accion = "registrado y habilitado"
        log(f"  módulo '{meta['name']}' v{meta['version']}: {accion}")
