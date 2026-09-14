from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from core import services as core_services

from . import services
from .models import Penalty, XPEvent


def index(request):
    """Historial de XP y penalizaciones."""
    return render(
        request,
        "progression/index.html",
        {
            "eventos": XPEvent.objects.order_by("-fecha", "-id")[:100],
            "penalizaciones": Penalty.objects.order_by("resuelta", "-fecha")[:50],
            "resumen": services.resumen_progresion(),
        },
    )


@require_POST
def resolver(request, pk):
    """Marca una penalización como resuelta y devuelve el bloque de alertas."""
    services.resolver_penalizacion(get_object_or_404(Penalty, pk=pk).pk)
    return render(request, "core/_alertas.html", core_services.contexto_panel())


def registrar_accion(request):
    """Modal para registrar a mano una accion de la tabla de XP."""
    contexto = {
        "acciones": [
            {"regla": regla, "disponible": services.xp_disponible_esta_semana(regla)}
            for regla in services.acciones_registrables()
        ]
    }

    if request.method == "POST":
        try:
            evento = services.registrar_accion(
                request.POST.get("accion", ""), request.POST.get("evidencia", "")
            )
        except ValueError as exc:
            contexto["error"] = str(exc)
            contexto["elegida"] = request.POST.get("accion", "")
            contexto["evidencia"] = request.POST.get("evidencia", "")
        else:
            contexto["evento"] = evento
            return render(request, "progression/_accion_hecha.html", contexto)

    return render(request, "progression/_modal_accion.html", contexto)
