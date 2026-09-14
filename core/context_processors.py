"""Contexto disponible en todas las plantillas."""
from __future__ import annotations

from . import services


def navegacion(request):
    """Menu lateral y barra inferior movil, con la entrada activa marcada."""
    if request.path.startswith("/admin/"):
        return {}
    return {"navegacion": services.navegacion(request.path)}
