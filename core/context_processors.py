"""Contexto disponible en todas las plantillas."""
from __future__ import annotations

from django.conf import settings

from . import services


def navegacion(request):
    """Menu lateral y barra inferior movil, con la entrada activa marcada."""
    if request.path.startswith("/admin/"):
        return {}
    entradas = services.navegacion(request.path)
    return {
        "navegacion": entradas,
        # Tarjeta del pie del menu lateral: nivel y rango en todas las paginas.
        "ficha": services.ficha_de_usuario() if request.user.is_authenticated else None,
        # La barra inferior parte las entradas en dos mitades con la captura
        # rapida en medio.
        "navegacion_movil": [e for e in entradas if e["movil"]],
        # Clave publica de las notificaciones: la necesita el navegador para suscribirse.
        "vapid_publica": settings.VAPID_PUBLIC_KEY,
    }
