#!/usr/bin/env python3
"""Convierte el informe de la PPS (Word) a Markdown para verlo en GitHub.

Uso:   brew install pandoc
       python3 scripts/informe2md.py "docs/referencia/Informe PPS Elias.docx"

Genera docs/informe/README.md (GitHub lo muestra al abrir la carpeta) y las imágenes en
docs/informe/media/. El Word es la fuente: editar el Word y volver a correr este script.

Limpieza sobre la salida de pandoc:
- portada armada con títulos de Word -> encabezado centrado con los logos;
- se quita el índice de Word (con números de página); GitHub muestra su propio índice;
- títulos subrayados (setext) -> "##"; un solo título de nivel 1 (el del trabajo);
- imágenes con medidas en pulgadas (GitHub ignora "style") -> ancho en píxeles;
- los marcadores <!-- VIDEO: ... --> del Markdown anterior se conservan (ver al pie).
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESTINO = ROOT / "docs" / "informe"
IMG = re.compile(r'<img src="([^"]+)" style="width:([\d.]+)in;height:[\d.]+in"\s*/>')
MARCA_VIDEO = re.compile(r"^<!-- VIDEO: (.+?) -->$")


def _img(m: re.Match) -> str:
    ancho = min(800, round(float(m.group(2)) * 96))
    return f'<img src="{m.group(1)}" width="{ancho}">'


def _texto(linea: str) -> str:
    """Texto plano de una línea de la portada (sin '#', negritas ni imágenes)."""
    linea = re.sub(r"<img[^>]*>", "", linea)
    return re.sub(r"^[#>\s]+|\*\*", "", linea).strip()


def _portada(lineas: list[str]) -> list[str]:
    logos = re.findall(r'<img src="([^"]+)"', "\n".join(lineas))
    out = ['<p align="center">'] + [f'  <img src="{src}" height="120">' for src in logos] + ["</p>", ""]
    titulos = [_texto(l) for l in lineas if l.startswith("#") and _texto(l)]
    for i, t in enumerate(titulos):
        etiqueta = "h1" if i == len(titulos) - 1 else "h3"  # el último es el título del trabajo
        out.append(f'<{etiqueta} align="center">{t}</{etiqueta}>')
    out.append("")
    datos = [_texto(l) for l in lineas if not l.startswith("#") and _texto(l)]
    out += ["| | |", "|---|---|"]
    for d in datos:
        clave, _, valor = d.partition(":")
        out.append(f"| **{clave.strip()}** | {valor.strip()} |")
    return out + [""]


def limpiar(md: str, videos: dict[str, str]) -> str:
    lineas = md.splitlines()
    # Títulos subrayados de pandoc -> ATX.
    atx = []
    for i, l in enumerate(lineas):
        if i + 1 < len(lineas) and l.strip() and re.fullmatch(r"-{3,}|={3,}", lineas[i + 1].strip()):
            atx.append(("# " if lineas[i + 1].strip()[0] == "=" else "## ") + l.strip())
            lineas[i + 1] = "\0"
        elif l != "\0":
            atx.append(l)
    lineas = [l for l in atx if l != "\0"]

    i_indice = next(i for i, l in enumerate(lineas) if re.match(r"^#+\s+Índice", l))
    cuerpo = lineas[i_indice + 1:]
    i_sig = next(i for i, l in enumerate(cuerpo) if l.startswith("#"))
    cuerpo = cuerpo[i_sig:]

    out = _portada(lineas[:i_indice])
    out += ["> Versión web del informe, generada desde el Word con `scripts/informe2md.py`.", ""]
    for l in cuerpo:
        if l.startswith("# "):
            l = "#" + l  # un solo H1: el título del trabajo
        l = IMG.sub(_img, l)
        out.append(l)
        titulo = re.sub(r"^#+\s+", "", l).strip() if l.startswith("#") else None
        if titulo and titulo in videos:
            out += ["", f"<!-- VIDEO: {titulo} -->", videos[titulo], ""]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip() + "\n"


def _videos_existentes(md: Path) -> dict[str, str]:
    """{título de sección: URL del video} a partir de los marcadores del README anterior."""
    if not md.exists():
        return {}
    lineas = md.read_text(encoding="utf-8").splitlines()
    out = {}
    for i, l in enumerate(lineas):
        m = MARCA_VIDEO.match(l.strip())
        if m and i + 1 < len(lineas) and lineas[i + 1].strip():
            out[m.group(1)] = lineas[i + 1].strip()
    return out


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    origen = Path(sys.argv[1]).resolve()
    if not shutil.which("pandoc"):
        sys.exit("Falta pandoc: brew install pandoc")
    readme = DESTINO / "README.md"
    videos = _videos_existentes(readme)
    DESTINO.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(DESTINO / "media", ignore_errors=True)
    md = subprocess.run(["pandoc", str(origen), "-f", "docx", "-t", "gfm", "--wrap=none",
                         "--extract-media=."], cwd=DESTINO, check=True,
                        capture_output=True, text=True).stdout
    readme.write_text(limpiar(md, videos), encoding="utf-8")
    print(f"  {readme.relative_to(ROOT)} ({len(list((DESTINO / 'media').glob('*')))} imágenes"
          f", {len(videos)} video(s) conservados)")


if __name__ == "__main__":
    main()
