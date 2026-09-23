"""Contexto disponible en todas las plantillas."""
from __future__ import annotations

from . import services


def navegacion(request):
    """Menu lateral y barra inferior movil, con la entrada activa marcada."""
    if request.path.startswith("/admin/"):
        return {}
    entradas = services.navegacion(request.path)
    return {
        "navegacion": entradas,
        # La barra inferior parte las entradas en dos mitades con la captura
        # rapida en medio.
        "navegacion_movil": [e for e in entradas if e["movil"]],
    }
