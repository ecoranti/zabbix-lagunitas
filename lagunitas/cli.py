"""Línea de comandos:  ./lagunitas <comando>   (o  python -m lagunitas <comando>)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, alerts, dashboards, hosts, lab, modules, services, templates, topology_map
from .config import InventoryError, ROOT, load_inventory, settings
from .model import SITIO_GRUPO, TEMPLATE_GRUPO
from .zbx import ZabbixAPI

PASOS = ["templates", "hosts", "dependencias", "servidor", "mapa", "servicios", "modulos", "dashboard",
         "alertas"]


def _api() -> ZabbixAPI:
    s = settings()
    return ZabbixAPI(s.url, s.token, s.user, s.password, s.verify_tls)


def _inventario(path: str | None) -> dict:
    s = settings()
    p = Path(path) if path else s.inventory
    try:
        return load_inventory(p if p.is_absolute() else ROOT / p)
    except InventoryError as exc:
        sys.exit(str(exc))


def cmd_aprovisionar(args) -> None:
    s, inv, api = settings(), _inventario(args.inventario), _api()
    pasos = args.solo or PASOS
    print(f"Zabbix {api.version()} — inventario '{inv.get('entorno')}' ({len(inv['elementos'])} equipos)")
    if args.migrar_v1:
        print("[migración v1]")
        hosts.migrar_legacy(api)
    groups = hosts.ensure_groups(api)
    if "templates" in pasos:
        print("[templates]")
        for nombre, r in templates.install_all(api).items():
            print(f"  {nombre}: {len(r['items'])} items")
    hostids: dict[str, str] = {}
    if "hosts" in pasos:
        print("[hosts]")
        hostids = hosts.ensure_hosts(api, inv, groups)
    if not hostids:
        hostids = {h["host"]: h["hostid"] for h in api.call("host.get", {
            "filter": {"host": [e["host"] for e in inv["elementos"]]}, "output": ["host"]})}
    caidas = hosts.caida_triggerids(api, inv, hostids)
    if "dependencias" in pasos:
        print("[dependencias]")
        hosts.ensure_dependencies(api, inv, caidas)
    if "servidor" in pasos:
        print("[servidor]")
        hosts.ensure_zabbix_server_host(api)
    sysmapid = slaid = raiz = None
    if "mapa" in pasos:
        print("[mapa]")
        sysmapid = topology_map.ensure_map(api, inv, hostids, caidas)
    if "servicios" in pasos:
        print("[servicios y SLA]")
        raiz = services.ensure_services(api, inv)
        slaid = services.ensure_sla(api, s.timezone)
    if "modulos" in pasos:
        print("[módulos del frontend]")
        modules.ensure_modules(api)
    if "dashboard" in pasos:
        print("[dashboard]")
        from .model import MAPA_NOMBRE, SERVICIO_RAIZ, SLA_NOMBRE
        sysmapid = sysmapid or api.call("map.get", {"filter": {"name": [MAPA_NOMBRE]}})[0]["sysmapid"]
        slaid = slaid or api.call("sla.get", {"filter": {"name": [SLA_NOMBRE]}})[0]["slaid"]
        raiz = raiz or api.call("service.get", {"filter": {"name": [SERVICIO_RAIZ]}})[0]["serviceid"]
        dashboards.ensure_dashboard(api, inv, hostids, groups, sysmapid, slaid, raiz)
    if "alertas" in pasos:
        print("[alertas]")
        alerts.ensure_alerting(api, groups)
    api.close()
    print("Listo.")


def cmd_verificar(args) -> None:
    """Chequeo de salud de la configuración (útil tras un despliegue)."""
    inv, api = _inventario(args.inventario), _api()
    ok = True
    print(f"Zabbix API {api.version()}")
    hs = api.call("host.get", {"groupids": [hosts.ensure_hostgroup(api, SITIO_GRUPO)],
                               "output": ["host", "status"], "selectInterfaces": ["available"]})
    en_zbx = {h["host"]: h for h in hs}
    faltan = [e["host"] for e in inv["elementos"] if e["host"] not in en_zbx]
    print(f"Hosts: {len(hs)} en Zabbix / {len(inv['elementos'])} en inventario"
          + (f"  FALTAN: {faltan}" if faltan else ""))
    ok &= not faltan
    malos = api.call("item.get", {"groupids": [hosts.ensure_hostgroup(api, SITIO_GRUPO)],
                                  "monitored": True, "filter": {"state": 1},
                                  "output": ["name", "error"], "selectHosts": ["host"]})
    print(f"Items no soportados: {len(malos)}")
    for i in malos[:20]:
        print(f"  - {i['hosts'][0]['host']}: {i['name']} -> {i['error'][:100]}")
    probs = api.call("problem.get", {"groupids": [hosts.ensure_hostgroup(api, SITIO_GRUPO)],
                                     "output": ["name", "severity"], "recent": False})
    print(f"Problemas abiertos: {len(probs)}")
    for p in probs[:20]:
        print(f"  - [{p['severity']}] {p['name']}")
    tpl = api.call("template.get", {"output": ["host"], "search": {"host": "Lagunitas"}})
    print(f"Templates del proyecto: {[t['host'] for t in tpl]}")
    api.close()
    sys.exit(0 if ok else 1)


def cmd_validar(args) -> None:
    """Valida el inventario sin conectarse a Zabbix y muestra un resumen."""
    inv = _inventario(args.inventario)
    from collections import Counter
    roles = Counter(e["rol"] for e in inv["elementos"])
    estados = Counter(e["estado"] for e in inv["elementos"])
    perfiles = Counter(p for e in inv["elementos"] for p in e["perfiles"])
    print(f"Inventario '{inv.get('entorno')}' válido: {len(inv['elementos'])} equipos")
    print("  roles:    " + ", ".join(f"{k}={v}" for k, v in roles.items()))
    print("  estados:  " + ", ".join(f"{k}={v}" for k, v in estados.items()))
    print("  perfiles: " + ", ".join(f"{k}={v}" for k, v in perfiles.items()))
    raices = [e["host"] for e in inv["elementos"] if not e.get("padre")]
    print(f"  equipos sin padre (raíces): {', '.join(raices)}")


def cmd_exportar(args) -> None:
    """Exporta templates y mapa a YAML (importables manualmente en otro Zabbix)."""
    api = _api()
    out = ROOT / "zabbix" / "export"
    out.mkdir(parents=True, exist_ok=True)
    tpls = api.call("template.get", {"output": ["templateid", "host"],
                                     "groupids": [api.call("templategroup.get", {
                                         "filter": {"name": [TEMPLATE_GRUPO]}})[0]["groupid"]]})
    for t in tpls:
        data = api.call("configuration.export", {"format": "yaml",
                                                 "options": {"templates": [t["templateid"]]}})
        f = out / f"template_{t['host'].replace(' ', '_').replace('-', '')}.yaml"
        f.write_text(data, encoding="utf-8")
        print(f"  {f.relative_to(ROOT)}")
    maps = api.call("map.get", {"search": {"name": "Las Lagunitas"}, "output": ["sysmapid"]})
    if maps:
        data = api.call("configuration.export", {"format": "yaml",
                                                 "options": {"maps": [m["sysmapid"] for m in maps]}})
        (out / "mapa_Las_Lagunitas.yaml").write_text(data, encoding="utf-8")
        print("  zabbix/export/mapa_Las_Lagunitas.yaml")
    api.close()


def cmd_lab(args) -> None:
    inv = _inventario(args.inventario)
    {"levantar": lambda: lab.levantar(inv), "apagar": lab.apagar,
     "estado": lambda: lab.estado(inv),
     "caida": lambda: lab.caida(inv, args.equipo, args.solo),
     "recuperar": lambda: lab.recuperar(inv, args.equipo, args.solo)}[args.accion]()


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="lagunitas", description=f"Monitoreo Red Las Lagunitas v{__version__}")
    p.add_argument("-i", "--inventario", help="archivo de inventario (por defecto LAGUNITAS_INVENTORY)")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("aprovisionar", help="crea/actualiza toda la configuración en Zabbix")
    a.add_argument("--solo", nargs="+", choices=PASOS, help="ejecutar solo algunos pasos")
    a.add_argument("--migrar-v1", action="store_true",
                   help="borra hosts/mapa/dashboard de la versión v1 antes de aprovisionar")
    a.set_defaults(func=cmd_aprovisionar)

    sub.add_parser("validar", help="valida el inventario (sin conectarse a Zabbix)").set_defaults(func=cmd_validar)
    sub.add_parser("verificar", help="chequeo de salud de la configuración").set_defaults(func=cmd_verificar)
    sub.add_parser("exportar", help="exporta templates y mapa a zabbix/export/").set_defaults(func=cmd_exportar)

    l = sub.add_parser("lab", help="simulador de la red en Docker (solo entorno LAB)")
    l.add_argument("accion", choices=["levantar", "apagar", "estado", "caida", "recuperar"])
    l.add_argument("equipo", nargs="?", help="nombre técnico del equipo (para caida/recuperar)")
    l.add_argument("--solo", action="store_true",
                   help="caida/recuperar: solo ese equipo, sin sus dependientes")
    l.set_defaults(func=cmd_lab)

    args = p.parse_args(argv)
    if getattr(args, "accion", None) in ("caida", "recuperar") and not args.equipo:
        p.error("indicá el equipo, ej: ./lagunitas lab caida Nodo_Kika")
    args.func(args)
