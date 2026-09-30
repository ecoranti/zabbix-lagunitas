"""Capturas reales del entorno para el informe (Playwright + Google Chrome instalado).

Uso (entorno aparte, no es dependencia del proyecto):
    python3 -m venv /tmp/pw && /tmp/pw/bin/pip install playwright
    /tmp/pw/bin/python scripts/capturas-informe.py [dash modal mapa reporte config problemas caida]

Entra a Zabbix con ZABBIX_USER/ZABBIX_PASSWORD de .env y guarda las capturas en
docs/informe/capturas/ (fuera de git). Los hostid corresponden al laboratorio.
"""
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs/informe/capturas"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://localhost:8090"
env = dict(l.split("=", 1) for l in (REPO / ".env").read_text().splitlines() if "=" in l and not l.startswith("#"))
USER, PASS = env["ZABBIX_USER"].strip(), env["ZABBIX_PASSWORD"].strip()

LIMPIO = """
.filter-space, .msg-global-footer, output.msg-global, .msg-bad, .msg-good, .msg-warning { display: none !important; }
.lg-modal { max-height: none !important; height: auto !important; }
.lg-m-body { overflow: visible !important; max-height: none !important; }
.lg-modal-overlay { position: absolute !important; align-items: flex-start !important; overflow: visible !important; }
"""


def ajustar_alto(page, sel=".wrapper", ancho=1600, minimo=900):
    h = page.evaluate(f"""() => {{ const e = document.querySelector('{sel}') || document.body;
        return Math.max(e.scrollHeight, document.body.scrollHeight); }}""")
    page.set_viewport_size({"width": ancho, "height": max(minimo, int(h) + 20)})
    time.sleep(1.5)


def ir(page, url, espera=6):
    page.goto(BASE + url, wait_until="networkidle")
    page.add_style_tag(content=LIMPIO)
    time.sleep(espera)


def foto(page, nombre, sel="main"):
    el = page.query_selector(sel)
    ruta = OUT / f"{nombre}.jpg"
    (el or page).screenshot(path=str(ruta), type="jpeg", quality=88)
    print("  ", ruta.name)


def dashboard(page, n, nombre, ancho=1600, extra=None):
    page.set_viewport_size({"width": ancho, "height": 1000})
    ir(page, f"/zabbix.php?action=dashboard.view&dashboardid=404&page={n}&from=now-6h&to=now")
    if extra:
        extra(page)
    ajustar_alto(page, ancho=ancho)
    page.add_style_tag(content=LIMPIO)
    time.sleep(3)
    foto(page, nombre)


def modal(page, hostid, tabs, prefijo):
    page.set_viewport_size({"width": 1600, "height": 1000})
    ir(page, "/zabbix.php?action=dashboard.view&dashboardid=404&page=2&from=now-6h&to=now")
    page.click(f'.lg-row[data-hostid="{hostid}"]')
    page.wait_for_selector(".lg-modal [data-lg-tab]", timeout=20000)
    time.sleep(2)
    for tab in tabs:
        page.click(f'.lg-modal [data-lg-tab="{tab}"]')
        time.sleep(3)
        page.set_viewport_size({"width": 1600, "height": 1000})
        h = page.evaluate("document.querySelector('.lg-modal').scrollHeight")
        page.set_viewport_size({"width": 1600, "height": int(h) + 120})
        time.sleep(1.5)
        foto(page, f"{prefijo}-{tab}", ".lg-modal")


def reporte(page, url, nombre):
    page.set_viewport_size({"width": 1600, "height": 1000})
    ir(page, url, espera=4)
    h = page.evaluate("document.querySelector('.lr-page').scrollHeight")
    page.set_viewport_size({"width": 1600, "height": int(h) + 200})
    time.sleep(2)
    foto(page, nombre, ".lr-page")


def main(solo=None):
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        ctx = b.new_context(viewport={"width": 1600, "height": 1000}, device_scale_factor=1.5, locale="es-AR")
        page = ctx.new_page()
        page.goto(BASE + "/index.php")
        page.fill("#name", USER)
        page.fill("#password", PASS)
        page.click("#enter")
        page.wait_for_load_state("networkidle")

        pasos = {
            "dash": lambda: [dashboard(page, 1, "01-dashboard-estado-red"), dashboard(page, 2, "02-dashboard-equipos"),
                             dashboard(page, 3, "03-dashboard-detalle-equipo"), dashboard(page, 4, "04-dashboard-ap-unifi"),
                             dashboard(page, 5, "05-dashboard-sla")],
            "modal": lambda: [modal(page, 10720, ["resumen", "radio", "estaciones", "interfaces", "rendimiento", "dependencias"], "10-modal-torre"),
                              modal(page, 10749, ["router", "interfaces"], "11-modal-gateway"),
                              modal(page, 10746, ["resumen", "unifi", "rendimiento"], "12-modal-ap")],
            "mapa": lambda: (page.set_viewport_size({"width": 1600, "height": 1000}),
                             ir(page, "/zabbix.php?action=map.view&sysmapid=3"), ajustar_alto(page),
                             foto(page, "20-mapa-topologia")),
            "reporte": lambda: [reporte(page, "/zabbix.php?action=lagunitas.reporte&periodo=7d", "30-reporte-disponibilidad"),
                                reporte(page, "/zabbix.php?action=lagunitas.reporte.equipo&periodo=7d&hostid=10720", "31-reporte-detalle-torre"),
                                reporte(page, "/zabbix.php?action=lagunitas.reporte.equipo&periodo=7d&hostid=10749", "32-reporte-detalle-gateway"),
                                reporte(page, "/zabbix.php?action=lagunitas.reporte.equipo&periodo=7d&hostid=10746", "33-reporte-detalle-ap")],
            "config": lambda: [(page.set_viewport_size({"width": 1600, "height": 1000}),
                                ir(page, "/zabbix.php?action=template.list&filter_name=Lagunitas&filter_set=1", 3),
                                foto(page, "40-templates")),
                               (ir(page, "/zabbix.php?action=host.view&filter_rst=1", 4),
                                ajustar_alto(page), foto(page, "41-hosts")),
                               (page.set_viewport_size({"width": 1600, "height": 1000}),
                                ir(page, "/zabbix.php?action=latest.view&hostids%5B%5D=10720&filter_set=1", 4),
                                ajustar_alto(page), foto(page, "42-latest-data-torre")),
                               (page.set_viewport_size({"width": 1600, "height": 1000}),
                                ir(page, "/zabbix.php?action=slareport.list", 4), foto(page, "43-sla-report")),
                               (page.set_viewport_size({"width": 1600, "height": 1000}),
                                ir(page, "/zabbix.php?action=host.dashboard.view&hostid=10720", 3), page.click("text=Detalle de radio airMAX"), time.sleep(6),
                                ajustar_alto(page), foto(page, "44-dashboard-template-torre"))],
            "problemas": lambda: (page.set_viewport_size({"width": 1600, "height": 1000}),
                                  ir(page, "/zabbix.php?action=problem.view&filter_set=1&show=1", 4),
                                  foto(page, "50-problemas")),
            "caida": lambda: [dashboard(page, 1, "51-caida-estado-red"), dashboard(page, 2, "52-caida-equipos"),
                              (page.set_viewport_size({"width": 1600, "height": 1000}),
                               ir(page, "/zabbix.php?action=problem.view&filter_set=1&show=1", 4),
                               foto(page, "53-caida-problemas"))],
        }
        for k, f in pasos.items():
            if solo and k not in solo:
                continue
            print(k)
            f()
        b.close()


if __name__ == "__main__":
    main(sys.argv[1:] or None)
