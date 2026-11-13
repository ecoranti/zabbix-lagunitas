#!/usr/bin/env python3
"""Genera la presentación de la capacitación comunitaria (PowerPoint 16:9).

Uso:   .venv/bin/pip install -r requirements-docs.txt
       .venv/bin/python scripts/capacitacion-pptx.py ["docs/Capacitacion comunitaria - Red Las Lagunitas.pptx"]

Todo el contenido está en este archivo: textos, notas del orador, recortes de las
capturas (docs/informe/media, las mismas figuras del informe) y diagramas dibujados
con formas editables. Los logos salen de docs/plantilla/portada-unrc.docx.

Los umbrales que se muestran se leen del código (lagunitas/templates*.py, hosts.py,
alerts.py, services.py) al generar: si cambian ahí, cambian en las diapositivas.
El script avisa por consola si algún texto no entra en su cuadro (medición con Arial).
"""
from __future__ import annotations

import io
import re
import sys
import zipfile
from pathlib import Path

from PIL import Image, ImageFont
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

REPO = Path(__file__).resolve().parents[1]
MEDIA = REPO / "docs/informe/media"
PORTADA = REPO / "docs/plantilla/portada-unrc.docx"
SALIDA = REPO / "docs/Capacitacion comunitaria - Red Las Lagunitas.pptx"

ANCHO, ALTO = 13.333, 7.5
MX = 0.6                      # margen lateral
CW = ANCHO - 2 * MX           # ancho útil
FUENTE = "Arial"

AZUL = "1F3A5F"               # mismo azul que las guías (scripts/md2docx.py)
AZUL_MEDIO = "2F6DA8"
TINTE = "EAF0F7"
TINTE_2 = "F4F6F9"
TEXTO = "1B2733"
GRIS = "555F66"
GRIS_CLARO = "C9D1D9"
BLANCO = "FFFFFF"
VERDE, AMBAR, ROJO, NARANJA, GRIS_EST, GRIS_NOMON = "2E9E4F", "E0A106", "D93025", "E8710A", "7A8794", "B8C0C8"
# Colores de severidad de Zabbix (los que se ven en "Problemas por severidad").
SEV = {"Disaster": "E45959", "High": "E97659", "Average": "FFA059", "Warning": "FFC859", "Information": "7499FF"}

# Figuras del informe (docs/informe/media) que se usan como capturas.
IMG = {
    "esquema": "image3.png", "estado": "image11.jpg", "equipos": "image12.jpg", "ficha": "image13.jpg",
    "radio": "image14.jpg", "router": "image16.jpg", "dependencias": "image18.jpg", "mapa": "image23.jpg",
    "reporte": "image25.jpg", "problemas": "image27.jpg", "caida_estado": "image28.jpg",
    "caida_equipos": "image29.jpg", "caida_problemas": "image30.jpg", "telegram": "image31.png",
}


# ----------------------------------------------------------------- umbrales desde el código
def _macro(texto: str, nombre: str) -> str:
    m = re.search(r'"\{\$' + re.escape(nombre) + r'\}",\s*"value":\s*"([^"]+)"', texto)
    if not m:
        sys.exit(f"No se encontró la macro {{${nombre}}} en el código: revisar scripts/capacitacion-pptx.py")
    return m.group(1)


def _num(valor: str, dec: int | None = None) -> str:
    """Número con coma decimal ('12.0' -> '12,0')."""
    n = float(valor)
    if dec is None:
        dec = 0 if n == int(n) else 1
    return f"{n:.{dec}f}".replace(".", ",")


def leer_umbrales() -> dict:
    icmp = (REPO / "lagunitas/templates.py").read_text(encoding="utf-8")
    snmp = (REPO / "lagunitas/templates_snmp.py").read_text(encoding="utf-8")
    hosts = (REPO / "lagunitas/hosts.py").read_text(encoding="utf-8")
    alertas = (REPO / "lagunitas/alerts.py").read_text(encoding="utf-8")
    servicios = (REPO / "lagunitas/services.py").read_text(encoding="utf-8")
    modelo = (REPO / "lagunitas/model.py").read_text(encoding="utf-8")
    base, nivel = map(int, re.search(r"CAIDA_BASE, CAIDA_POR_NIVEL = (\d+), (\d+)", hosts).groups())
    return {
        "perdida": _macro(icmp, "ICMP.PERDIDA.WARN"),
        "latencia_ms": _num(str(float(_macro(icmp, "ICMP.LATENCIA.WARN")) * 1000)),
        "caida_base": base, "caida_nivel": nivel,
        "senal_warn": _macro(snmp, "AIRMAX.SENAL.WARN"), "senal_crit": _macro(snmp, "AIRMAX.SENAL.CRIT"),
        "ruido": _macro(snmp, "AIRMAX.RUIDO.WARN"), "snr": _macro(snmp, "AIRMAX.SNR.WARN"),
        "ccq": _macro(snmp, "AIRMAX.CCQ.WARN"),
        "v_warn": _num(_macro(snmp, "MIKROTIK.VOLTAJE.WARN"), 1),
        "v_crit": _num(_macro(snmp, "MIKROTIK.VOLTAJE.CRIT"), 1),
        "v_max": _num(_macro(snmp, "MIKROTIK.VOLTAJE.MAX"), 1),
        "repite": re.search(r'"esc_period": "(\d+)m"', alertas).group(1),
        "sla": _num(re.search(r'slo: str = "([\d.]+)"', servicios).group(1), 1),
        "intervalo": re.search(r'INTERVALO_VALOR = "(\d+)s"', modelo).group(1),
    }


def profundidad_maxima() -> int:
    """Niveles del equipo más alejado del gateway según el inventario de producción."""
    import yaml
    inv = yaml.safe_load((REPO / "config/inventory.produccion.yaml").read_text(encoding="utf-8"))
    padre = {}
    for e in inv["elementos"]:
        padre[e["host"]] = e.get("padre")
        for d in e.get("dispositivos") or []:
            padre[d["host"]] = d.get("padre") or e["host"]

    def nivel(h: str) -> int:
        n = 0
        while padre.get(h):
            h, n = padre[h], n + 1
        return n
    return max(nivel(h) for h in padre)


# ----------------------------------------------------------------- utilidades de dibujo
def rgb(h: str) -> RGBColor:
    return RGBColor.from_string(h)


_FUENTES: dict = {}
AVISOS: list[str] = []


def _fuente(size: float, bold: bool):
    clave = (round(size * 4), bold)
    if clave not in _FUENTES:
        candidatos = (["Arial Bold.ttf", "LiberationSans-Bold.ttf", "arialbd.ttf"] if bold
                      else ["Arial.ttf", "LiberationSans-Regular.ttf", "arial.ttf"])
        carpetas = ["/System/Library/Fonts/Supplemental", "/Library/Fonts", "/usr/share/fonts/truetype/liberation",
                    "/usr/share/fonts/liberation", "C:/Windows/Fonts"]
        _FUENTES[clave] = None
        for c in carpetas:
            for n in candidatos:
                if (Path(c) / n).exists():
                    _FUENTES[clave] = ImageFont.truetype(str(Path(c) / n), int(size * 4))
                    break
            if _FUENTES[clave]:
                break
    return _FUENTES[clave]


def _lineas(texto: str, size: float, bold: bool, ancho_pt: float) -> int:
    f = _fuente(size, bold)
    if f is None:
        return 1
    n = 0
    for parte in texto.split("\n"):
        linea, n = "", n + 1
        for palabra in parte.split(" "):
            prueba = (linea + " " + palabra).strip()
            if f.getlength(prueba) / 4 > ancho_pt and linea:
                n, linea = n + 1, palabra
            else:
                linea = prueba
    return n


