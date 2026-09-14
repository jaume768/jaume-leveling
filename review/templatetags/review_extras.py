"""Filtros de plantilla de la revisión."""
from django import template

register = template.Library()


@register.filter
def dictkey(diccionario, clave):
    """Acceso por clave variable: {{ semaforos|dictkey:campo.name }}."""
    if not diccionario:
        return ""
    return diccionario.get(clave, "")
