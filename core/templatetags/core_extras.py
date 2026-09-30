"""Filtros de plantilla compartidos."""
from django import template

register = template.Library()


@register.filter
def dictkey(diccionario, clave):
    """Acceso por clave variable: {{ tipos|dictkey:tipo }}."""
    if not diccionario:
        return ""
    if hasattr(diccionario, "get"):
        return diccionario.get(clave, "")
    return ""


@register.filter
def miles(valor):
    """Entero con punto de miles: 2000 -> "2.000".

    El formato del locale pone un espacio fino, que en las cifras del panel
    se lee como dos numeros sueltos.
    """
    try:
        return f"{round(float(valor)):,}".replace(",", ".")
    except (TypeError, ValueError):
        return valor