class Deck:
    def __init__(self) -> None:
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = Inches(ANCHO), Inches(ALTO)
        self.bloque = ""
        self.sl = None
        self.n = 0
        self.indice: list[tuple[int, str]] = []
        with zipfile.ZipFile(PORTADA) as z:
            self.logos = [z.read("word/media/image2.png"), z.read("word/media/image1.png")]

    # --- diapositivas
    def nueva(self, titulo: str, notas: str, fondo: str = BLANCO, color_titulo: str = AZUL,
              caja=(MX, 0.42, CW, 0.95), size: float = 32, pie: bool = True):
        self.sl = self.prs.slides.add_slide(self.prs.slide_layouts[5])
        self.n += 1
        self.indice.append((self.n, titulo.replace("\n", " ")))
        bg = self.sl.background.fill
        bg.solid()
        bg.fore_color.rgb = rgb(fondo)
        t = self.sl.shapes.title
        t.left, t.top, t.width, t.height = (Inches(v) for v in caja)
        tf = t.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE if pie else MSO_ANCHOR.BOTTOM
        for i, linea in enumerate(titulo.split("\n")):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = PP_ALIGN.LEFT
            r = p.add_run()
            r.text = linea
            r.font.size, r.font.bold, r.font.name = Pt(size), True, FUENTE
            r.font.color.rgb = rgb(color_titulo)
        self._medir(titulo, size, True, caja[2], caja[3], f"título «{titulo[:40]}»", 1.0)
        self.sl.notes_slide.notes_text_frame.text = notas.strip()
        if pie:
            oscuro = fondo != BLANCO
            c = "B9C6D6" if oscuro else GRIS
            izq = "Capacitación comunitaria · Red Las Lagunitas" + (f"  |  {self.bloque}" if self.bloque else "")
            self.txt(MX, 7.0, 9.5, 0.28, izq, size=11, color=c)
            tb = self.sl.shapes.add_textbox(Inches(ANCHO - MX - 1.2), Inches(7.0), Inches(1.2), Inches(0.28))
            tf = tb.text_frame
            tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.RIGHT
            fld = p._p.makeelement(qn("a:fld"), {"id": "{B6F15528-21DE-4FAA-801E-634DDDAF4B2B}", "type": "slidenum"})
            rpr = fld.makeelement(qn("a:rPr"), {"lang": "es-AR", "sz": "1100"})
            fill = rpr.makeelement(qn("a:solidFill"), {})
            fill.append(fill.makeelement(qn("a:srgbClr"), {"val": c}))
            rpr.append(fill)
            rpr.append(rpr.makeelement(qn("a:latin"), {"typeface": FUENTE}))
            t_el = fld.makeelement(qn("a:t"), {})
            t_el.text = str(self.n)
            fld.append(rpr)
            fld.append(t_el)
            p._p.append(fld)
        return self.sl

    def seccion(self, numero: int, titulo: str, minutos: str, resumen: str, notas: str):
        self.bloque = f"{numero}. {titulo}"
        self.nueva(titulo, notas, fondo=AZUL, color_titulo=BLANCO, caja=(2.9, 2.55, 9.6, 1.5), size=44)
        self.ovalo(0.9, 2.6, 1.5, str(numero), fill=BLANCO, color=AZUL, size=54)
        self.txt(2.9, 4.2, 9.4, 1.0, resumen, size=22, color="D6E0EC")
        self.txt(2.9, 2.05, 6, 0.4, f"BLOQUE {numero}  ·  {minutos}", size=16, color="9FB4CC", bold=True)

    # --- texto
    def _medir(self, texto, size, bold, w, h, donde, interlineado=1.0, extra_pt=0.0):
        alto = _lineas(texto, size, bold, w * 72) * size * 1.2 * interlineado + extra_pt
        if alto > h * 72 + 1.5:
            AVISOS.append(f"  [desborde] diapositiva {self.n}, {donde}: {alto / 72:.2f}\" > {h:.2f}\"")

    def txt(self, x, y, w, h, contenido, size=18, color=TEXTO, bold=False, align="l", anchor="t",
            esp=6, vinetas=False, cursiva=False, interlineado=1.0):
        """contenido: str o lista de párrafos; párrafo: str o lista de tramos (str | (str, {b,c,i,s}))."""
        tb = self.sl.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE, "b": MSO_ANCHOR.BOTTOM}[anchor]
        parrafos = contenido if isinstance(contenido, list) else [contenido]
        alto_pt, sangria = 0.0, 0.28 if vinetas else 0.0
        for i, par in enumerate(parrafos):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}[align]
            p.space_after = Pt(esp if i < len(parrafos) - 1 else 0)
            if interlineado != 1.0:
                p.line_spacing = interlineado
            if vinetas:
                ppr = p._p.get_or_add_pPr()
                ppr.set("marL", str(Inches(sangria)))
                ppr.set("indent", str(-Inches(sangria)))
                col = ppr.makeelement(qn("a:buClr"), {})
                col.append(col.makeelement(qn("a:srgbClr"), {"val": AZUL_MEDIO}))
                ppr.append(col)
                ppr.append(ppr.makeelement(qn("a:buFont"), {"typeface": "Arial"}))
                ppr.append(ppr.makeelement(qn("a:buChar"), {"char": "•"}))
            tramos = par if isinstance(par, list) else [par]
            plano, alguno_negrita, mayor = "", bold, size
            for tr in tramos:
                texto, o = (tr, {}) if isinstance(tr, str) else tr
                r = p.add_run()
                r.text = texto
                f = r.font
                f.name, f.size = FUENTE, Pt(o.get("s", size))
                f.bold, f.italic = o.get("b", bold), o.get("i", cursiva)
                f.color.rgb = rgb(o.get("c", color))
                plano += texto
                alguno_negrita = alguno_negrita or o.get("b", False)
                mayor = max(mayor, o.get("s", size))
            alto_pt += _lineas(plano, mayor, alguno_negrita, (w - sangria) * 72) * mayor * 1.2 * interlineado
            alto_pt += esp if i < len(parrafos) - 1 else 0
        if alto_pt > h * 72 + 1.5:
            AVISOS.append(f"  [desborde] diapositiva {self.n}, texto «{str(parrafos[0])[:38]}»: "
                          f"{alto_pt / 72:.2f}\" > {h:.2f}\"")
        return tb

    # --- formas
    def _forma(self, tipo, x, y, w, h, fill, linea=None, grosor=1.0):
        s = self.sl.shapes.add_shape(tipo, Inches(x), Inches(y), Inches(w), Inches(h))
        s.shadow.inherit = False
        if fill is None:
            s.fill.background()
        else:
            s.fill.solid()
            s.fill.fore_color.rgb = rgb(fill)
        if linea is None:
            s.line.fill.background()
        else:
            s.line.color.rgb = rgb(linea)
            s.line.width = Pt(grosor)
        return s

    def tarjeta(self, x, y, w, h, fill=TINTE, linea=None, grosor=1.0, radio=0.10):
        s = self._forma(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, fill, linea, grosor)
        s.adjustments[0] = min(0.5, radio / min(w, h))
        return s

    def _texto_forma(self, s, texto, size, color, bold=True, w=None, h=None):
        tf = s.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = Inches(0.06)
        tf.margin_top = tf.margin_bottom = Inches(0.02)
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        for i, linea in enumerate(texto.split("\n")):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = PP_ALIGN.CENTER
            r = p.add_run()
            r.text = linea
            r.font.name, r.font.size, r.font.bold = FUENTE, Pt(size), bold
            r.font.color.rgb = rgb(color)
        if w and h:
            self._medir(texto, size, bold, w - 0.12, h - 0.04, f"forma «{texto[:30]}»")

    def chip(self, x, y, w, h, texto, fill, color=BLANCO, size=16, linea=None, bold=True, radio=0.10, discontinua=False):
        s = self.tarjeta(x, y, w, h, fill, linea, 1.5, radio)
        if discontinua:
            s.line.dash_style = MSO_LINE.DASH
        self._texto_forma(s, texto, size, color, bold, w, h)
        return s

    def ovalo(self, x, y, d, texto, fill=AZUL, color=BLANCO, size=18, borde=None):
        s = self._forma(MSO_SHAPE.OVAL, x, y, d, d, fill, borde, 2.0)
        tf = s.text_frame
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.word_wrap = False
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = texto
        r.font.name, r.font.size, r.font.bold = FUENTE, Pt(size), True
        r.font.color.rgb = rgb(color)
        return s

    def linea(self, x1, y1, x2, y2, color=GRIS_EST, grosor=2.0, discontinua=False, flecha=False):
        c = self.sl.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
        c.line.color.rgb = rgb(color)
        c.line.width = Pt(grosor)
        if discontinua:
            c.line.dash_style = MSO_LINE.DASH
        if flecha:
            ln = c.line._get_or_add_ln()
            ln.append(ln.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"}))
        return c

    # --- imágenes
    def imagen(self, clave_o_bytes, x, y, w, h, recorte=None, alt="", borde=True, alinear="c"):
        """Inserta sin deformar (contenida en la caja). recorte = (x0, y0, x1, y1) en píxeles del original.
        Devuelve una función que convierte píxeles del original a pulgadas de la diapositiva."""
        if isinstance(clave_o_bytes, bytes):
            im = Image.open(io.BytesIO(clave_o_bytes))
        else:
            im = Image.open(MEDIA / IMG[clave_o_bytes])
        x0, y0 = 0, 0
        if recorte:
            x0, y0 = recorte[0], recorte[1]
            im = im.crop(recorte)
        esc = min(w / im.width, h / im.height)
        iw, ih = im.width * esc, im.height * esc
        ix = x + {"l": 0, "c": (w - iw) / 2, "r": w - iw}[alinear]
        iy = y
        buf = io.BytesIO()
        if im.mode in ("RGBA", "P", "LA"):
            im.save(buf, "PNG")
        else:
            im.convert("RGB").save(buf, "JPEG", quality=92)
        buf.seek(0)
        pic = self.sl.shapes.add_picture(buf, Inches(ix), Inches(iy), Inches(iw), Inches(ih))
        pic._element.nvPicPr.cNvPr.set("descr", alt)
        if borde:
            pic.line.color.rgb = rgb(GRIS_CLARO)
            pic.line.width = Pt(1)
        return lambda px, py: (ix + (px - x0) * esc, iy + (py - y0) * esc)

    def marca(self, a_pulgadas, px, py, numero, d=0.42):
        cx, cy = a_pulgadas(px, py)
        self.ovalo(cx - d / 2, cy - d / 2, d, str(numero), fill=AZUL, color=BLANCO, size=15, borde=BLANCO)

    def recuadro(self, a_pulgadas, caja_px):
        x0, y0 = a_pulgadas(caja_px[0], caja_px[1])
        x1, y1 = a_pulgadas(caja_px[2], caja_px[3])
        self.tarjeta(x0, y0, x1 - x0, y1 - y0, None, AZUL, 2.5, 0.06)

    def leyenda(self, x, y, w, items, size=17, paso=0.62, d=0.42):
        """Lista numerada (título, descripción) que acompaña a las marcas de una captura."""
        for i, (titulo, desc) in enumerate(items):
            self.ovalo(x, y + i * paso, d, str(i + 1), size=15)
            self.txt(x + d + 0.18, y + i * paso, w - d - 0.18, paso - 0.1,
                     [[(titulo, {"b": True, "c": AZUL})], desc], size=size, esp=2)


# ----------------------------------------------------------------- diagrama de dependencias
# Sitios operativos del inventario (config/inventory.produccion.yaml): (columna, fila, rol, padre).
ARBOL = {
    "Gateway\nMikrotik": (0, 2, "gateway", None),
    "Unión de\nlos Ríos": (1, 2, "torre", "Gateway\nMikrotik"),
    "Nodo Kika": (2, 0, "nodo", "Unión de\nlos Ríos"),
    "Kika": (3, 0, "hogar", "Nodo Kika"),
    "Nodo Cheo/\nMaricel": (2, 1, "nodo", "Unión de\nlos Ríos"),
    "Cheo/Maricel": (3, 1, "hogar", "Nodo Cheo/\nMaricel"),
    "Rodeo del\nPadre": (2, 2, "torre", "Unión de\nlos Ríos"),
    "Nodo Ale/\nPatricio": (3, 2, "nodo", "Rodeo del\nPadre"),
    "Ale/Patricio": (4, 2, "hogar", "Nodo Ale/\nPatricio"),
    "Ex\nAserradero": (2, 3, "torre", "Unión de\nlos Ríos"),
    "El Carrizal": (3, 3, "torre", "Ex\nAserradero"),
    "Walter": (4, 3, "hogar", "El Carrizal"),
    "Mesada": (4, 4, "nodo", "El Carrizal"),
    "Escuela\nRural": (5, 4, "hogar", "Mesada"),
    "Esther": (6, 4, "hogar", "Escuela\nRural"),
}
COLOR_ROL = {"gateway": AZUL, "torre": AZUL_MEDIO, "nodo": "5B7C99", "hogar": VERDE}


def arbol(d: Deck, y0: float, caido: str | None = None, alto_fila: float = 0.78) -> None:
    bw, bh, paso_x = 1.5, 0.6, (CW - 1.5) / 6
    pos = {k: (MX + c * paso_x, y0 + f * alto_fila) for k, (c, f, _, _) in ARBOL.items()}

    def afectado(k: str) -> bool:
        p = ARBOL[k][3]
        while p:
            if p == caido:
                return True
            p = ARBOL[p][3]
        return False

    for k, (_, _, _, padre) in ARBOL.items():
        if padre:
            (x1, y1), (x2, y2) = pos[padre], pos[k]
            roto = caido and (k == caido or afectado(k))
            d.linea(x1 + bw, y1 + bh / 2, x2, y2 + bh / 2, color=GRIS_CLARO if roto else GRIS_EST,
                    grosor=2.0, discontinua=bool(roto))
    for k, (_, _, rol, _) in ARBOL.items():
        x, y = pos[k]
        fill = COLOR_ROL[rol]
        if caido:
            fill = ROJO if k == caido else NARANJA if afectado(k) else VERDE
        d.chip(x, y, bw, bh, k, fill, size=13)


# ----------------------------------------------------------------- contenido
def construir(d: Deck, u: dict) -> None:
    caida_max = u["caida_base"] + u["caida_nivel"] * profundidad_maxima()
    caida_torre = u["caida_base"] + u["caida_nivel"]
    minutos_mes = 30 * 24 * 60 * (100 - float(u["sla"].replace(",", "."))) / 100
    sla_tiempo = f"{int(minutos_mes // 60)} h {int(round(minutos_mes % 60))} min"

    # ---------------------------------------------------------------- 1. Portada
    d.nueva("Capacitación comunitaria", """
QUÉ DECIR: Presentate y contá en una frase de qué se trata: la red comunitaria ahora tiene un sistema que la vigila todo el tiempo, y hoy vamos a aprender a usarlo. No hace falta saber de redes ni de computación.
CONTEXTO PARA QUIEN DICTA: Este material forma parte de la Práctica Profesional Supervisada (PPS) de Ingeniería en Telecomunicaciones de la UNRC. El sistema se validó en un laboratorio que reproduce la red; por eso las pantallas que se ven son de ese entorno. El material está pensado para que cualquier integrante de la comunidad pueda dictarlo, o para leerlo por cuenta propia siguiendo estas notas.
DURACIÓN TOTAL: entre 75 y 90 minutos, con una práctica guiada de unos 20 minutos.
""", fondo=AZUL, color_titulo=BLANCO, caja=(0.8, 1.55, 7.4, 1.9), size=50, pie=False)
    d.txt(0.8, 3.6, 7.2, 1.3, "Cómo usar el sistema de monitoreo de la Red Comunitaria y Científica Las Lagunitas",
          size=24, color="D6E0EC")
    d.txt(0.8, 5.55, 7.2, 0.9, ["Material para dictar el taller o para la autocapacitación",
                                "Zabbix 7.0 LTS  ·  Alpa Corral, Córdoba"], size=16, color="9FB4CC", esp=4)
    d._forma(MSO_SHAPE.RECTANGLE, 8.75, 0, ANCHO - 8.75, ALTO, BLANCO)
    d.imagen(d.logos[0], 9.55, 0.85, 1.25, 1.75, alt="Escudo de la Universidad Nacional de Río Cuarto", borde=False)
    d.imagen(d.logos[1], 11.05, 0.85, 1.25, 1.75, alt="Escudo de la Facultad de Ingeniería de la UNRC", borde=False)
    d.txt(9.3, 2.95, 3.5, 1.0, ["Universidad Nacional de Río Cuarto", "Facultad de Ingeniería"],
          size=16, color=AZUL, bold=True, esp=2)
    d.txt(9.3, 3.95, 3.5, 0.9, "Práctica Profesional Supervisada · Ingeniería en Telecomunicaciones", size=14, color=GRIS)
    d.txt(9.3, 5.1, 3.5, 1.6, [[("Autor  ", {"c": GRIS}), ("Elias Coranti", {"b": True})],
                               [("Tutor universidad  ", {"c": GRIS}), ("Pablo Solivella", {"b": True})],
                               [("Tutor organización  ", {"c": GRIS}), ("Daniel Bellomo", {"b": True})]],
          size=14, esp=5)

    # ---------------------------------------------------------------- 2. Cómo usar este material
    d.nueva("Cómo usar este material", """
QUÉ DECIR: Este material sirve de dos maneras. Si lo dictás, cada diapositiva tiene notas como esta con lo que conviene decir y mostrar. Si lo leés por tu cuenta, seguí las notas en orden y hacé la práctica del bloque 7 frente al sistema.
ANTES DE EMPEZAR (quien dicta): 1) Comprobá que podés entrar al sistema con tu usuario. 2) Tené abierto el tablero «Las Lagunitas - Centro de monitoreo» en otra pestaña para alternar con las diapositivas. 3) Si hay conexión, pedí a quienes participan que tengan el celular con Telegram a mano.
ACLARACIÓN HONESTA: las capturas son del laboratorio donde se probó el sistema. Los nombres de los sitios son los reales, pero los valores (señal, voltaje, porcentajes) son simulados. En la red real las pantallas son las mismas; cambian los números.
""")
    tarjetas = [
        ("Para dictarla", "Cada diapositiva tiene notas del orador con qué decir y qué mostrar. Alterná con el sistema en vivo."),
        ("Para autocapacitarse", "Leé las notas en orden y hacé la práctica guiada del bloque 7 frente al sistema."),
        ("Qué hace falta", "Una computadora con navegador, usuario del sistema y, si se puede, proyector y Telegram en el celular."),
    ]
    for i, (t, c) in enumerate(tarjetas):
        x = MX + i * (3.85 + 0.275)
        d.tarjeta(x, 1.65, 3.85, 3.2)
        d.ovalo(x + 0.3, 1.95, 0.6, str(i + 1), size=22)
        d.txt(x + 0.3, 2.75, 3.25, 0.45, t, size=20, bold=True, color=AZUL)
        d.txt(x + 0.3, 3.25, 3.25, 1.5, c, size=16)
    d.tarjeta(MX, 5.2, CW, 1.35, TINTE_2, GRIS_CLARO)
    d.txt(MX + 0.35, 5.3, CW - 0.7, 1.15,
          [[("Sobre las capturas. ", {"b": True, "c": AZUL}),
            "Son del laboratorio donde se validó el sistema: los nombres de los sitios son los de la red, "
            "los valores son simulados. En la red real las pantallas son las mismas."]], size=16, anchor="m")

    # ---------------------------------------------------------------- 3. Objetivos
    d.nueva("Al terminar vas a poder", """
QUÉ DECIR: Leé los cinco objetivos y aclará que son prácticos: se trata de saber mirar, entender y avisar, no de configurar. Las tareas técnicas (agregar equipos, cambiar umbrales) quedan para quien administra el sistema.
PREGUNTA PARA ABRIR: «¿Cómo nos enteramos hoy cuando se cae Internet?» Dejá que cuenten su experiencia; sirve para el bloque 2.
PARA EL CIERRE: volvé a esta diapositiva y repasá objetivo por objetivo si se cumplió.
""")
    objetivos = [
        ("Explicar", "qué es la red y cómo llega Internet hasta cada casa"),
        ("Leer", "el tablero y el mapa, y reconocer los colores y estados"),
        ("Interpretar", "una alarma, incluida la que llega por Telegram"),
        ("Actuar", "con un procedimiento claro y saber a quién avisar"),
        ("Hacer", "las tareas simples: revisar un equipo y sacar un reporte"),
    ]
    for i, (v, r) in enumerate(objetivos):
        y = 1.6 + i * 1.0
        d.tarjeta(MX, y, CW, 0.84, TINTE if i % 2 == 0 else TINTE_2)
        d.ovalo(MX + 0.22, y + 0.14, 0.56, str(i + 1), size=20)
        d.txt(MX + 1.05, y, 2.5, 0.84, v, size=22, bold=True, color=AZUL, anchor="m")
        d.txt(MX + 3.5, y, CW - 3.8, 0.84, r, size=20, anchor="m")

    # ---------------------------------------------------------------- 4. Agenda
    d.nueva("Recorrido de la capacitación", """
QUÉ DECIR: Mostrá el recorrido y los tiempos. Son siete bloques cortos; el más largo es el de alarmas, que es el más importante, y el último es práctico.
TIEMPOS: son orientativos y suman unos 90 minutos. Si hay menos tiempo, se pueden acortar los bloques 2 y 6. No conviene recortar el 5 (alarmas) ni la práctica.
SUGERENCIA: hacé una pausa corta después del bloque 4.
""")
    agenda = [("La red", "10 min", "Qué es y cómo llega Internet a cada casa"),
              ("Para qué monitorear", "5 min", "Qué mira el sistema y qué no"),
              ("Entrar y recorrer", "15 min", "Tablero, mapa, colores y estados"),
              ("La ficha de un equipo", "10 min", "Señal, latencia, pérdida y batería"),
              ("Alarmas", "20 min", "Qué hacer, Telegram y casos típicos"),
              ("Reportes y tareas", "10 min", "Disponibilidad, quién hace qué, cuidados"),
              ("Práctica y cierre", "20 min", "Actividad guiada, repaso y glosario")]
    for i, (t, m, c) in enumerate(agenda):
        y = 1.55 + i * 0.74
        d.ovalo(MX, y + 0.04, 0.52, str(i + 1), size=18)
        d.txt(MX + 0.8, y, 3.9, 0.6, t, size=20, bold=True, color=AZUL, anchor="m")
        d.txt(MX + 4.75, y, 5.9, 0.6, c, size=17, anchor="m")
        d.chip(ANCHO - MX - 1.3, y + 0.06, 1.3, 0.48, m, TINTE, AZUL, size=15)
        if i < len(agenda) - 1:
            d.linea(MX + 0.8, y + 0.67, ANCHO - MX, y + 0.67, GRIS_CLARO, 0.75)

    # ================================================================ BLOQUE 1
    d.seccion(1, "La red", "10 minutos", "Qué es la Red Las Lagunitas y cómo llega Internet a cada casa", """
QUÉ DECIR: Antes de mirar el sistema hay que entender qué es lo que vigila. En este bloque vemos cómo está armada la red y por qué algunos equipos dependen de otros.
PREGUNTA: «¿Alguien sabe por qué torre o por qué nodo pasa la conexión de su casa?»
""")

    # ---------------------------------------------------------------- 6. Qué es la red
    d.nueva("Una red hecha de torres, nodos y hogares", """
QUÉ DECIR: Este es el gráfico esquemático que usa la propia red comunitaria. Los cuadrados son las cuatro torres (Unión de los Ríos, Rodeo del Padre, Ex Aserradero y El Carrizal), los círculos son nodos intermedios que repiten la señal y las casitas son los hogares y la Escuela Rural.
QUÉ MOSTRAR: señalá las tres clases de línea: llena es un enlace operativo, de rayas es un enlace en proceso y de puntos es un tramo sin configurar. El sistema de monitoreo usa esa misma convención en su mapa.
DATO: Internet entra por un solo lugar, el router Mikrotik (el «gateway»), que se conecta con la Cooperativa de Alpa Corral.
FUENTE DE LAS CIFRAS: inventario de la red (config/inventory.produccion.yaml) e informe de la PPS, Fase 1. No todos los tramos están en servicio: algunos están en proceso o sin configurar.
""")
    d.imagen("esquema", MX, 1.6, 8.6, 4.4, alt="Gráfico esquemático de la red: torres, nodos y hogares con el estado de cada enlace")
    d.txt(MX, 6.1, 8.6, 0.5, "Gráfico esquemático de la red comunitaria. Línea llena: operativo. Rayas: en proceso. Puntos: sin configurar.",
          size=12, color=GRIS)
    for i, (n, t) in enumerate([("4", "torres que forman la columna vertebral"), ("9", "nodos intermedios que reparten la señal"),
                                ("13", "puntos de usuario: 12 hogares y la Escuela Rural"), ("1", "salida a Internet: el gateway Mikrotik")]):
        y = 1.6 + i * 1.24
        d.tarjeta(9.5, y, ANCHO - MX - 9.5, 1.08)
        d.txt(9.6, y, 1.0, 1.08, n, size=40, bold=True, color=AZUL, align="c", anchor="m")
        d.txt(10.7, y, 1.9, 1.08, t, size=14, anchor="m")

    # ---------------------------------------------------------------- 7. Cómo llega Internet
    d.nueva("Internet llega por tramos, como el agua por una acequia", """
QUÉ DECIR: Internet no llega «directo» a cada casa. Va pasando de un equipo al siguiente por enlaces de radio, como el agua que baja por una acequia: si se corta arriba, no llega nada abajo, aunque el resto del canal esté sano.
QUÉ MOSTRAR: seguí con el dedo el camino hasta la casa de Esther, que es uno de los más largos de la red: Cooperativa, gateway Mikrotik, Unión de los Ríos, Ex Aserradero, El Carrizal, Mesada, Escuela Rural y Esther.
PRECISIÓN TÉCNICA: el dibujo muestra los sitios. En Mesada y en la Escuela hay además una segunda antena que retransmite hacia el sitio siguiente; el sistema las monitorea como equipos aparte («Mesada · AP a Escuela», «Escuela · AP a Esther»).
PREGUNTA: «Si se apaga El Carrizal, ¿quiénes se quedan sin Internet?» (Respuesta: Walter, Mesada, la Escuela y Esther).
FUENTE: campo «padre» de cada equipo en config/inventory.produccion.yaml.
""")
    cadena = [("Internet", "Cooperativa\nAlpa Corral", "6B7785"), ("Gateway", "Mikrotik", AZUL), ("Torre", "Unión de\nlos Ríos", AZUL_MEDIO),
              ("Torre", "Ex\nAserradero", AZUL_MEDIO), ("Torre", "El Carrizal", AZUL_MEDIO), ("Nodo", "Mesada", "5B7C99"),
              ("Institución", "Escuela\nRural", VERDE), ("Hogar", "Esther", VERDE)]
    bw, gap = 1.3, (CW - 8 * 1.3) / 7
    for i, (rol, nombre, color) in enumerate(cadena):
        x = MX + i * (bw + gap)
        d.txt(x, 1.75, bw, 0.3, rol.upper(), size=11, bold=True, color=GRIS, align="c")
        d.chip(x, 2.1, bw, 1.0, nombre, color, size=13)
        if i < len(cadena) - 1:
            d.linea(x + bw + 0.03, 2.6, x + bw + gap - 0.03, 2.6, AZUL, 2.5, flecha=True)
    d.tarjeta(MX, 3.75, 5.9, 2.75)
    d.txt(MX + 0.35, 3.95, 5.2, 0.45, "La idea", size=20, bold=True, color=AZUL)
    d.txt(MX + 0.35, 4.45, 5.2, 1.9, ["Cada flecha es un tramo. La mayoría son enlaces de radio entre antenas.",
                                      "Si se corta un tramo, todo lo que está a su derecha queda sin Internet."], size=19, esp=12)
    d.tarjeta(6.85, 3.75, ANCHO - MX - 6.85, 2.75, TINTE_2, GRIS_CLARO)
    d.txt(7.2, 3.95, 5.2, 0.45, "Para pensar", size=20, bold=True, color=AZUL)
    d.txt(7.2, 4.45, 5.2, 1.9, ["Si se apaga El Carrizal, ¿quiénes se quedan sin Internet?",
                                [("Mesada, la Escuela Rural y Esther. También Walter, que cuelga de esa torre.", {"c": GRIS})]],
          size=19, esp=12)

    # ---------------------------------------------------------------- 8. Padre e hijo
    d.nueva("Cada equipo tiene un «padre» del que depende", """
QUÉ DECIR: A la relación entre un equipo y el que le da la conexión la llamamos padre e hijo. El padre de la torre Rodeo del Padre es Unión de los Ríos; el padre de Unión de los Ríos es el gateway. Un equipo puede tener muchos hijos, pero un solo padre.
QUÉ MOSTRAR: recorré el árbol de izquierda a derecha. Pedí a cada participante que busque su casa y diga cuál es su padre, su «abuelo» y así hasta el gateway.
POR QUÉ IMPORTA: esta relación está cargada en el sistema, y es lo que le permite distinguir un equipo que falló de un equipo que solo se quedó sin camino. Lo vemos en la diapositiva siguiente.
ALCANCE DEL DIBUJO: están los sitios que hoy figuran como operativos en el inventario. Los tramos en proceso o sin configurar (Franco, Cerro Blanco, Juan Carlos, Las Guindas, Don Julio, Gladys, Eulalia/Domingo, Martín) se suman cuando entren en servicio.
FUENTE: config/inventory.produccion.yaml (campos «padre» y «estado»).
""")
    arbol(d, 1.6)
    for i, (t, c) in enumerate([("Gateway", AZUL), ("Torre", AZUL_MEDIO), ("Nodo intermedio", "5B7C99"), ("Hogar o institución", VERDE)]):
        d.tarjeta(MX + i * 2.55, 5.72, 0.3, 0.3, c, radio=0.05)
        d.txt(MX + 0.42 + i * 2.55, 5.69, 2.1, 0.36, t, size=14, anchor="m")
    d.txt(MX, 6.2, CW, 0.5, "Sitios operativos según el inventario. Se lee de izquierda a derecha: cada equipo depende del que tiene a su izquierda.",
          size=14, color=GRIS)

    # ---------------------------------------------------------------- 9. Si cae el padre
    d.nueva("Si cae el padre, los hijos quedan sin servicio", f"""
QUÉ DECIR: Mirá el mismo árbol con una falla: se apagó la torre Unión de los Ríos (en rojo). Todos los equipos que cuelgan de ella quedan sin camino hacia Internet (en naranja), aunque estén encendidos y sanos. El único que sigue bien es el gateway.
IDEA CLAVE: hay un solo equipo con un problema y es el rojo. Los naranjas no hay que ir a revisarlos: se recuperan solos cuando vuelve el rojo.
CÓMO LO RESUELVE EL SISTEMA: como conoce quién depende de quién, avisa una sola vez, por la torre. En la prueba de laboratorio dejaron de responder 19 equipos (la torre y 18 que dependen de ella, contando las antenas y routers internos de cada sitio) y llegó una única alerta.
PREGUNTA: «¿Qué pasaría si el sistema no supiera de padres e hijos?» (Llegarían 19 avisos juntos y no se sabría por dónde empezar).
FUENTE: informe de la PPS, sección Validación (caída troncal simulada); dependencias en lagunitas/hosts.py.
""")
    arbol(d, 1.6, caido="Unión de\nlos Ríos")
    for i, (t, c) in enumerate([("Caído: el que falló", ROJO), ("Sin servicio: perdió el camino", NARANJA), ("En línea", VERDE)]):
        d.tarjeta(MX + i * 3.9, 5.72, 0.3, 0.3, c, radio=0.05)
        d.txt(MX + 0.42 + i * 3.9, 5.69, 3.4, 0.36, t, size=14, anchor="m")
    d.tarjeta(MX, 6.15, CW, 0.62, TINTE)
    d.txt(MX + 0.3, 6.15, CW - 0.6, 0.62, [[("Un solo problema, una sola alerta. ", {"b": True, "c": AZUL}),
                                            "El sistema avisa por la torre y no por cada equipo que quedó sin camino."]],
          size=17, anchor="m")

    # ---------------------------------------------------------------- 10. Energía
    d.nueva("La mayoría de los nodos vive del sol y de una batería", """
QUÉ DECIR: Casi todos los nodos están lejos de la red eléctrica. Funcionan con un panel solar que carga una batería de 12 voltios, y la batería alimenta la antena día y noche.
DATO: según el relevamiento, con la batería llena un nodo aguanta entre 1,6 y 2 días sin sol. Varios días nublados seguidos, un panel sucio o con sombra, o una batería vieja pueden apagar un nodo.
POR QUÉ IMPORTA PARA EL MONITOREO: cuando un equipo deja de responder, la causa puede ser el enlace de radio o la energía. Por eso, cuando el sistema avisa una caída, lo primero que se revisa en el sitio es la alimentación.
LÍMITE REAL DEL SISTEMA: los controladores de carga instalados (Epever LS-E) no tienen forma de comunicarse, así que el sistema no puede leer cada batería. Solo conoce el voltaje donde el equipo alimentado es un router Mikrotik, que sí lo informa. Lo vemos en el bloque 4.
FUENTE: informe de la PPS, Fase 1 (Alimentación energética: baterías VRLA de 12 V y 55 Ah, autonomía de 1,6 a 2 días) y guía de integración de equipos (Energía de los nodos solares).
""")
    pasos = [("Panel solar", "Carga la batería de día"), ("Regulador", "Cuida la carga de la batería"), ("Batería 12 V", "Guarda energía para la noche"),
             ("Antena o router", "Funciona las 24 horas")]
    pw, pg = 2.6, (CW - 4 * 2.6) / 3
    for i, (t, c) in enumerate(pasos):
        x = MX + i * (pw + pg)
        d.tarjeta(x, 1.65, pw, 1.75)
        d.txt(x + 0.15, 1.8, pw - 0.3, 0.5, t, size=20, bold=True, color=AZUL, align="c")
        d.txt(x + 0.15, 2.35, pw - 0.3, 0.9, c, size=16, align="c")
        if i < 3:
            d.linea(x + pw + 0.05, 2.52, x + pw + pg - 0.05, 2.52, AZUL, 2.5, flecha=True)
    d.tarjeta(MX, 3.8, 3.9, 2.75, AZUL)
    d.txt(MX + 0.2, 3.95, 3.5, 1.2, "1,6 a 2 días", size=40, bold=True, color=BLANCO, align="c", anchor="m")
    d.txt(MX + 0.3, 5.15, 3.3, 1.2, "es lo que aguanta un nodo sin sol, con la batería llena", size=17, color="D6E0EC", align="c")
    d.txt(4.9, 3.85, ANCHO - MX - 4.9, 2.7, [
        [("Una caída puede ser el enlace o la energía. ", {"b": True, "c": AZUL}), "Por eso, ante una caída, primero se revisa la alimentación."],
        "Varios días nublados, un panel sucio o con sombra, o una batería gastada pueden apagar un nodo.",
        "El sistema solo conoce el voltaje donde hay un router Mikrotik que lo informa."],
        size=17, vinetas=True, esp=10)

    # ================================================================ BLOQUE 2
    d.seccion(2, "Para qué monitorear", "5 minutos", "Qué mira el sistema, qué avisa y qué no puede ver", """
QUÉ DECIR: Ahora que sabemos cómo es la red, veamos qué cambia al tener un sistema que la mira todo el tiempo.
RETOMAR: la pregunta del inicio, «¿cómo nos enteramos hoy cuando se cae Internet?».
""")

    # ---------------------------------------------------------------- 12. Antes y ahora
    d.nueva("De enterarse por un vecino a recibir un aviso", f"""
QUÉ DECIR: Hasta ahora, una caída se conocía cuando un vecino avisaba que no tenía Internet, y alguien con conocimientos tenía que conectarse a distancia y revisar enlace por enlace. No quedaba registro de cuánto duró ni de cuántas veces pasó.
CON EL SISTEMA: un servidor le pregunta a cada equipo cada {u['intervalo']} segundos si está bien, guarda las respuestas y, si algo anda mal, avisa al grupo de Telegram de operadores.
ANALOGÍA: es como un sereno que recorre toda la red sin parar y anota lo que ve en un cuaderno.
ACLARACIÓN: el sistema avisa y ayuda a encontrar la causa, pero no arregla nada por sí solo. Subir a una torre o cambiar una batería lo sigue haciendo la comunidad.
FUENTE: informe de la PPS, Fase 1 (Monitoreo existente y sus limitaciones); intervalo de medición en lagunitas/model.py.
""")
    for i, (t, fill, linea, items, col) in enumerate([
        ("Antes", TINTE_2, GRIS_CLARO, ["Un vecino avisa que no tiene Internet", "Alguien revisa a mano, enlace por enlace",
                                        "No queda registro de lo que pasó"], GRIS),
        ("Con el sistema", TINTE, None, [f"Cada equipo se controla cada {u['intervalo']} segundos", "El aviso llega solo, por Telegram",
                                         "Queda el historial para ver qué falla más"], AZUL)]):
        x = MX + i * (CW / 2 + 0.15)
        w = CW / 2 - 0.15
        d.tarjeta(x, 1.65, w, 3.6, fill, linea)
        d.txt(x + 0.4, 1.85, w - 0.8, 0.55, t, size=24, bold=True, color=col)
        d.txt(x + 0.4, 2.6, w - 0.8, 2.5, items, size=19, vinetas=True, esp=14)
    d.tarjeta(MX, 5.55, CW, 1.0, AZUL)
    d.txt(MX + 0.4, 5.55, CW - 0.8, 1.0, "El sistema avisa y ayuda a encontrar la causa. Arreglar sigue siendo tarea de la comunidad.",
          size=19, color=BLANCO, bold=True, anchor="m")

    # ---------------------------------------------------------------- 13. Qué mide
    d.nueva("Qué mira el sistema en cada equipo", f"""
QUÉ DECIR: El sistema hace cuatro clases de preguntas. La primera se la hace a todos los equipos: «¿estás ahí?». Es el ping. Con el mismo ping mide cuánto tarda la respuesta (latencia) y cuántas se pierden.
A las antenas Ubiquiti airMAX de las torres y nodos les pregunta además cómo está el enlace de radio: señal, ruido y calidad. Al router Mikrotik le pregunta el voltaje de alimentación y si la conexión a Internet con la Cooperativa está activa.
QUÉ NO PUEDE VER (decirlo con claridad): los routers airCube de los hogares solo responden al ping, así que el sistema sabe si están encendidos pero no cómo anda el Wi-Fi dentro de la casa. Y las baterías de los nodos no se pueden leer, salvo donde hay un Mikrotik.
PARA EL JURADO: disponibilidad, latencia y pérdida por ICMP; radio por SNMP (UBNT-MIB); Mikrotik por SNMP (voltaje, DHCP, PPPoE). Mediciones cada {u['intervalo']} s.
FUENTE: README.md, lagunitas/templates.py, lagunitas/templates_snmp.py, informe de la PPS (Variables críticas identificadas).
""")
    cuatro = [("¿Responde?", "El «ping»: una llamada corta para ver si el equipo contesta.", "Todos los equipos"),
              ("¿Responde bien?", "Cuánto tarda en contestar y cuántas respuestas se pierden.", "Todos los equipos"),
              ("¿Cómo está el enlace?", "Señal, ruido y calidad de la conexión de radio.", "Antenas airMAX"),
              ("¿Hay energía e Internet?", "Voltaje de alimentación y conexión con la Cooperativa.", "Gateway Mikrotik")]
    cwid = (CW - 3 * 0.25) / 4
    for i, (t, c, a) in enumerate(cuatro):
        x = MX + i * (cwid + 0.25)
        d.tarjeta(x, 1.65, cwid, 3.45)
        d.ovalo(x + 0.25, 1.9, 0.56, str(i + 1), size=20)
        d.txt(x + 0.25, 2.65, cwid - 0.5, 0.75, t, size=19, bold=True, color=AZUL, anchor="m")
        d.txt(x + 0.25, 3.45, cwid - 0.5, 1.0, c, size=15)
        d.chip(x + 0.25, 4.5, cwid - 0.5, 0.42, a, BLANCO, AZUL, size=13)
    d.tarjeta(MX, 5.4, CW, 1.15, TINTE_2, GRIS_CLARO)
    d.txt(MX + 0.35, 5.4, CW - 0.7, 1.15, [[("Lo que no puede ver. ", {"b": True, "c": AZUL}),
                                            "El Wi-Fi dentro de cada casa (los routers airCube solo responden al ping) y la batería de los nodos "
                                            "donde no hay un Mikrotik."]], size=16, anchor="m")

    # ================================================================ BLOQUE 3
    d.seccion(3, "Entrar y recorrer", "15 minutos", "El tablero, el mapa y el significado de cada color", """
QUÉ DECIR: Vamos a entrar al sistema y a recorrer las pantallas que se usan todos los días. Con usuario de operador solo se puede mirar: no hay forma de romper nada.
QUÉ MOSTRAR: desde acá conviene alternar entre las diapositivas y el sistema real.
""")

    # ---------------------------------------------------------------- 15. Cómo entrar
    d.nueva("Cómo entrar al sistema", """
QUÉ DECIR: El sistema se usa desde el navegador de cualquier computadora o celular, como una página web. No hay que instalar nada.
QUÉ MOSTRAR: hacé los cuatro pasos en vivo. La dirección la define quien administra el sistema al instalarlo: escribila en el cuadro antes de dictar. En el laboratorio es http://localhost:8090.
USUARIOS: cada operador tiene un usuario propio dentro del grupo «Operadores Las Lagunitas», con permiso de solo lectura sobre la red. El usuario Admin es solo para quien administra.
SI ALGUIEN NO TIENE USUARIO: anotá su nombre para pedírselo a quien administra el sistema. No presten usuarios.
DATO A COMPLETAR: la dirección de acceso de la instalación real.
FUENTE: manual de administración (Acceso) y lagunitas/alerts.py (grupo de usuarios con permiso de lectura).
""")
    pasos = [("Abrí el navegador", "y escribí la dirección del sistema"), ("Ingresá con tu usuario", "y tu contraseña personales"),
             ("Entrá al menú Dashboards", "en la columna de la izquierda"), ("Elegí el tablero", "Las Lagunitas - Centro de monitoreo")]
    for i, (t, c) in enumerate(pasos):
        y = 1.6 + i * 1.0
        d.ovalo(MX, y + 0.1, 0.62, str(i + 1), size=22)
        d.txt(MX + 0.9, y, 6.2, 0.45, t, size=20, bold=True, color=AZUL, anchor="m")
        d.txt(MX + 0.9, y + 0.43, 6.2, 0.4, c, size=16, color=GRIS)
    d.tarjeta(8.2, 1.6, ANCHO - MX - 8.2, 2.25, BLANCO, AZUL, 1.5)
    d.txt(8.5, 1.75, 4.0, 0.4, "DIRECCIÓN DEL SISTEMA", size=13, bold=True, color=GRIS)
    d.txt(8.5, 2.2, 4.0, 0.6, "https://", size=24, bold=True, color=AZUL)
    d.linea(9.75, 2.72, 12.4, 2.72, GRIS, 1.25)
    d.txt(8.5, 2.95, 4.0, 0.8, "Completar con la dirección definida al instalar el sistema", size=13, color=GRIS)
    d.tarjeta(8.2, 4.1, ANCHO - MX - 8.2, 1.5)
    d.txt(8.5, 4.2, 3.95, 1.3, [[("Solo lectura. ", {"b": True, "c": AZUL}), "Con usuario de operador podés mirar todo sin riesgo de desconfigurar nada."]],
          size=15, anchor="m")
    d.tarjeta(MX, 5.85, CW, 0.75, TINTE_2, GRIS_CLARO)
    d.txt(MX + 0.3, 5.85, CW - 0.6, 0.75, "Cada persona usa su propio usuario. Si no tenés uno, pedilo a quien administra el sistema.",
          size=16, anchor="m")

    # ---------------------------------------------------------------- 16. Cinco páginas
    d.nueva("Un tablero con cinco páginas", """
QUÉ DECIR: El tablero se llama «Las Lagunitas - Centro de monitoreo» y tiene cinco páginas, que se cambian con las pestañas de arriba. Para el día a día alcanza con las dos primeras.
QUÉ MOSTRAR: en el sistema, hacé clic en cada pestaña. Mostrá el botón «Start slideshow», que hace rotar las páginas solas: es útil si algún día se deja una pantalla fija en un lugar común.
DETALLE: «AP UniFi» solo tiene datos si la red incorpora puntos de acceso UniFi; en el laboratorio hay uno real de prueba. «SLA» muestra el cumplimiento mensual por sitio, que vemos en el bloque 6.
FUENTE: manual de administración (Uso diario: el Centro de monitoreo).
""")
    f = d.imagen("estado", MX, 1.55, CW, 0.75, recorte=(0, 0, 900, 105), alt="Pestañas del tablero: Estado de la red, Equipos, Detalle por equipo, AP UniFi y SLA",
                 alinear="l")
    paginas = [("Estado de la red", "El panorama: panal de equipos, problemas y mapa.", True),
               ("Equipos", "La lista completa, con buscador y filtros.", True),
               ("Detalle por equipo", "Los gráficos de un equipo que elijas.", False),
               ("AP UniFi", "Puntos de acceso Wi-Fi UniFi, si la red los tiene.", False),
               ("SLA", "El cumplimiento de cada mes.", False)]
    pw = (CW - 4 * 0.2) / 5
    for i, (t, c, diario) in enumerate(paginas):
        x = MX + i * (pw + 0.2)
        d.tarjeta(x, 2.65, pw, 2.75, TINTE if diario else TINTE_2, None if diario else GRIS_CLARO)
        d.ovalo(x + 0.2, 2.85, 0.5, str(i + 1), size=18, fill=AZUL if diario else GRIS_EST)
        d.txt(x + 0.2, 3.5, pw - 0.4, 0.7, t, size=17, bold=True, color=AZUL, anchor="m")
        d.txt(x + 0.2, 4.25, pw - 0.4, 1.1, c, size=14)
    d.tarjeta(MX, 5.7, CW, 0.85, AZUL)
    d.txt(MX + 0.4, 5.7, CW - 0.8, 0.85, "Para el día a día alcanza con las dos primeras: Estado de la red y Equipos.",
          size=19, bold=True, color=BLANCO, anchor="m")

    # ---------------------------------------------------------------- 17. Estado de la red
    d.nueva("Página «Estado de la red»: el panorama de un vistazo", """
QUÉ DECIR: Esta es la pantalla para mirar primero. Tiene tres partes.
1) El panal: un hexágono por cada equipo monitoreado. Verde es que responde; rojo, que no responde. Si está todo verde, la red está bien.
2) Problemas por severidad: cuántos problemas hay abiertos de cada nivel de gravedad. Lo normal es que estén todos en cero.
3) El mapa de la red, con el estado de cada sitio. Lo vemos en detalle en la diapositiva siguiente.
Más abajo, fuera del recorte, está la lista «Alertas activas» con los problemas abiertos y los recién resueltos.
QUÉ MOSTRAR: la página real. Preguntá: «¿está todo bien ahora?, ¿cómo te das cuenta?».
ACLARACIÓN: en el panal, «Activo (1)» significa que el equipo respondió al último ping y «Caído (0)» que no respondió.
FUENTE: manual de administración (Página «Estado de la red»). Captura del laboratorio.
""")
    f = d.imagen("estado", MX, 1.55, 7.45, 5.2, recorte=(0, 40, 2328, 1640), alt="Página Estado de la red con el panal de equipos, los problemas por severidad y el mapa",
                 alinear="l")
    d.marca(f, 640, 130, 1)
    d.marca(f, 640, 952, 2)
    d.marca(f, 1010, 130, 3)
    d.leyenda(8.4, 1.75, ANCHO - MX - 8.4, [
        ("Panal", "Un hexágono por equipo: verde responde, rojo no responde."),
        ("Problemas por severidad", "Cuántos hay abiertos de cada gravedad."),
        ("Mapa", "Dónde está cada sitio y cómo se conecta.")], size=16, paso=1.15)
    d.tarjeta(8.4, 5.3, ANCHO - MX - 8.4, 1.3)
    d.txt(8.65, 5.3, ANCHO - MX - 8.9, 1.3, [[("Todo verde y todo en cero: ", {"b": True, "c": AZUL}), "la red está bien."]],
          size=17, anchor="m")

    # ---------------------------------------------------------------- 18. Mapa
    d.nueva("El mapa usa las mismas líneas que el esquema de la red", """
QUÉ DECIR: El mapa del sistema está dibujado con la misma convención que el gráfico de la red que ya conocemos.
LÍNEAS: llena y verde es un tramo operativo; de rayas naranjas, un tramo en proceso; de puntos grises, un tramo sin configurar.
LA CAPTURA muestra una parte del mapa, ampliada para que se lea; el mapa completo está en la diapositiva anterior y en el sistema.
ÍCONOS: debajo de cada sitio dice «OK» en verde si no tiene problemas. Si un equipo cae, su ícono se marca en rojo, aparece el nombre del problema y el enlace hacia su padre se pinta rojo y grueso. Los sitios con fondo gris y la palabra «Disabled» todavía no se monitorean porque su tramo no está en servicio: no es una falla.
QUÉ MOSTRAR: hacé clic sobre un sitio en el mapa real y mostrá el menú que aparece, con el acceso al detalle del equipo y a sus problemas.
ACTIVIDAD RÁPIDA: que cada participante ubique su casa y diga si su tramo está operativo, en proceso o sin configurar.
FUENTE: lagunitas/model.py (estados y tipos de línea) y manual de administración. Captura del laboratorio, que incluye además un punto de acceso UniFi real de prueba («AP U7 Pro Wall»).
""")
    d.imagen("mapa", MX, 1.55, 6.9, 5.2, recorte=(60, 200, 1470, 1310), alt="Parte del mapa de topología de la red en el sistema",
             alinear="l")
    x = 7.85
    filas = [(VERDE, False, "Línea llena", "Tramo operativo: se monitorea."), (AMBAR, True, "Línea de rayas", "Tramo en proceso."),
             (GRIS_EST, True, "Línea de puntos", "Tramo sin configurar.")]
    for i, (c, dis, t, e) in enumerate(filas):
        y = 1.75 + i * 0.82
        ln = d.linea(x, y + 0.2, x + 0.9, y + 0.2, c, 3.0, discontinua=dis)
        if i == 2:
            ln.line.dash_style = MSO_LINE.ROUND_DOT
        d.txt(x + 1.15, y - 0.12, 3.7, 0.36, t, size=17, bold=True, color=AZUL)
        d.txt(x + 1.15, y + 0.24, 3.7, 0.36, e, size=15)
    d.linea(x, 4.2, ANCHO - MX, 4.2, GRIS_CLARO, 0.75)
    for i, (c, borde, t, e) in enumerate([(VERDE, None, "OK en verde", "El equipo no tiene problemas."),
                                          (ROJO, None, "Rojo", "Cayó. Su enlace se pinta rojo."),
                                          (GRIS_NOMON, None, "Gris, «Disabled»", "Aún no se monitorea. No es falla.")]):
        y = 4.45 + i * 0.78
        d.tarjeta(x + 0.2, y, 0.5, 0.42, c, radio=0.06)
        d.txt(x + 1.15, y - 0.14, 3.7, 0.36, t, size=17, bold=True, color=AZUL)
        d.txt(x + 1.15, y + 0.22, 3.7, 0.36, e, size=15)

    # ---------------------------------------------------------------- 19. Página Equipos
    d.nueva("Página «Equipos»: la lista completa", """
QUÉ DECIR: La segunda página es la lista de todos los equipos, ordenados por tipo: el gateway, las torres, los nodos y los hogares e instituciones.
1) Las tarjetas de arriba son el resumen: total de equipos, cuántos están en línea, con advertencias, caídos, sin servicio, sin datos y no monitoreados. Si hacés clic en una tarjeta, la lista muestra solo esos equipos.
2) El buscador sirve para encontrar un equipo por nombre, por dirección o por modelo.
3) Los filtros rápidos muestran solo los caídos, solo las torres, etcétera.
4) Cada fila es un equipo. Las filas con problemas aparecen primero.
QUÉ MOSTRAR: escribí «Escuela» en el buscador. Después hacé clic en la tarjeta «No monitoreados» y explicá que son tramos que todavía no están en servicio.
LECTURA DE LA CAPTURA (laboratorio): 33 equipos cargados, 21 en línea y 12 no monitoreados. La cuenta incluye las antenas y routers secundarios de cada sitio.
FUENTE: manual de administración (Página «Equipos»). Captura del laboratorio.
""")
    f = d.imagen("equipos", MX, 1.5, CW, 4.3, recorte=(0, 98, 2328, 921), alt="Página Equipos con tarjetas de resumen, buscador, filtros y tabla por rol")
    d.marca(f, 420, 128, 1)
    d.marca(f, 500, 268, 2)
    d.marca(f, 1150, 268, 3)
    d.marca(f, 245, 660, 4)
    items = [("Tarjetas de resumen", "un clic filtra la lista"), ("Buscador", "por nombre o dirección"),
             ("Filtros rápidos", "por estado o por tipo"), ("Una fila por equipo", "los problemas, primero")]
    lw = CW / 4
    for i, (t, c) in enumerate(items):
        x = MX + i * lw
        d.ovalo(x, 6.0, 0.42, str(i + 1), size=15)
        d.txt(x + 0.55, 5.93, lw - 0.65, 0.34, t, size=15, bold=True, color=AZUL)
        d.txt(x + 0.55, 6.27, lw - 0.65, 0.34, c, size=13, color=GRIS)

    # ---------------------------------------------------------------- 20. Cómo leer una fila
    d.nueva("Cómo leer una fila de la lista", f"""
QUÉ DECIR: Cada fila se lee de izquierda a derecha, como una ficha resumida.
ESTADO: el color y la palabra que resumen cómo está el equipo. EQUIPO: su nombre, su dirección en la red y el modelo. DISPONIBILIDAD 24 H: qué parte del último día estuvo respondiendo.
LATENCIA: cuánto tarda en responder. PÉRDIDA: qué parte de las respuestas no llegó. ENLACE / ENERGÍA: en las antenas, la señal y la calidad del enlace; en el gateway, el voltaje y los clientes conectados. DEPENDE DE: su padre. PROBLEMAS: si tiene alguno abierto.
QUÉ MOSTRAR: en la captura, El Carrizal no tiene dato de enlace porque en esa torre el equipo cargado es un router airCube, que solo responde al ping. Ex Aserradero muestra -58 dBm y CCQ 96 %.
ACLARACIÓN: los valores de latencia de la captura (0,1 ms) son de laboratorio, donde todo está en la misma máquina. En la red real son mayores; el sistema avisa cuando el promedio de 5 minutos pasa los {u['latencia_ms']} ms.
FUENTE: manual de administración (Página «Equipos»); umbral en lagunitas/templates.py. Captura del laboratorio.
""")
    d.imagen("equipos", MX, 1.5, CW, 1.95, recorte=(16, 579, 1094, 766), alt="Primera mitad de una fila: estado, equipo y disponibilidad de 24 horas",
             alinear="l")
    d.imagen("equipos", MX, 4.05, CW, 1.75, recorte=(1094, 579, 2328, 766), alt="Segunda mitad de la fila: latencia, pérdida, enlace o energía, depende de y problemas",
             alinear="l")
    d.txt(MX, 3.48, CW, 0.45, [[("Estado", {"b": True, "c": AZUL}), ": cómo está.   ", ("Equipo", {"b": True, "c": AZUL}),
                                ": nombre, dirección y modelo.   ", ("Disponibilidad 24 h", {"b": True, "c": AZUL}),
                                ": cuánto respondió en el último día."]], size=15)
    d.txt(MX, 5.9, CW, 0.85, [[("Latencia", {"b": True, "c": AZUL}), ": cuánto tarda.   ", ("Pérdida", {"b": True, "c": AZUL}),
                               ": cuánto no llega.   ", ("Enlace / energía", {"b": True, "c": AZUL}), ": señal o voltaje.   ",
                               ("Depende de", {"b": True, "c": AZUL}), ": su padre.   ", ("Problemas", {"b": True, "c": AZUL}), ": los abiertos."]],
          size=15)

    # ---------------------------------------------------------------- 21. Estados
    d.nueva("Seis estados posibles y qué hacer con cada uno", """
QUÉ DECIR: Cada equipo está siempre en uno de estos seis estados. Lo más importante es la diferencia entre los dos del medio.
CAÍDO (rojo): el equipo no responde y es el origen del problema. Ahí hay que actuar.
SIN SERVICIO (naranja): el equipo no responde, pero porque cayó otro del que depende. El sistema dice cuál («por Unión de los Ríos»). No hay que ir a revisar ese equipo, sino el que causó el corte.
ADVERTENCIA (amarillo): responde, pero mal: se pierden respuestas, tarda mucho o tiene otro aviso leve. Conviene mirarlo antes de que empeore.
SIN DATOS (gris): el sistema no recibe mediciones nuevas hace más de 5 minutos. Suele ser un problema del propio sistema de medición, no del equipo. Se avisa a quien administra.
NO MONITOREADO (gris claro): el tramo todavía no está en servicio, o el equipo está en mantenimiento programado. No es una falla.
PREGUNTA: «Mi casa aparece en naranja, Sin servicio. ¿Tengo que reiniciar mi router?» (No: el problema está más arriba).
FUENTE: manual de administración (Significado de los estados) y zabbix/modules/lagunitas-red/includes/RedService.php (regla de «Sin datos»: 300 s).
""")
    estados = [("En línea", VERDE, BLANCO, "Responde y no tiene problemas.", "Nada."),
               ("Advertencia", AMBAR, TEXTO, "Responde, pero con pérdida o latencia altas.", "Mirar la ficha del equipo."),
               ("Caído", ROJO, BLANCO, "No responde. Es el origen del problema.", "Atender: seguir los 5 pasos."),
               ("Sin servicio", NARANJA, BLANCO, "No responde porque cayó un equipo del que depende.", "Atender la causa, no este equipo."),
               ("Sin datos", GRIS_EST, BLANCO, "El sistema no recibe mediciones hace más de 5 minutos.", "Avisar a quien administra."),
               ("No monitoreado", GRIS_NOMON, TEXTO, "Tramo que aún no está en servicio, o en mantenimiento.", "Nada.")]
    d.txt(MX + 2.6, 1.42, 5.9, 0.3, "QUÉ SIGNIFICA", size=12, bold=True, color=GRIS)
    d.txt(9.3, 1.42, 3.4, 0.3, "QUÉ HACER", size=12, bold=True, color=GRIS)
    for i, (n, c, ct, s, a) in enumerate(estados):
        y = 1.78 + i * 0.83
        d.tarjeta(MX, y, CW, 0.72, TINTE_2 if i % 2 else TINTE)
        d.chip(MX + 0.12, y + 0.11, 2.25, 0.5, n, c, ct, size=16)
        d.txt(MX + 2.6, y, 6.4, 0.72, s, size=16, anchor="m")
        d.txt(9.3, y, 3.3, 0.72, a, size=16, bold=True, color=AZUL, anchor="m")

    # ---------------------------------------------------------------- 22. Severidades
    d.nueva("La gravedad de un problema también tiene color", f"""
QUÉ DECIR: Cuando el sistema detecta algo, abre un «problema» y le pone una gravedad, que en pantalla aparece en inglés. Son cinco niveles; de arriba hacia abajo, del más grave al más leve.
DISASTER: se cortó la conexión de la red con Internet. Afecta a todos.
HIGH: un equipo dejó de responder, o la batería del gateway está en un nivel crítico.
AVERAGE: algo serio pero parcial: la señal de un enlace está al borde de cortarse, una antena dejó de dar datos o se quedó sin equipos conectados.
WARNING: algo se está degradando: señal débil, interferencia, se pierden respuestas, la batería está bajando.
INFORMATION: solo para saber: un equipo se reinició o cambió de versión.
REGLA PARA RECORDAR: por Telegram llegan únicamente los problemas de gravedad Average o mayor. Los Warning y los Information se ven en el tablero, pero no suenan en el celular. Por eso conviene mirar el tablero cada tanto aunque no haya llegado ningún aviso.
FUENTE: severidades en lagunitas/templates.py y lagunitas/templates_snmp.py; regla de notificación en lagunitas/alerts.py (severidad mínima 3 = Average).
""")
    niveles = [("Disaster", "Desastre", "Toda la red sin conexión a Internet.", True),
               ("High", "Alta", "Un equipo no responde. Voltaje crítico en el gateway.", True),
               ("Average", "Media", "Señal crítica. Una antena sin datos o sin equipos conectados.", True),
               ("Warning", "Advertencia", "Señal débil, interferencia, pérdida, latencia, voltaje bajo.", False),
               ("Information", "Información", "Un equipo se reinició o cambió de versión.", False)]
    d.txt(MX + 3.0, 1.42, 6.0, 0.3, "EJEMPLOS", size=12, bold=True, color=GRIS)
    d.txt(10.35, 1.42, 2.4, 0.3, "¿AVISA POR TELEGRAM?", size=12, bold=True, color=GRIS, align="c")
    for i, (en, es, ej, tg) in enumerate(niveles):
        y = 1.78 + i * 0.86
        d.tarjeta(MX, y, CW, 0.75, TINTE_2 if i % 2 else TINTE)
        d.chip(MX + 0.12, y + 0.12, 1.55, 0.51, en, SEV[en], TEXTO, size=15)
        d.txt(MX + 1.8, y, 1.2, 0.75, es, size=13, color=GRIS, anchor="m")
        d.txt(MX + 3.0, y, 6.6, 0.75, ej, size=16, anchor="m")
        d.chip(10.8, y + 0.14, 1.5, 0.47, "Sí" if tg else "No", AZUL if tg else BLANCO, BLANCO if tg else GRIS, size=15,
               linea=None if tg else GRIS_CLARO)
    d.tarjeta(MX, 6.12, CW, 0.62, AZUL)
    d.txt(MX + 0.3, 6.12, CW - 0.6, 0.62, "Por Telegram solo llega lo que es Average o más grave. Lo demás se ve en el tablero.",
          size=17, bold=True, color=BLANCO, anchor="m")

    # ================================================================ BLOQUE 4
    d.seccion(4, "La ficha de un equipo", "10 minutos", "Cómo leer la señal, la latencia, la pérdida y la batería", """
QUÉ DECIR: Con un clic sobre cualquier equipo de la lista se abre su ficha. En este bloque aprendemos a leer los cuatro números que más importan.
SUGERENCIA: este es un buen momento para una pausa corta al terminar el bloque.
""")

    # ---------------------------------------------------------------- 24. Ficha
    d.nueva("Un clic sobre un equipo abre su ficha", """
QUÉ DECIR: En la página Equipos, al hacer clic sobre una fila se abre esta ventana. Arriba a la derecha está el estado. La pestaña Resumen muestra los números principales en tarjetas y, debajo, los datos del equipo: qué modelo es, de quién depende, si está en mantenimiento.
PESTAÑAS: las que aparecen dependen del tipo de equipo. Una antena tiene Radio y Estaciones; el gateway tiene «Router y energía». Todos tienen Problemas, Rendimiento (gráficos), Dependencias e Interfaces.
QUÉ MOSTRAR: abrí la ficha de Unión de los Ríos y recorré las pestañas. En Rendimiento, cambiá el período de 24 horas a 7 días para ver cómo se comportó en la semana.
COLORES DE LOS NÚMEROS: verde es que el valor está dentro de lo normal.
FUENTE: manual de administración (clic en un equipo abre su detalle). Captura del laboratorio.
""")
    f = d.imagen("ficha", MX, 1.55, 8.3, 4.6, alt="Ficha de la torre Unión de los Ríos, pestaña Resumen", alinear="l")
    d.marca(f, 1420, 50, 1)
    d.marca(f, 655, 122, 2)
    d.marca(f, 1640, 300, 3)
    d.marca(f, 1300, 762, 4)
    d.leyenda(9.25, 1.6, ANCHO - MX - 9.25, [
        ("Estado", "Cómo está en este momento."),
        ("Pestañas", "Cambian según el tipo de equipo."),
        ("Tarjetas", "Los números principales."),
        ("Datos", "Modelo, padre y mantenimiento.")], size=15, paso=1.02)
    d.txt(MX, 6.25, 8.3, 0.4, "Ficha de la torre Unión de los Ríos (laboratorio).", size=12, color=GRIS)

    # ---------------------------------------------------------------- 25. Latencia y pérdida
    d.nueva("Latencia y pérdida: cuánto tarda y cuánto no llega", f"""
QUÉ DECIR: Son los dos números que se miden en todos los equipos, con el mismo ping.
LATENCIA: el tiempo que tarda el equipo en contestar, en milisegundos (milésimas de segundo). Es como gritar de un cerro a otro y contar cuánto tarda la respuesta. Cuanto más baja, mejor. El sistema avisa (Warning) cuando el promedio de 5 minutos supera los {u['latencia_ms']} milisegundos.
PÉRDIDA: de cada 100 preguntas, cuántas quedaron sin respuesta. Es como una conversación con viento, donde se pierden palabras. Lo ideal es 0 %. El sistema avisa (Warning) cuando la pérdida se mantiene por encima del {u['perdida']} % durante 5 minutos seguidos.
CUANDO LA PÉRDIDA ES 100 %: el equipo ya no responde nada y el estado pasa a Caído o Sin servicio.
QUÉ SE NOTA EN CASA: con latencia o pérdida altas las videollamadas se cortan y las páginas tardan, aunque «haya Internet».
PRECISIÓN PARA EL JURADO: latencia alta = avg(icmppingsec, 5m) > {u['latencia_ms']} ms; pérdida alta = min(icmppingloss, 5m) > {u['perdida']} % y menor que 100 %.
FUENTE: lagunitas/templates.py (macros ICMP.LATENCIA.WARN e ICMP.PERDIDA.WARN).
""")
    for i, (t, an, que, n, un, cu) in enumerate([
        ("Latencia", "Como gritar de un cerro a otro y contar cuánto tarda la respuesta.", "Cuanto más baja, mejor.",
         f"{u['latencia_ms']} ms", "milisegundos", "El sistema avisa si el promedio de 5 minutos supera"),
        ("Pérdida", "Como hablar con viento: de cada 100 palabras, cuántas no llegan.", "Lo ideal es 0 %.",
         f"{u['perdida']} %", "de las respuestas", "El sistema avisa si durante 5 minutos seguidos se pierde más del")]):
        x = MX + i * (CW / 2 + 0.15)
        w = CW / 2 - 0.15
        d.tarjeta(x, 1.6, w, 4.95)
        d.txt(x + 0.4, 1.8, w - 0.8, 0.55, t, size=26, bold=True, color=AZUL)
        d.txt(x + 0.4, 2.45, w - 0.8, 0.95, an, size=17)
        d.txt(x + 0.4, 3.4, w - 0.8, 0.4, que, size=17, bold=True, color=AZUL)
        d.tarjeta(x + 0.4, 4.0, w - 0.8, 2.25, BLANCO)
        d.txt(x + 0.6, 4.12, w - 1.2, 0.75, cu, size=14, color=GRIS, anchor="m")
        d.txt(x + 0.6, 4.9, w - 1.2, 0.85, n, size=44, bold=True, color=AZUL, anchor="m")
        d.txt(x + 0.6, 5.75, w - 1.2, 0.4, "Gravedad: Warning. Se ve en el tablero.", size=13, color=GRIS)

    # ---------------------------------------------------------------- 26. Señal
    d.nueva("Señal de radio: cuanto más cerca de cero, mejor", f"""
QUÉ DECIR: La señal dice con cuánta fuerza una antena escucha a la otra. Se mide en dBm y siempre es un número negativo. La regla es simple: cuanto más cerca de cero, más fuerte. Menos 60 es mejor que menos 80.
ANALOGÍA: es como escuchar a alguien que habla desde lejos. Si se aleja, hay árboles en el medio o la antena se movió con el viento, se escucha más bajo.
VALORES DE REFERENCIA: entre -50 y -65 dBm la señal es buena; entre -65 y {u['senal_warn']} es aceptable.
CUÁNDO AVISA EL SISTEMA: si el promedio de 10 minutos baja de {u['senal_warn']} dBm abre un problema «señal débil» (Warning, se ve en el tablero). Si baja de {u['senal_crit']} dBm abre «señal crítica» (Average, llega por Telegram): el enlace está al borde de cortarse.
OTROS NÚMEROS DE LA PESTAÑA RADIO: el CCQ es el porcentaje de transmisiones que salen bien al primer intento; avisa por debajo de {u['ccq']} %. El piso de ruido mide la interferencia; avisa por encima de {u['ruido']} dBm. El SNR es la diferencia entre señal y ruido; avisa por debajo de {u['snr']} dB. Los tres son Warning y usan el promedio de 15 minutos.
CAUSAS HABITUALES DE SEÑAL BAJA: antena desalineada por el viento, vegetación que creció en la línea entre antenas, problemas en el otro extremo.
ENLACES LARGOS: quien administra puede ajustar el umbral para un equipo cuyo enlace es naturalmente más débil.
FUENTE: umbrales en lagunitas/templates_snmp.py (macros AIRMAX.*); rangos de referencia en el manual de administración (Cómo leer las métricas de radio y energía). Captura del laboratorio.
""")
    d.imagen("radio", MX, 1.5, CW, 1.72, recorte=(0, 140, 1683, 275), alt="Tarjetas de la pestaña Radio: señal, piso de ruido, SNR, CCQ, calidad y capacidad airMAX")
    # escala de señal: de -50 a -90 dBm
    ex, ew, ey, eh = MX, CW, 3.95, 0.62
    def pos(v: float) -> float:
        return ex + (v - (-50)) / (-90 - (-50)) * ew
    sw, sc = float(u["senal_warn"]), float(u["senal_crit"])
    tramos = [(-50, -65, VERDE, BLANCO, "Buena"), (-65, sw, "8BC34A", TEXTO, "Aceptable"), (sw, sc, AMBAR, TEXTO, "Débil"),
              (sc, -90, ROJO, BLANCO, "Crítica")]
    for a, b, c, ct, t in tramos:
        s = d._forma(MSO_SHAPE.RECTANGLE, pos(a), ey, pos(b) - pos(a), eh, c)
        d._texto_forma(s, t, 16, ct)
    for v in (-50, -65, sw, sc, -90):
        etiqueta = f"{int(v)}"
        xe = pos(v) if v == -50 else pos(v) - 1.2 if v == -90 else pos(v) - 0.6
        d.txt(xe, ey + eh + 0.06, 1.2, 0.32, etiqueta, size=15, bold=True, color=AZUL,
              align="l" if v == -50 else "r" if v == -90 else "c")
    d.txt(MX, ey - 0.42, 6, 0.34, "Señal recibida, en dBm", size=14, bold=True, color=GRIS)
    d.txt(ANCHO - MX - 6, ey - 0.42, 6, 0.34, "más lejos de cero: peor", size=14, color=GRIS, align="r")
    d.tarjeta(MX, 5.3, 5.95, 1.3)
    d.txt(MX + 0.3, 5.3, 5.4, 1.3, [[("Señal débil", {"b": True, "c": AZUL}), f": promedio de 10 min por debajo de {u['senal_warn']} dBm. Warning."],
                                    [("Señal crítica", {"b": True, "c": AZUL}), f": por debajo de {u['senal_crit']} dBm. Average, llega por Telegram."]],
          size=14, anchor="m", esp=5)
    d.tarjeta(6.8, 5.3, ANCHO - MX - 6.8, 1.3, TINTE_2, GRIS_CLARO)
    d.txt(7.1, 5.3, ANCHO - MX - 7.4, 1.3, [[("También avisa", {"b": True, "c": AZUL}), f" (Warning) si el CCQ baja de {u['ccq']} %, "
                                             f"el ruido sube de {u['ruido']} dBm o el SNR baja de {u['snr']} dB."]], size=14, anchor="m")

    # ---------------------------------------------------------------- 27. Batería
    d.nueva("Batería: el voltaje dice cuánta carga queda", f"""
QUÉ DECIR: El router Mikrotik informa con cuántos voltios se está alimentando. Si se alimenta de la batería del nodo, ese número indica cómo está la batería. Se ve en la ficha del gateway, pestaña «Router y energía».
VALORES DE REFERENCIA de una batería de 12 V como las de la red, en reposo: 12,7 V es batería llena; 12,2 V es aproximadamente la mitad; por debajo de 11,8 V la descarga es profunda y la batería se daña.
CUÁNDO AVISA EL SISTEMA: «voltaje bajo» (Warning, se ve en el tablero) si el promedio de 10 minutos baja de {u['v_warn']} V. «Voltaje crítico» (High, llega por Telegram) si el promedio de 5 minutos baja de {u['v_crit']} V: el nodo está por apagarse. «Voltaje excesivo» (Average, llega por Telegram) si el promedio de 10 minutos supera {u['v_max']} V: puede estar fallando el regulador de carga.
QUÉ HACER: mirar si el panel está sucio o tiene sombra, si hubo varios días nublados, y avisar al referente técnico. No desconectar la batería ni el regulador.
OTRA PISTA: un aviso de «el equipo se reinició» de madrugada, repetido, suele indicar que la batería no llega al amanecer.
LÍMITE: de día, con sol, el voltaje sube porque el panel está cargando; el dato más útil es el de la noche y la madrugada.
PRECISIÓN PARA EL JURADO: el voltaje sale del OID de salud de RouterOS (mtxrHlVoltage) por SNMP; es una medición indirecta del estado de carga.
FUENTE: umbrales en lagunitas/templates_snmp.py (macros MIKROTIK.VOLTAJE.*); referencia de carga en la guía de integración de equipos y en la propia ficha del gateway. Captura del laboratorio.
""")
    d.imagen("router", MX, 1.5, CW, 1.72, recorte=(0, 140, 1683, 275), alt="Tarjetas de la pestaña Router y energía: voltaje, CPU, memoria, temperatura, clientes DHCP e Internet")
    ey = 3.95
    vmin, vmax = 11.0, 15.4
    def posv(v: float) -> float:
        return ex + (v - vmin) / (vmax - vmin) * ew
    vw, vc, vm = (float(u[k].replace(",", ".")) for k in ("v_warn", "v_crit", "v_max"))
    for a, b, c, ct, t in [(vmin, vc, ROJO, BLANCO, "Crítico"), (vc, vw, AMBAR, TEXTO, "Bajo"), (vw, vm, VERDE, BLANCO, "Normal"),
                           (vm, vmax, NARANJA, BLANCO, "Excesivo")]:
        s = d._forma(MSO_SHAPE.RECTANGLE, posv(a), ey, posv(b) - posv(a), eh, c)
        d._texto_forma(s, t, 15, ct)
    d.txt(posv(vc) - 0.5, ey + eh + 0.06, 1.0, 0.32, f"{u['v_crit']} V", size=15, bold=True, color=AZUL, align="c")
    d.txt(posv(vw) - 0.5, ey + eh + 0.06, 1.0, 0.32, f"{u['v_warn']} V", size=15, bold=True, color=AZUL, align="c")
    d.txt(posv(vm) - 0.6, ey + eh + 0.06, 1.2, 0.32, f"{u['v_max']} V", size=15, bold=True, color=AZUL, align="c")
    d.txt(MX, ey - 0.42, 8, 0.34, "Voltaje de alimentación del router Mikrotik", size=14, bold=True, color=GRIS)
    d.tarjeta(MX, 5.3, 5.95, 1.3)
    d.txt(MX + 0.3, 5.3, 5.4, 1.3, [[("Voltaje bajo", {"b": True, "c": AZUL}), f": menos de {u['v_warn']} V. Warning, se ve en el tablero."],
                                    [("Voltaje crítico", {"b": True, "c": AZUL}), f": menos de {u['v_crit']} V. High, llega por Telegram."]],
          size=14, anchor="m", esp=5)
    d.tarjeta(6.8, 5.3, ANCHO - MX - 6.8, 1.3, TINTE_2, GRIS_CLARO)
    d.txt(7.1, 5.3, ANCHO - MX - 7.4, 1.3, [[("Referencia", {"b": True, "c": AZUL}), " de una batería de 12 V en reposo: 12,7 V llena, "
                                             "12,2 V a la mitad, menos de 11,8 V descarga profunda."]], size=14, anchor="m")

    # ---------------------------------------------------------------- 28. Dependencias
    d.nueva("Pestaña Dependencias: a quién afecta este equipo", """
QUÉ DECIR: Esta pestaña responde dos preguntas. Arriba, «Camino hacia el backbone»: por qué equipos pasa la conexión de este equipo hasta llegar al gateway. Abajo, «Si este equipo cae, quedan sin servicio»: la lista de todos los que dependen de él.
PARA QUÉ SIRVE: ante una caída, es la forma más rápida de saber a cuántos vecinos afecta y a quiénes conviene avisar.
QUÉ MOSTRAR: abrí Dependencias en Unión de los Ríos y después en la casa de algún participante. En una casa, el camino es largo y la lista de abajo está vacía o tiene solo su router.
LECTURA DE LA CAPTURA (laboratorio): de Unión de los Ríos dependen 30 equipos. La cuenta incluye las antenas y routers secundarios de cada sitio y también los tramos todavía no monitoreados.
FUENTE: manual de administración (pestaña Dependencias). Captura del laboratorio.
""")
    f = d.imagen("dependencias", MX, 1.55, 7.9, 4.75, recorte=(0, 0, 1683, 1010), alt="Pestaña Dependencias de Unión de los Ríos: camino hacia el backbone y equipos que quedan sin servicio",
                 alinear="l")
    d.marca(f, 420, 170, 1)
    d.marca(f, 560, 325, 2)
    d.leyenda(8.9, 1.75, ANCHO - MX - 8.9, [
        ("Camino hacia el backbone", "Por dónde pasa su conexión hasta el gateway."),
        ("Si este equipo cae", "Todos los equipos que quedarían sin servicio.")], size=16, paso=1.35)
    d.tarjeta(8.9, 4.6, ANCHO - MX - 8.9, 1.7)
    d.txt(9.15, 4.6, ANCHO - MX - 9.4, 1.7, "Ante una caída, acá se ve a cuántos vecinos afecta y a quiénes avisar.", size=17, bold=True,
          color=AZUL, anchor="m")

    # ================================================================ BLOQUE 5
    d.seccion(5, "Alarmas", "20 minutos", "Qué hacer cuando llega un aviso, paso a paso, y cuatro casos típicos", """
QUÉ DECIR: Este es el bloque más importante. Vamos a ver qué hacer cuando llega un aviso, cómo leer el mensaje de Telegram y cuatro situaciones que van a pasar tarde o temprano.
IDEA PARA REPETIR: no hace falta resolver el problema uno mismo; hace falta entender qué pasó, saber si es grave y avisar a la persona correcta con buena información.
""")

    # ---------------------------------------------------------------- 30. Telegram
    d.nueva("Así llega una alarma por Telegram", f"""
QUÉ DECIR: Las alarmas llegan al grupo de Telegram «Operadores Las Lagunitas». El mensaje con el círculo rojo avisa un problema. Se lee así: primero la gravedad (High), después el equipo y qué le pasa («Nodo Kika: sin respuesta (ICMP)», es decir, no contesta el ping). Debajo, el estado («Caído»), el nombre y la dirección del equipo, y la fecha y hora de inicio.
Cuando el equipo vuelve, llega un segundo mensaje con la tilde verde, «Resuelto», como respuesta al primero, con cuánto duró el problema. En el ejemplo, un minuto y medio.
REGLAS: 1) Solo llegan los problemas de gravedad Average o mayor. 2) Si el problema sigue abierto, el aviso se repite una vez, a los {u['repite']} minutos. 3) Siempre se avisa cuando se resuelve. 4) Durante un mantenimiento programado no se envían avisos.
MUY IMPORTANTE: el bot solo envía. No lee ni contesta lo que se le escriba, así que no sirve responderle. Para coordinar, escriban en el grupo entre personas.
SI APARECE UN MENSAJE RARO que no parece una alarma, avisar a quien administra: puede haberse filtrado la clave del bot.
PARA SUMAR A ALGUIEN A LAS ALARMAS: alcanza con agregarlo al grupo de Telegram; lo hace un administrador del grupo.
FUENTE: lagunitas/alerts.py (plantillas del mensaje, repetición a los {u['repite']} min, severidad mínima Average) y guía de implementación (Seguridad del bot de Telegram). Captura de la prueba de laboratorio (informe, sección Validación).
""")
    f = d.imagen("telegram", MX, 1.55, 7.0, 3.5, alt="Mensajes del bot en el grupo de Telegram: aviso de problema y aviso de resuelto", alinear="l")
    d.marca(f, 30, 110, 1)
    d.marca(f, 30, 165, 2)
    d.marca(f, 30, 258, 3)
    d.leyenda(8.05, 1.6, ANCHO - MX - 8.05, [
        ("Qué pasó", "Gravedad, equipo y problema."),
        ("Dónde y cuándo", "Estado, dirección y hora de inicio."),
        ("Resuelto", "Llega solo cuando el equipo vuelve, con la duración.")], size=16, paso=1.15)
    reglas = [("Solo lo importante", "Gravedad Average o mayor"), ("Recordatorio", f"Una vez, a los {u['repite']} minutos"),
              ("Aviso de resuelto", "Cuando el equipo vuelve"), ("El bot solo envía", "No lee ni responde mensajes")]
    rw = (CW - 3 * 0.2) / 4
    for i, (t, c) in enumerate(reglas):
        x = MX + i * (rw + 0.2)
        d.tarjeta(x, 5.35, rw, 1.25, AZUL if i == 3 else TINTE)
        d.txt(x + 0.2, 5.45, rw - 0.4, 0.5, t, size=17, bold=True, color=BLANCO if i == 3 else AZUL, anchor="m")
        d.txt(x + 0.2, 5.95, rw - 0.4, 0.55, c, size=14, color="D6E0EC" if i == 3 else TEXTO)

    # ---------------------------------------------------------------- 31. Cinco pasos
    d.nueva("Qué hacer ante una alarma: cinco pasos", """
QUÉ DECIR: Este es el procedimiento para cualquier alarma. Conviene tenerlo impreso junto a la computadora.
1) LEER el mensaje completo: qué equipo es y qué gravedad tiene. No actuar con solo ver la notificación.
2) MIRAR el tablero: en la página Equipos, buscar el equipo en rojo (Caído). Los naranjas (Sin servicio) son consecuencia y no hay que revisarlos.
3) MEDIR el impacto: abrir la ficha del equipo caído, pestaña Dependencias, y ver cuántos vecinos quedaron sin servicio.
4) AVISAR Y REVISAR: avisar al referente técnico con esos datos (qué equipo, desde cuándo, a cuántos afecta). Si alguien está cerca del sitio, revisar lo simple: si el equipo tiene energía, si hay luces encendidas, si el panel está limpio, si la antena se movió.
5) REGISTRAR: dejar anotado en el sistema lo que se hizo (el registro también se avisa al grupo de Telegram). En «Alertas activas», columna Update, opción Acknowledge, con un mensaje corto («Avisado a Fulano, se revisa mañana»). Así el resto sabe que alguien ya se ocupó. Cuando el equipo vuelve, el problema se cierra solo y llega el «Resuelto».
CAUSAS MÁS COMUNES EN ESTA RED: falta de energía (panel o batería), antena desalineada por el viento, equipo colgado que necesita un reinicio, corte de un enlace troncal.
ACLARACIÓN: registrar con Acknowledge no cierra el problema ni detiene las mediciones; solo deja constancia.
FUENTE: manual de administración (Qué hacer ante una caída).
""")
    pasos = [("Leer", "el mensaje completo: equipo y gravedad"), ("Mirar", "el tablero y buscar el equipo en rojo"),
             ("Medir", "a cuántos afecta, en Dependencias"), ("Avisar", "al referente y revisar lo simple en el sitio"),
             ("Registrar", "lo que se hizo, con Acknowledge")]
    pw = (CW - 4 * 0.22) / 5
    for i, (t, c) in enumerate(pasos):
        x = MX + i * (pw + 0.22)
        d.tarjeta(x, 1.65, pw, 3.1)
        d.ovalo(x + pw / 2 - 0.42, 1.9, 0.84, str(i + 1), size=32)
        d.txt(x + 0.15, 2.95, pw - 0.3, 0.5, t, size=22, bold=True, color=AZUL, align="c")
        d.txt(x + 0.18, 3.5, pw - 0.36, 1.15, c, size=15, align="c")
    d.tarjeta(MX, 5.05, CW, 1.5, TINTE_2, GRIS_CLARO)
    d.txt(MX + 0.35, 5.15, CW - 0.7, 0.4, "Causas más comunes en esta red", size=16, bold=True, color=AZUL)
    causas = ["Falta de energía: panel o batería", "Antena desalineada por el viento", "Equipo colgado: necesita reinicio", "Corte de un enlace troncal"]
    for i, c in enumerate(causas):
        d.chip(MX + 0.35 + i * 2.95, 5.68, 2.8, 0.66, c, BLANCO, TEXTO, size=13, linea=GRIS_CLARO, bold=False)

    # ---------------------------------------------------------------- 32. A quién avisar
    d.nueva("A quién avisar", """
QUÉ DECIR: Para que el procedimiento funcione, todos tienen que saber a quién llamar. Completen juntos estos datos y dejen la diapositiva impresa en un lugar visible.
QUIÉN ES QUIÉN: el referente técnico de la red es quien coordina los trabajos en torres y nodos. Quien administra el sistema de monitoreo se ocupa del sistema en sí: usuarios, equipos cargados, avisos que no llegan. El contacto de la Cooperativa de Alpa Corral es para cuando se corta la conexión de toda la red con Internet.
DATO A COMPLETAR: nombres y teléfonos. Este material no los trae cargados a propósito, para no difundir datos personales y porque pueden cambiar.
SUGERENCIA: definan también un reemplazo para cada rol.
""")
    contactos = [("Referente técnico de la red", "Caídas de torres o nodos, trabajos en sitio"),
                 ("Quien administra el monitoreo", "Usuarios, equipos «Sin datos», avisos que no llegan"),
                 ("Cooperativa de Alpa Corral", "Corte de la conexión de toda la red a Internet")]
    cw3 = (CW - 2 * 0.3) / 3
    for i, (t, c) in enumerate(contactos):
        x = MX + i * (cw3 + 0.3)
        d.tarjeta(x, 1.65, cw3, 3.75, BLANCO, AZUL, 1.5)
        d.txt(x + 0.3, 1.85, cw3 - 0.6, 0.75, t, size=19, bold=True, color=AZUL, anchor="m")
        d.txt(x + 0.3, 2.65, cw3 - 0.6, 0.75, c, size=14, color=GRIS)
        for j, campo in enumerate(["Nombre", "Teléfono"]):
            yy = 3.65 + j * 0.8
            d.txt(x + 0.3, yy, 1.2, 0.35, campo, size=13, color=GRIS)
            d.linea(x + 0.3, yy + 0.62, x + cw3 - 0.3, yy + 0.62, GRIS, 1.0)
    d.tarjeta(MX, 5.7, CW, 0.9)
    d.txt(MX + 0.35, 5.7, CW - 0.7, 0.9, [[("Para coordinar entre operadores: ", {"b": True, "c": AZUL}),
                                           "el grupo de Telegram «Operadores Las Lagunitas», donde también llegan las alarmas."]],
          size=16, anchor="m")

    # ---------------------------------------------------------------- 33. Caso 1a
    d.nueva("Caso 1. Se cae una torre: así se ve en el tablero", f"""
QUÉ DECIR: Este caso se probó en el laboratorio: se apagó la torre Unión de los Ríos, de la que depende casi toda la red.
QUÉ SE VE: 1) El panal se pone rojo: 19 equipos dejaron de responder. Solo quedan verdes el gateway y un punto de acceso de prueba que no depende de la torre. 2) En problemas por severidad hay un solo problema, de gravedad High. 3) En el mapa, la torre aparece marcada en rojo con el texto del problema, y su enlace hacia el gateway se pinta rojo.
LO QUE HAY QUE NOTAR: 19 equipos no responden, pero hay UN solo problema abierto y llegó UN solo aviso. El sistema ya hizo el diagnóstico: el problema está en Unión de los Ríos.
DETALLE DEL MAPA: los demás sitios siguen diciendo «OK» en verde porque el mapa marca en rojo solamente al equipo que originó la falla. El panal y la página Equipos muestran quiénes quedaron sin respuesta.
TIEMPOS: la alerta apareció alrededor de un minuto y medio después del corte (una torre se declara caída a los {caida_torre} segundos sin respuesta). Al volver a encender, el problema se cerró solo en segundos.
FUENTE: informe de la PPS, sección Validación (caída troncal simulada, 19 equipos, una única alerta High). Captura del laboratorio.
""")
    f = d.imagen("caida_estado", MX, 1.55, 7.45, 5.2, recorte=(0, 40, 2328, 1640), alt="Estado de la red durante la caída simulada de la torre Unión de los Ríos",
                 alinear="l")
    d.marca(f, 640, 130, 1)
    d.marca(f, 640, 952, 2)
    d.marca(f, 985, 800, 3)
    d.leyenda(8.4, 1.7, ANCHO - MX - 8.4, [
        ("Panal en rojo", "19 equipos dejaron de responder."),
        ("Un solo problema", "De gravedad High."),
        ("La torre, marcada en el mapa", "Con su enlace en rojo.")], size=16, paso=1.05)
    d.tarjeta(8.4, 4.95, ANCHO - MX - 8.4, 1.7, AZUL)
    d.txt(8.6, 5.05, ANCHO - MX - 8.8, 0.85, "1 alerta", size=40, bold=True, color=BLANCO, align="c", anchor="m")
    d.txt(8.6, 5.9, ANCHO - MX - 8.8, 0.65, "aunque 19 equipos no responden", size=16, color="D6E0EC", align="c")

    # ---------------------------------------------------------------- 34. Caso 1b
    d.nueva("Caso 1. Un equipo «Caído» y dieciocho «Sin servicio»", """
QUÉ DECIR: La misma caída vista en la página Equipos. Las tarjetas de arriba lo resumen: 1 caído y 18 sin servicio.
En la lista, Unión de los Ríos figura como «Caído» en rojo, con la marca «1 crítico» en la columna de problemas. Todos los demás figuran «Sin servicio» en naranja, y debajo de cada uno dice por qué: «por Unión de los Ríos».
APLICAR LOS CINCO PASOS: 1) Leer: High, Unión de los Ríos, sin respuesta. 2) Mirar: un rojo, el resto naranja. 3) Medir: en Dependencias, todos los vecinos de la red. 4) Avisar al referente técnico y, si alguien puede acercarse a la torre, revisar la energía. 5) Registrar con Acknowledge.
QUÉ NO HACER: reiniciar los routers de las casas ni ir a revisar los nodos en naranja. No tienen ninguna falla.
PREGUNTA: «¿Por qué la disponibilidad de 24 horas de casi todos sigue por encima de 99 %?» (Porque la caída recién empieza: el porcentaje baja a medida que pasa el tiempo).
FUENTE: informe de la PPS, sección Validación. Captura del laboratorio.
""")
    f = d.imagen("caida_equipos", MX, 1.5, CW, 4.45, recorte=(0, 98, 2328, 945), alt="Página Equipos durante la caída: una torre Caída y los demás equipos Sin servicio")
    d.recuadro(f, (1000, 155, 1668, 235))
    d.recuadro(f, (14, 622, 700, 705))
    d.tarjeta(MX, 6.1, CW, 0.62)
    d.txt(MX + 0.3, 6.1, CW - 0.6, 0.62, [[("Se atiende el rojo. ", {"b": True, "c": ROJO}),
                                           "Los naranjas dicen «por Unión de los Ríos»: se recuperan solos cuando vuelve la torre."]],
          size=17, anchor="m")

    # ---------------------------------------------------------------- 35. Caso 2
    d.nueva("Caso 2. Señal débil: no suena el celular, pero se mira", f"""
QUÉ DECIR: Este caso es distinto: nada se cayó, pero algo se está degradando. En la prueba de laboratorio se simularon tres degradaciones a la vez: señal débil en la antena de la casa de Walter, interferencia en el nodo Mesada y batería baja en el gateway.
QUÉ SE VE: en Monitoring, Problems aparecen los problemas abiertos, todos de gravedad Warning (amarillo): «Walter: señal débil», «Mesada: ruido alto en el canal», «Mesada: CCQ bajo», «Gateway Mikrotik: voltaje bajo».
LO IMPORTANTE: como son Warning, estos problemas NO llegan por Telegram. Solo se ven en el tablero: la tarjeta «Advertencias» de la página Equipos deja de estar en cero, y el equipo figura con estado Advertencia.
POR QUÉ IMPORTA: una señal débil hoy puede ser un enlace caído la semana que viene. Si la señal sigue bajando y pasa a «crítica» (por debajo de {u['senal_crit']} dBm), ahí sí llega el aviso.
QUÉ HACER: abrir la ficha del equipo, pestaña Radio, y anotar la señal. Mirar en Rendimiento desde cuándo viene bajando. Avisar al referente técnico sin urgencia. Causas típicas: la antena se movió con el viento o creció vegetación en el medio.
TIEMPOS: estos avisos tardaron entre 6 y 11 minutos en aparecer, porque usan promedios de 10 y 15 minutos. Es a propósito, para no alarmar por una variación de un momento.
HÁBITO RECOMENDADO: mirar el tablero una vez por día, o al menos un par de veces por semana, aunque no haya llegado ningún aviso.
FUENTE: informe de la PPS, sección Validación (escenarios de falla simulados por SNMP); severidades en lagunitas/templates_snmp.py. Captura del laboratorio.
""")
    d.imagen("problemas", MX, 1.5, CW, 2.75, recorte=(17, 17, 1300, 349), alt="Lista de problemas de gravedad Warning: señal débil, ruido alto, CCQ bajo y voltaje bajo",
             alinear="l")
    tres = [("Qué pasa", "La antena de Walter recibe poca señal. Todavía funciona."), ("Cómo me entero", "Solo en el tablero: es Warning y no llega por Telegram."),
            ("Qué hago", "Anoto la señal, miro desde cuándo baja y aviso al referente.")]
    tw = (CW - 2 * 0.25) / 3
    for i, (t, c) in enumerate(tres):
        x = MX + i * (tw + 0.25)
        d.tarjeta(x, 4.55, tw, 2.05, AZUL if i == 1 else TINTE)
        d.txt(x + 0.3, 4.7, tw - 0.6, 0.45, t, size=19, bold=True, color=BLANCO if i == 1 else AZUL)
        d.txt(x + 0.3, 5.2, tw - 0.6, 1.3, c, size=16, color="FFFFFF" if i == 1 else TEXTO)

    # ---------------------------------------------------------------- 36. Caso 3
    d.nueva("Caso 3. Batería baja en el gateway", f"""
QUÉ DECIR: El gateway es el equipo más importante de la red: si se apaga, se cae todo. Por eso se vigila su voltaje.
PRIMER AVISO, «voltaje bajo»: el promedio de 10 minutos bajó de {u['v_warn']} V. Es Warning: se ve en el tablero y no llega por Telegram. Todavía hay tiempo.
SEGUNDO AVISO, «voltaje crítico»: el promedio de 5 minutos bajó de {u['v_crit']} V. Es High y llega por Telegram. La batería está en descarga profunda y el equipo se va a apagar.
QUÉ HACER con el primer aviso: revisar si el panel está sucio, tapado o con sombra; pensar si hubo varios días nublados; avisar al referente técnico. Con el segundo aviso: avisar de inmediato, porque es probable un corte general.
QUÉ NO HACER: no desconectar la batería, el regulador ni el panel para «probar».
SI EL VOLTAJE ES DEMASIADO ALTO (más de {u['v_max']} V): el sistema avisa «voltaje excesivo» (Average, llega por Telegram). Puede estar fallando el regulador de carga y hay que avisar al referente técnico.
ALCANCE: este control existe donde el equipo es un Mikrotik alimentado desde la batería. En los demás nodos, una caída de madrugada o reinicios repetidos son la pista de un problema de energía.
FUENTE: lagunitas/templates_snmp.py (voltaje bajo: Warning, promedio de 10 min; voltaje crítico: High, promedio de 5 min; voltaje excesivo: Average).
""")
    for i, (t, sev, cond, tg, col, ct, accion) in enumerate([
        ("Voltaje bajo", "Warning", f"menos de {u['v_warn']} V", "Solo en el tablero", SEV["Warning"], TEXTO,
         "Revisar el panel: limpio, sin sombra. Avisar al referente."),
        ("Voltaje crítico", "High", f"menos de {u['v_crit']} V", "Llega por Telegram", SEV["High"], TEXTO,
         "Avisar de inmediato: el gateway se puede apagar.")]):
        x = MX + i * (CW / 2 + 0.15)
        w = CW / 2 - 0.15
        d.tarjeta(x, 1.65, w, 3.65)
        d.chip(x + 0.4, 1.9, 1.6, 0.48, sev, col, ct, size=15)
        d.txt(x + 2.2, 1.9, w - 2.6, 0.48, tg, size=15, color=GRIS, anchor="m")
        d.txt(x + 0.4, 2.55, w - 0.8, 0.55, t, size=26, bold=True, color=AZUL)
        d.txt(x + 0.4, 3.15, w - 0.8, 0.75, cond, size=34, bold=True, color=TEXTO, anchor="m")
        d.txt(x + 0.4, 4.05, w - 0.8, 1.1, accion, size=17)
    d.tarjeta(MX, 5.6, CW, 1.0, TINTE_2, GRIS_CLARO)
    d.txt(MX + 0.35, 5.6, CW - 0.7, 1.0, [[("No desconectar ", {"b": True, "c": AZUL}), "la batería, el regulador ni el panel para probar. ",
                                           ("Si se apaga el gateway, se queda sin Internet toda la red.", {"b": True})]], size=16, anchor="m")

    # ---------------------------------------------------------------- 37. Caso 4
    d.nueva("Caso 4. Toda la red sin Internet", """
QUÉ DECIR: Es la única alarma de gravedad Disaster, la más alta. Significa que el gateway perdió la conexión con la Cooperativa de Alpa Corral, que es por donde entra Internet a toda la red.
QUÉ SE VE: llega un aviso «Disaster: Gateway Mikrotik: sin enlace a Internet». En la ficha del gateway, pestaña «Router y energía», la tarjeta Internet deja de decir «Conectado».
LO QUE CONFUNDE: en el tablero todos los equipos siguen verdes, «En línea». Es correcto: las antenas y los enlaces internos de la red funcionan; lo que se cortó es la salida. Por eso NO hay que tocar antenas ni reiniciar equipos de la red.
QUÉ HACER: avisar al referente técnico y consultar con la Cooperativa si hay un corte de su lado. El problema se cierra solo cuando vuelve la conexión.
CASO PARECIDO, PERO DISTINTO: si lo que cae es el gateway entero (por ejemplo, por falta de energía), el aviso es «High: Gateway Mikrotik: sin respuesta» y todos los demás equipos quedan «Sin servicio».
PRECISIÓN PARA EL JURADO: el trigger evalúa el estado operativo de la interfaz PPPoE (pppoe-out) del Mikrotik por SNMP; también se dispara si no hay datos de esa interfaz durante 5 minutos.
ACLARACIÓN: el sistema de monitoreo necesita llegar a Internet para enviar el Telegram. Según dónde esté instalado el servidor, un corte general puede demorar el aviso. Es un punto a confirmar en la instalación real.
FUENTE: lagunitas/templates_snmp.py (trigger «sin enlace a Internet», Disaster) e informe de la PPS (conexión PPPoE con la Cooperativa de Alpa Corral).
""")
    d.tarjeta(MX, 1.65, 5.2, 2.2, SEV["Disaster"])
    d.txt(MX + 0.3, 1.8, 4.6, 0.4, "DISASTER", size=15, bold=True, color=BLANCO)
    d.txt(MX + 0.3, 2.2, 4.6, 1.5, "Gateway Mikrotik: sin enlace a Internet", size=24, bold=True, color=BLANCO, anchor="m")
    d.txt(MX, 4.05, 5.2, 0.9, "Se cortó la conexión entre el gateway y la Cooperativa de Alpa Corral.", size=17)
    d.txt(MX, 5.0, 5.2, 1.5, [[("Ojo: ", {"b": True, "c": AZUL}), "en el tablero los equipos siguen en verde. La red interna funciona; "
                               "lo que falta es la salida."]], size=17)
    for i, (t, items, fill, linea) in enumerate([
        ("Qué hacer", ["Avisar al referente técnico", "Consultar con la Cooperativa", "Esperar el aviso de Resuelto"], TINTE, None),
        ("Qué no hacer", ["Mover o tocar antenas", "Reiniciar equipos de la red", "Desenchufar el gateway"], TINTE_2, GRIS_CLARO)]):
        x = 6.25 + i * 3.32
        d.tarjeta(x, 1.65, 3.16, 4.9, fill, linea)
        d.txt(x + 0.3, 1.85, 2.6, 0.5, t, size=21, bold=True, color=AZUL if i == 0 else ROJO)
        d.txt(x + 0.3, 2.55, 2.6, 3.8, items, size=17, vinetas=True, esp=16)

    # ---------------------------------------------------------------- 38. Por qué tarda
    d.nueva("Por qué una alarma tarda un par de minutos", f"""
QUÉ DECIR: Una duda frecuente: «se cortó y el aviso tardó en llegar». No es una falla; el sistema espera a estar seguro antes de avisar.
CADA {u['intervalo']} SEGUNDOS se mide cada equipo.
PARA DECLARAR UNA CAÍDA, el equipo tiene que estar sin responder un tiempo seguido: {u['caida_base']} segundos el gateway, y {u['caida_nivel']} segundos más por cada equipo que hay en el camino. Una torre conectada al gateway, {caida_torre} segundos; el equipo más alejado de la red, {caida_max} segundos. En la prueba con el Nodo Kika, el aviso llegó al celular a los 129 segundos.
POR QUÉ ESCALONADO: así el padre siempre se declara caído antes que sus hijos, y el sistema puede avisar una sola vez. Sin eso, a veces un hijo «ganaba la carrera» y generaba un aviso de más.
PARA SEÑAL, RUIDO Y VOLTAJE se usan promedios de 5 a 15 minutos. Una ráfaga de viento o una nube no generan una alarma; una degradación sostenida, sí.
MENSAJE: un par de minutos de espera es el precio de no recibir falsas alarmas. Una alarma que suena por cualquier cosa termina siendo ignorada.
FUENTE: lagunitas/hosts.py (CAIDA_BASE = {u['caida_base']} s y CAIDA_POR_NIVEL = {u['caida_nivel']} s; el máximo sale de la profundidad del inventario), lagunitas/model.py (intervalo), lagunitas/templates_snmp.py (ventanas de promedio) e informe de la PPS (129 s en la prueba de Telegram).
""")
    datos = [(f"{u['intervalo']} s", "Cada cuánto se mide cada equipo"),
             (f"{u['caida_base']} a {caida_max} s", f"Sin responder para declarar una caída: {u['caida_base']} s el gateway y {u['caida_nivel']} s más por cada nivel"),
             ("5 a 15 min", "Promedio que se usa para señal, ruido y voltaje")]
    dw = (CW - 2 * 0.25) / 3
    for i, (n, t) in enumerate(datos):
        x = MX + i * (dw + 0.25)
        d.tarjeta(x, 1.65, dw, 3.1)
        d.txt(x + 0.2, 1.85, dw - 0.4, 1.1, n, size=40, bold=True, color=AZUL, align="c", anchor="m")
        d.txt(x + 0.3, 3.05, dw - 0.6, 1.5, t, size=16, align="c")
    d.tarjeta(MX, 5.05, CW, 1.5, AZUL)
    d.txt(MX + 0.4, 5.05, CW - 0.8, 1.5, ["El sistema espera a estar seguro antes de avisar.",
                                         [("Una ráfaga de viento no dispara una alarma; una falla sostenida, sí.", {"b": False, "c": "D6E0EC", "s": 17})]],
          size=20, bold=True, color=BLANCO, anchor="m", esp=6)

    # ================================================================ BLOQUE 6
    d.seccion(6, "Reportes y tareas", "10 minutos", "Qué tan bien anduvo la red, quién hace qué y cómo cuidarla", """
QUÉ DECIR: Además de avisar en el momento, el sistema guarda todo lo que pasó. Con eso se puede responder «¿cómo anduvo la red este mes?» y rendir cuentas a la comunidad. Después vemos qué tareas hace cada uno y cómo cuidar la red.
""")

    # ---------------------------------------------------------------- 40. Reporte
    d.nueva("El reporte de disponibilidad, en tres pasos", f"""
QUÉ DECIR: El reporte responde cómo anduvo la red en un período. Se saca en tres pasos.
1) En el menú de la izquierda, Reports, opción «Disponibilidad de la red».
2) Elegir el período (hoy, 24 horas, 7 días, 30 días, mes actual o mes anterior) y apretar «Generar reporte».
3) Leer las tarjetas y las conclusiones, que el sistema escribe solo: disponibilidad promedio, cuántos equipos cumplieron el objetivo, cuál fue la caída más larga y cuál afectó a más equipos.
Para guardarlo o compartirlo: botón «Imprimir / Guardar PDF», o «Exportar CSV» para abrirlo en una planilla.
DOS VISTAS: en «Tipo de reporte» se puede elegir Técnico o Gerencial. El gerencial oculta los datos técnicos y es el indicado para mostrar en una asamblea o a quien financia.
LECTURA DE LA CAPTURA (laboratorio, últimos 7 días): 21 equipos evaluados, disponibilidad media 99,996 %, los 21 cumplen el objetivo de {u['sla']} %, 2 caídas.
QUÉ MOSTRAR: generá el reporte de los últimos 7 días en vivo y leé las conclusiones en voz alta.
A VERIFICAR EN LA INSTALACIÓN REAL: que el usuario de operador tenga habilitado el menú del reporte.
FUENTE: manual de administración (Reports, Disponibilidad de la red). Captura del laboratorio.
""")
    f = d.imagen("reporte", MX, 1.5, 8.2, 3.4, recorte=(0, 0, 2298, 927), alt="Reporte Disponibilidad de la red: filtros, tarjetas de indicadores y conclusiones automáticas",
                 alinear="l")
    d.marca(f, 440, 228, 1)
    d.marca(f, 265, 368, 2)
    d.marca(f, 1700, 55, 3)
    d.leyenda(9.15, 1.6, ANCHO - MX - 9.15, [
        ("Elegir el período", "Y el tipo de reporte."),
        ("Generar reporte", "Y leer las tarjetas."),
        ("Guardar como PDF", "O exportar a planilla.")], size=16, paso=1.05)
    d.tarjeta(MX, 5.2, CW, 1.4)
    d.txt(MX + 0.35, 5.2, CW - 0.7, 1.4, [[("Las conclusiones las escribe el sistema: ", {"b": True, "c": AZUL}),
                                           "disponibilidad promedio, equipos que no cumplieron, la caída más larga y la que afectó a más equipos."],
                                          [("La vista «Gerencial» oculta lo técnico: sirve para mostrar en una asamblea.", {"c": GRIS})]],
          size=16, anchor="m", esp=6)

    # ---------------------------------------------------------------- 41. Porcentaje
    d.nueva("Qué significa el porcentaje de disponibilidad", f"""
QUÉ DECIR: La disponibilidad es el porcentaje del tiempo en que un equipo estuvo funcionando. 100 % es que no falló nunca en el período.
EL OBJETIVO de la red es {u['sla']} % por mes. Parece casi lo mismo que 100, pero en tiempo es concreto: en un mes de 30 días, {u['sla']} % permite hasta {sla_tiempo} de corte en total. Con 99 % serían 7 horas 12 minutos, y con 95 %, un día y medio.
DOS DISPONIBILIDADES: el reporte muestra dos columnas y conviene distinguirlas.
«Propia»: el tiempo en que ese equipo respondió por sí mismo. Mide si el equipo falla.
«Del servicio»: descuenta además el tiempo en que cayó algún equipo del que depende. Es lo que realmente vivió la casa.
EJEMPLO DEL REPORTE DE LABORATORIO: el Nodo Ale/Patricio no falló nunca (propia 100 %), pero su padre, la torre Rodeo del Padre, estuvo caída un minuto. Por eso su disponibilidad del servicio es 99,985 %. Para la familia, lo que cuenta es la segunda.
QUÉ NO BAJA LA DISPONIBILIDAD: una señal débil o una batería baja se informan como «salud degradada», pero no descuentan disponibilidad mientras el equipo responda. Los cortes durante un mantenimiento programado se pueden excluir.
PRECISIÓN PARA EL JURADO: la disponibilidad se calcula sobre el trigger de caída de cada equipo, uniendo intervalos simultáneos para no contar dos veces el mismo tiempo. El cálculo de {sla_tiempo} es 0,5 % de 720 horas.
FUENTE: lagunitas/services.py (objetivo {u['sla']} %), manual de administración (disponibilidad propia y del servicio), reporte del laboratorio (figura 21 del informe).
""")
    d.tarjeta(MX, 1.65, 4.3, 3.3, AZUL)
    d.txt(MX + 0.2, 1.8, 3.9, 0.4, "OBJETIVO MENSUAL", size=14, bold=True, color="9FB4CC", align="c")
    d.txt(MX + 0.2, 2.2, 3.9, 1.1, f"{u['sla']} %", size=60, bold=True, color=BLANCO, align="c", anchor="m")
    d.txt(MX + 0.3, 3.4, 3.7, 1.4, [f"permite hasta {sla_tiempo}", "de corte en un mes de 30 días"], size=17, color="D6E0EC", align="c", esp=2)
    for i, (t, c, ej, val) in enumerate([
        ("Disponibilidad propia", "Cuánto tiempo respondió ese equipo. Mide si el equipo falla.", "Nodo Ale/Patricio", "100,000 %"),
        ("Disponibilidad del servicio", "Descuenta también las caídas de los equipos de los que depende. Es lo que vivió la casa.",
         "Nodo Ale/Patricio", "99,985 %")]):
        x = 5.2 + i * 3.84
        w = 3.69
        d.tarjeta(x, 1.65, w, 3.3)
        d.txt(x + 0.25, 1.78, w - 0.5, 0.75, t, size=18, bold=True, color=AZUL, anchor="m")
        d.txt(x + 0.25, 2.55, w - 0.5, 1.3, c, size=14)
        d.tarjeta(x + 0.25, 3.9, w - 0.5, 0.9, BLANCO)
        d.txt(x + 0.4, 3.95, w - 0.8, 0.3, ej, size=12, color=GRIS)
        d.txt(x + 0.4, 4.25, w - 0.8, 0.5, val, size=22, bold=True, color=AZUL, anchor="m")
    d.tarjeta(MX, 5.25, CW, 1.35, TINTE_2, GRIS_CLARO)
    d.txt(MX + 0.35, 5.25, CW - 0.7, 1.35, [[("El ejemplo, del reporte de laboratorio: ", {"b": True, "c": AZUL}),
                                             "el nodo no falló, pero su padre (la torre Rodeo del Padre) estuvo caído 1 minuto. "
                                             "Para la familia cuenta la disponibilidad del servicio."]], size=16, anchor="m")

    # ---------------------------------------------------------------- 42. Quién hace qué
    d.nueva("Quién hace qué", """
QUÉ DECIR: No todo lo hace la misma persona. Hay tareas que cualquier integrante con usuario de operador puede y debería hacer, y otras que quedan para quien administra el sistema porque cambian su configuración.
COMUNIDAD Y OPERADORES: mirar el tablero con regularidad; atender las alarmas con los cinco pasos; revisar lo simple en el sitio (energía, luces, panel, estado de la antena); registrar lo actuado; sacar reportes; y avisar ANTES de hacer un trabajo en una torre.
QUIEN ADMINISTRA: dar de alta o de baja equipos y activar tramos nuevos; crear usuarios; cargar los mantenimientos programados; ajustar umbrales; ocuparse de las copias de seguridad y las actualizaciones.
POR QUÉ AVISAR ANTES DE UN TRABAJO: quien administra carga un «mantenimiento» para ese horario. Así el sistema no manda alarmas por un corte que ya se sabía y ese tiempo no se cuenta como falla.
DETALLE TÉCNICO PARA QUIEN ADMINISTRA: los equipos se agregan editando el inventario y ejecutando el aprovisionamiento. Los cambios hechos a mano dentro de Zabbix se pierden en el siguiente aprovisionamiento. Está explicado en el manual de administración.
FUENTE: manual de administración (Gestión de equipos, Mantenimientos programados, Mantenimiento del sistema).
""")
    for i, (t, sub, items, fill, linea) in enumerate([
        ("Comunidad y operadores", "Con usuario de operador",
         ["Mirar el tablero con regularidad", "Atender las alarmas con los 5 pasos", "Revisar lo simple en el sitio",
          "Registrar lo que se hizo", "Sacar reportes", "Avisar antes de trabajar en una torre"], TINTE, None),
        ("Quien administra el sistema", "Cambia la configuración",
         ["Agregar, quitar o activar equipos", "Crear usuarios", "Cargar mantenimientos programados",
          "Ajustar umbrales de alarma", "Copias de seguridad", "Actualizaciones del sistema"], TINTE_2, GRIS_CLARO)]):
        x = MX + i * (CW / 2 + 0.15)
        w = CW / 2 - 0.15
        d.tarjeta(x, 1.6, w, 5.0, fill, linea)
        d.txt(x + 0.4, 1.78, w - 0.8, 0.5, t, size=22, bold=True, color=AZUL)
        d.txt(x + 0.4, 2.3, w - 0.8, 0.35, sub, size=14, color=GRIS)
        d.txt(x + 0.4, 2.85, w - 0.8, 3.6, items, size=17, vinetas=True, esp=9)

    # ---------------------------------------------------------------- 43. Buenas prácticas
    d.nueva("Cuidados que evitan la mayoría de los problemas", """
QUÉ DECIR: Muchas caídas se evitan con cuidados simples. Los agrupamos en cuatro temas.
ENERGÍA: no desenchufar la antena ni el router de la casa, ni siquiera de noche o al irse unos días. Muchos equipos, además de dar servicio a esa casa, retransmiten hacia el vecino siguiente: si se apagan, se cortan los que dependen de ellos. Mantener el panel limpio y sin sombra de ramas.
ANTENAS: no moverlas, no colgarles nada y no «acomodarlas». Están apuntadas con precisión hacia la otra antena y un pequeño giro alcanza para perder el enlace. Si un árbol crece en la línea entre dos antenas, avisar.
CONTRASEÑAS: cada persona usa su usuario. No se comparten contraseñas ni se anotan a la vista. No publicar capturas del sistema en redes sociales. No pasar el enlace de invitación del grupo de Telegram: quien entra recibe todas las alarmas.
TRABAJOS PROGRAMADOS: avisar antes de cortar energía o trabajar en una torre, para que se cargue un mantenimiento.
PREGUNTA PARA EL GRUPO: «¿Qué equipo de mi casa no debería apagar nunca, y por qué?»
FUENTE: manual de administración (causas habituales de caídas, mantenimientos), guía de implementación (Seguridad del bot de Telegram) e inventario (equipos que retransmiten hacia otros sitios).
""")
    temas = [("Energía", ["No desenchufar la antena ni el router", "Panel limpio y sin sombra"]),
             ("Antenas", ["No moverlas ni colgarles nada", "Avisar si crece vegetación adelante"]),
             ("Contraseñas", ["Un usuario por persona, sin prestarlo", "No compartir el enlace del grupo"]),
             ("Trabajos", ["Avisar antes de cortar energía", "Avisar antes de subir a una torre"])]
    tw, th = (CW - 0.3) / 2, 2.35
    for i, (t, items) in enumerate(temas):
        x = MX + (i % 2) * (tw + 0.3)
        y = 1.6 + (i // 2) * (th + 0.25)
        d.tarjeta(x, y, tw, th)
        d.ovalo(x + 0.3, y + 0.3, 0.6, str(i + 1), size=22)
        d.txt(x + 1.1, y + 0.3, tw - 1.4, 0.6, t, size=22, bold=True, color=AZUL, anchor="m")
        d.txt(x + 1.1, y + 1.0, tw - 1.4, 1.25, items, size=17, vinetas=True, esp=8)

    # ================================================================ BLOQUE 7
    d.seccion(7, "Práctica y cierre", "20 minutos", "Actividad guiada frente al sistema, repaso y dónde seguir leyendo", """
QUÉ DECIR: Ahora les toca a ustedes. La mejor forma de perderle el miedo al sistema es usarlo. Recuerden que con usuario de operador no se puede desconfigurar nada.
ORGANIZACIÓN: si hay una sola computadora, pasen de a uno y que el resto vaya diciendo qué hacer. Si hay varias, trabajen de a dos.
""")

    # ---------------------------------------------------------------- 45. Actividad
    d.nueva("Actividad guiada: seis tareas frente al sistema", """
QUÉ DECIR: Lean cada tarea en voz alta y resuélvanla en el sistema. No pasen a la siguiente hasta que todos hayan visto la respuesta. Tiempo: unos 15 minutos.
RESPUESTAS ESPERADAS (cambian según el momento; estas son las del laboratorio, sirven de guía):
1) Se entra por el navegador, menú Dashboards, tablero «Las Lagunitas - Centro de monitoreo».
2) Depende de cada casa. Ejemplo: la Escuela Rural depende de Mesada (de su antena «Mesada · AP a Escuela»). Se ve en el mapa siguiendo la línea, o en la columna «Depende de» de la página Equipos.
3) En el laboratorio: 21 en línea, 0 caídos, 0 sin servicio, 12 no monitoreados.
4) En el laboratorio: señal -60 dBm y CCQ 95 %. Las dos están bien: la señal está entre -50 y -65 y el CCQ está por encima de 75 %.
5) En el laboratorio: 30 equipos. Es casi toda la red.
6) Reports, Disponibilidad de la red, período «Últimos 7 días», Generar reporte. Leer el recuadro Conclusiones.
SI ALGO NO SALE: anotarlo. Es información útil para mejorar este material o el sistema.
PARA QUIEN LA HACE SIN INSTRUCTOR: compará tus respuestas con las de estas notas, teniendo en cuenta que los números de la red real van a ser distintos.
""")
    tareas = [("Entrá", "al sistema y abrí el Centro de monitoreo."),
              ("Ubicá tu casa", "en el mapa. ¿De qué equipo depende?"),
              ("Contá", "cuántos equipos están En línea. ¿Hay alguno Caído o Sin servicio?"),
              ("Abrí la ficha", "de Unión de los Ríos. ¿Cuánto marcan la señal y el CCQ? ¿Están bien?"),
              ("Mirá Dependencias", "en esa ficha. ¿Cuántos equipos quedan sin servicio si cae?"),
              ("Sacá el reporte", "de los últimos 7 días y leé las conclusiones.")]
    tw, th = (CW - 0.3) / 2, 1.5
    for i, (t, c) in enumerate(tareas):
        x = MX + (i % 2) * (tw + 0.3)
        y = 1.55 + (i // 2) * (th + 0.2)
        d.tarjeta(x, y, tw, th)
        d.ovalo(x + 0.25, y + 0.43, 0.64, str(i + 1), size=24)
        d.txt(x + 1.15, y + 0.12, tw - 1.4, 0.45, t, size=19, bold=True, color=AZUL, anchor="m")
        d.txt(x + 1.15, y + 0.6, tw - 1.4, 0.8, c, size=16)

    # ---------------------------------------------------------------- 46. Simulacro
    d.nueva("Simulacro de alarma, para hacer en grupo", """
QUÉ DECIR: El simulacro consiste en provocar una caída controlada y aplicar los cinco pasos entre todos. Hay dos formas, según dónde se dicte.
EN EL LABORATORIO (no afecta a nadie): quien dicta ejecuta en la terminal del laboratorio el comando «bin/lagunitas lab caida Nodo_Kika». A los dos minutos, aproximadamente, aparece el Nodo Kika como Caído, la casa de Kika como Sin servicio, y llega el Telegram. Para terminar: «bin/lagunitas lab recuperar Nodo_Kika». El problema se cierra solo y llega el Resuelto.
EN LA RED REAL: solo como prueba controlada. Acordar un horario con la comunidad, elegir un equipo de borde (el router de una casa, no una torre) y desconectarlo unos minutos. Debe aparecer una sola alarma y, al reconectar, el aviso de resuelto. Anotar la fecha, el equipo y los tiempos.
MIENTRAS SE ESPERA LA ALARMA, preguntar: «¿Qué esperamos ver en el panal? ¿Y en la página Equipos? ¿Va a llegar un Telegram o dos?»
DESPUÉS: que una persona lea el mensaje, otra busque el equipo en rojo, otra abra Dependencias y otra registre con Acknowledge.
NO HACER la prueba en una torre ni en el gateway: dejarían sin servicio a muchos vecinos.
RECOMENDACIÓN DEL MANUAL: repetir una prueba así después de cada cambio en la red, o una vez por mes, para confirmar que la cadena de avisos funciona.
FUENTE: guía del laboratorio (Pruebas de alertas) y manual de administración (Pruebas de alarma controladas).
""")
    for i, (t, sub, items, fill, linea) in enumerate([
        ("En el laboratorio", "No afecta a nadie", ["Quien dicta simula la caída del Nodo Kika", "A los 2 minutos llega la alarma",
                                                     "El grupo aplica los 5 pasos", "Se recupera el nodo y llega el Resuelto"], TINTE, None),
        ("En la red real", "Solo como prueba acordada", ["Acordar el horario con la comunidad", "Elegir un equipo de borde: el router de una casa",
                                                         "Desconectarlo unos minutos", "Nunca una torre ni el gateway"], TINTE_2, GRIS_CLARO)]):
        x = MX + i * (CW / 2 + 0.15)
        w = CW / 2 - 0.15
        d.tarjeta(x, 1.6, w, 3.85, fill, linea)
        d.txt(x + 0.4, 1.78, w - 0.8, 0.5, t, size=22, bold=True, color=AZUL)
        d.txt(x + 0.4, 2.3, w - 0.8, 0.35, sub, size=14, color=GRIS)
        d.txt(x + 0.4, 2.85, w - 0.8, 2.5, items, size=17, vinetas=True, esp=9)
    d.tarjeta(MX, 5.7, CW, 0.9, AZUL)
    d.txt(MX + 0.4, 5.7, CW - 0.8, 0.9, "Mientras esperan: ¿qué vamos a ver en el panal? ¿Va a llegar un Telegram o dos?",
          size=18, bold=True, color=BLANCO, anchor="m")

    # ---------------------------------------------------------------- 47. Repaso
    d.nueva("Preguntas de repaso", f"""
QUÉ DECIR: Seis preguntas para comprobar que quedaron las ideas principales. Dejá que respondan antes de pasar a la diapositiva siguiente, que tiene las respuestas.
RESPUESTAS:
1) El problema está en la torre Unión de los Ríos. Mi equipo va a figurar «Sin servicio», en naranja: no tengo que tocar nada en casa.
2) «Caído» es el equipo que falló y origina el problema. «Sin servicio» es un equipo que no responde porque cayó otro del que depende.
3) Es débil: está por debajo de {u['senal_warn']} dBm. Cuanto más cerca de cero, mejor.
4) Es voltaje bajo (menos de {u['v_warn']} V): la batería se está descargando. Reviso el panel y aviso al referente. Si baja de {u['v_crit']} V es crítico.
5) No. «Señal débil» es Warning y por Telegram llega solo lo que es Average o mayor. Se ve en el tablero.
6) Unas {sla_tiempo} en un mes de 30 días.
""")
    preguntas = ["Llega «High: Unión de los Ríos: sin respuesta» y en tu casa no hay Internet. ¿Dónde está el problema?",
                 "¿Qué diferencia hay entre «Caído» y «Sin servicio»?",
                 "Una antena marca -80 dBm de señal. ¿Es buena o mala?",
                 "El gateway marca 11,9 V. ¿Qué significa y qué hacés?",
                 "¿Llega por Telegram un problema de «señal débil»?",
                 f"Con {u['sla']} % de disponibilidad en un mes, ¿cuánto tiempo hubo de corte?"]
    tw, th = (CW - 0.3) / 2, 1.5
    for i, p in enumerate(preguntas):
        x = MX + (i % 2) * (tw + 0.3)
        y = 1.55 + (i // 2) * (th + 0.2)
        d.tarjeta(x, y, tw, th, TINTE if (i // 2) % 2 == 0 else TINTE_2)
        d.ovalo(x + 0.25, y + 0.45, 0.6, str(i + 1), size=22)
        d.txt(x + 1.1, y + 0.1, tw - 1.35, th - 0.2, p, size=17, anchor="m")

    # ---------------------------------------------------------------- 48. Respuestas
    d.nueva("Respuestas", """
QUÉ DECIR: Repasá cada respuesta y, si alguna generó dudas, volvé a la diapositiva del tema: dependencias (bloque 1), estados y severidades (bloque 3), señal y batería (bloque 4), Telegram (bloque 5), porcentaje de disponibilidad (bloque 6).
PARA QUIEN SE AUTOCAPACITA: si acertaste cuatro o más, ya podés atender una alarma siguiendo los cinco pasos.
""")
    respuestas = ["En la torre. Tu equipo figura «Sin servicio»: no hay nada que tocar en casa.",
                  "Caído es el que falló. Sin servicio es el que perdió el camino por culpa de otro.",
                  f"Débil: está por debajo de {u['senal_warn']} dBm. Más cerca de cero es mejor.",
                  f"Voltaje bajo (menos de {u['v_warn']} V). Revisar el panel y avisar al referente.",
                  "No. Es Warning: se ve en el tablero. Telegram avisa desde Average.",
                  f"Hasta {sla_tiempo}, en un mes de 30 días."]
    for i, r in enumerate(respuestas):
        x = MX + (i % 2) * (tw + 0.3)
        y = 1.55 + (i // 2) * (th + 0.2)
        d.tarjeta(x, y, tw, th, BLANCO, AZUL, 1.25)
        d.ovalo(x + 0.25, y + 0.45, 0.6, str(i + 1), size=22)
        d.txt(x + 1.1, y + 0.1, tw - 1.35, th - 0.2, r, size=17, anchor="m")

    # ---------------------------------------------------------------- 49. Glosario
    d.nueva("Glosario", """
QUÉ DECIR: No hace falta leerlo completo. Queda como referencia para cuando aparezca una palabra desconocida en el sistema o en los manuales.
PALABRAS EN INGLÉS QUE APARECEN EN PANTALLA: Dashboard (tablero), Problems (problemas), Host (equipo), Severity (gravedad), Update (actualizar o registrar), Acknowledge (dar por visto), Resolved (resuelto), Disabled (deshabilitado, no monitoreado), Reports (reportes), Maintenance (mantenimiento).
PRECISIONES PARA EL JURADO: «ping» es una solicitud de eco ICMP; el CCQ (Client Connection Quality) es el indicador de airOS sobre la proporción de transmisiones exitosas; el SLA configurado es un objetivo mensual de disponibilidad sobre los servicios de Zabbix.
""")
    glos = [("Gateway", "El router por donde entra Internet a toda la red."),
            ("Torre", "Sitio principal de la red troncal (backbone)."),
            ("Nodo", "Punto intermedio que repite la señal hacia las casas."),
            ("Enlace", "Conexión de radio entre dos antenas."),
            ("Padre / hijo", "El equipo que da conexión y el que la recibe."),
            ("Ping", "Pregunta corta para saber si un equipo responde."),
            ("Latencia", "Tiempo que tarda la respuesta, en milisegundos."),
            ("Pérdida", "Porcentaje de respuestas que no llegan."),
            ("Señal (dBm)", "Fuerza con que una antena recibe a la otra."),
            ("CCQ", "Porcentaje de transmisiones que salen bien."),
            ("Disponibilidad", "Porcentaje del tiempo que algo funcionó."),
            ("SLA", "El objetivo de disponibilidad que se fija la red."),
            ("Severidad", "Gravedad de un problema, de Information a Disaster."),
            ("Mantenimiento", "Trabajo avisado: el sistema no alarma mientras dura.")]
    gw = (CW - 0.4) / 2
    for i, (t, c) in enumerate(glos):
        x = MX + (i // 7) * (gw + 0.4)
        y = 1.55 + (i % 7) * 0.73
        d.txt(x, y, 1.9, 0.6, t, size=16, bold=True, color=AZUL, anchor="m")
        d.txt(x + 1.95, y, gw - 1.95, 0.6, c, size=15, anchor="m")
        if i % 7 < 6:
            d.linea(x, y + 0.665, x + gw, y + 0.665, GRIS_CLARO, 0.75)

    # ---------------------------------------------------------------- 50. Manuales
    d.nueva("Dónde seguir leyendo", """
QUÉ DECIR: Esta capacitación es la puerta de entrada. El detalle está en cuatro documentos que acompañan al sistema. Para la comunidad, el que más sirve es el Manual de administración: explica el uso diario, las alarmas, los reportes y los problemas frecuentes.
DÓNDE ESTÁN: en la carpeta «docs» del proyecto, en versión para leer en pantalla y en versión Word para imprimir. El proyecto es software libre (licencia GPL-3.0) y está publicado en GitHub, en el repositorio ecoranti/zabbix-lagunitas.
PARA QUIÉN ES CADA UNO: el Manual de administración, para operadores y para quien administra. La Guía de integración de equipos, para quien suma una antena o un router al monitoreo. La Guía de implementación, para quien instala el sistema desde cero. La Guía del laboratorio, para practicar sin tocar la red real.
SUGERENCIA: dejar una copia impresa del Manual de administración y de la diapositiva de los cinco pasos junto a la computadora que se use para mirar el tablero.
FUENTE: README.md (sección Documentación).
""")
    docs = [("Manual de administración", "El día a día: tablero, alarmas, reportes y problemas frecuentes.", "Empezar por acá", True),
            ("Guía de integración de equipos", "Cómo sumar una antena o un router al monitoreo.", "Para quien suma equipos", False),
            ("Guía de implementación", "Cómo instalar el sistema desde cero.", "Para quien instala", False),
            ("Guía del laboratorio", "Cómo practicar sin tocar la red real.", "Para practicar", False)]
    dw = (CW - 3 * 0.25) / 4
    for i, (t, c, quien, principal) in enumerate(docs):
        x = MX + i * (dw + 0.25)
        d.tarjeta(x, 1.65, dw, 3.4, AZUL if principal else TINTE)
        d.txt(x + 0.25, 1.85, dw - 0.5, 0.95, t, size=19, bold=True, color=BLANCO if principal else AZUL, anchor="m")
        d.txt(x + 0.25, 2.9, dw - 0.5, 1.3, c, size=15, color="D6E0EC" if principal else TEXTO)
        d.chip(x + 0.25, 4.38, dw - 0.5, 0.44, quien, BLANCO, AZUL, size=13)
    d.tarjeta(MX, 5.35, CW, 1.25, TINTE_2, GRIS_CLARO)
    d.txt(MX + 0.35, 5.35, CW - 0.7, 1.25, [[("Dónde están: ", {"b": True, "c": AZUL}), "en la carpeta «docs» del proyecto, para leer en pantalla y en Word para imprimir."],
                                            [("github.com/ecoranti/zabbix-lagunitas  ·  software libre, licencia GPL-3.0", {"c": GRIS})]],
          size=16, anchor="m", esp=5)

    # ---------------------------------------------------------------- 51. Cierre
    d.bloque = ""
    d.nueva("Tres ideas para llevarse", """
QUÉ DECIR: Para cerrar, las tres ideas que resumen todo.
1) La red es una cadena: cada equipo depende de otro. Por eso, ante un corte, siempre se busca el equipo en rojo y no se pierde tiempo con los naranjas.
2) Ante una alarma, cinco pasos: leer, mirar, medir, avisar y registrar.
3) El sistema avisa; la red la cuida la comunidad. Mirar el tablero cada tanto, no desenchufar equipos y avisar antes de un trabajo evita la mayoría de los problemas.
CIERRE: volvé a la diapositiva de objetivos y preguntá cuáles se cumplieron. Agradecé la participación y anotá las dudas que quedaron: sirven para mejorar este material.
PRÓXIMO PASO SUGERIDO: acordar quién mira el tablero y con qué frecuencia, completar la diapositiva «A quién avisar» y fijar la fecha de la primera prueba de alarma controlada.
ESTADO DEL PROYECTO, PARA SER TRANSPARENTES: el sistema se validó en laboratorio. Su puesta en marcha sobre la red real depende de que se complete el despliegue de la red física.
""", fondo=AZUL, color_titulo=BLANCO, caja=(MX, 0.6, CW, 1.0), size=38)
    ideas = [("La red es una cadena", "Ante un corte, buscá el equipo en rojo. Los naranjas vuelven solos."),
             ("Cinco pasos", "Leer, mirar, medir, avisar y registrar."),
             ("El sistema avisa, la comunidad cuida", "Mirar el tablero, no desenchufar y avisar antes de un trabajo.")]
    iw = (CW - 2 * 0.3) / 3
    for i, (t, c) in enumerate(ideas):
        x = MX + i * (iw + 0.3)
        d.tarjeta(x, 2.0, iw, 3.5, "2B4C78")
        d.ovalo(x + 0.35, 2.3, 0.8, str(i + 1), fill=BLANCO, color=AZUL, size=30)
        d.txt(x + 0.35, 3.3, iw - 0.7, 0.95, t, size=22, bold=True, color=BLANCO, anchor="m")
        d.txt(x + 0.35, 4.3, iw - 0.7, 1.1, c, size=16, color="D6E0EC")
    d.txt(MX, 5.9, CW, 0.6, "Red Comunitaria y Científica Las Lagunitas  ·  Alpa Corral, Córdoba", size=16, color="9FB4CC")


def main() -> None:
    salida = Path(sys.argv[1]) if len(sys.argv) > 1 else SALIDA
    d = Deck()
    construir(d, leer_umbrales())
    cp = d.prs.core_properties
    cp.title = "Capacitación comunitaria - Red Las Lagunitas"
    cp.subject = "Uso del sistema de monitoreo (Zabbix 7.0) de la Red Comunitaria y Científica Las Lagunitas"
    cp.author = "Elias Coranti"
    cp.language = "es-AR"
    d.prs.save(salida)
    print(f"OK -> {salida} ({d.n} diapositivas)")
    for n, t in d.indice:
        print(f"  {n:2d}. {t}")
    if AVISOS:
        print("Revisar (texto que no entra en su cuadro):")
        print("\n".join(AVISOS))


if __name__ == "__main__":
    main()
