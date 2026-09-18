"""Filtros de plantilla del consejero."""
import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

# El modelo responde en markdown. Aqui se traduce el subconjunto que usa de
# verdad (titulos, listas, negrita, cursiva, codigo, citas y reglas) y nada
# mas: no hace falta una dependencia entera para esto.
_NEGRITA = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_CURSIVA = re.compile(r"(?<![\*\w])\*(?!\s)(.+?)(?<!\s)\*(?!\*)", re.DOTALL)
_CODIGO = re.compile(r"`([^`]+)`")
_ENLACE = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
_TITULO = re.compile(r"^(#{1,6})\s+(.*)$")
_VINETA = re.compile(r"^\s*[-*+]\s+(.*)$")
_NUMERO = re.compile(r"^\s*\d+[.)]\s+(.*)$")
_CITA = re.compile(r"^\s*>\s?(.*)$")
_REGLA = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")

_NIVEL_TITULO = {1: "h2", 2: "h3", 3: "h4", 4: "h4", 5: "h4", 6: "h4"}


def _en_linea(texto):
    """Marcas dentro de una linea. El texto ya viene escapado."""
    texto = _CODIGO.sub(r"<code>\1</code>", texto)
    texto = _ENLACE.sub(
        r'<a href="\2" target="_blank" rel="noopener">\1</a>', texto
    )
    texto = _NEGRITA.sub(r"<strong>\1</strong>", texto)
    texto = _CURSIVA.sub(r"<em>\1</em>", texto)
    return texto


@register.filter
def markdown(texto):
    """Markdown basico a HTML. La entrada se escapa antes de tocar nada."""
    if not texto:
        return ""

    # Se escapa linea a linea, no de golpe: si se escapara antes de separar,
    # los `>` de las citas llegarian aqui convertidos en `&gt;`.
    lineas = texto.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    salida = []
    parrafo = []
    lista = None  # "ul", "ol" o None
    cita = []
    bloque = None  # etiqueta del bloque de codigo abierto

    def cerrar_parrafo():
        nonlocal parrafo
        if parrafo:
            salida.append("<p>" + _en_linea("<br>".join(parrafo)) + "</p>")
            parrafo = []

    def cerrar_lista():
        nonlocal lista
        if lista:
            salida.append(f"</{lista}>")
            lista = None

    def cerrar_cita():
        nonlocal cita
        if cita:
            salida.append(
                "<blockquote><p>" + _en_linea("<br>".join(cita)) + "</p></blockquote>"
            )
            cita = []

    def cerrar_todo():
        cerrar_parrafo()
        cerrar_lista()
        cerrar_cita()

    for linea in lineas:
        if linea.strip().startswith("```"):
            if bloque is None:
                cerrar_todo()
                bloque = []
            else:
                salida.append("<pre><code>" + "\n".join(bloque) + "</code></pre>")
                bloque = None
            continue

        if bloque is not None:
            bloque.append(escape(linea))
            continue

        if not linea.strip():
            cerrar_todo()
            continue

        if _REGLA.match(linea):
            cerrar_todo()
            salida.append("<hr>")
            continue

        titulo = _TITULO.match(linea)
        if titulo:
            cerrar_todo()
            etiqueta = _NIVEL_TITULO[len(titulo.group(1))]
            salida.append(
                f"<{etiqueta}>{_en_linea(escape(titulo.group(2)))}</{etiqueta}>"
            )
            continue

        marca = _CITA.match(linea)
        if marca:
            cerrar_parrafo()
            cerrar_lista()
            cita.append(escape(marca.group(1)))
            continue
        cerrar_cita()

        vineta = _VINETA.match(linea)
        numero = None if vineta else _NUMERO.match(linea)
        if vineta or numero:
            cerrar_parrafo()
            etiqueta = "ul" if vineta else "ol"
            if lista != etiqueta:
                cerrar_lista()
                salida.append(f"<{etiqueta}>")
                lista = etiqueta
            contenido = (vineta or numero).group(1)
            salida.append(f"<li>{_en_linea(escape(contenido))}</li>")
            continue

        cerrar_lista()
        parrafo.append(escape(linea.strip()))

    if bloque is not None:
        salida.append("<pre><code>" + "\n".join(bloque) + "</code></pre>")
    cerrar_todo()

    return mark_safe("".join(salida))
