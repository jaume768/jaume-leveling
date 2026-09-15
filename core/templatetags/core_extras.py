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
