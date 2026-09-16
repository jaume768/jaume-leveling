from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core import services as core_services

from . import services
from .models import Penalty, XPEvent


@require_POST
def activar_reinicio(request):
    """Declara la semana en curso como Semana de Reinicio."""
    try:
        services.activar_semana_de_reinicio(request.POST.get("motivo", ""))
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            "Semana de Reinicio activada: 3 contactos, 1 entregable y la revisión. "
            "La XP va ×1,5.",
        )
    return redirect("progression:index")


def index(request):
    """Historial de XP y penalizaciones."""
    return render(
        request,
        "progression/index.html",
        {
            "reinicio": services.semana_de_reinicio(),
            "puede_reiniciar": services.puede_activar_reinicio()[0],
            "motivo_no_reinicio": services.puede_activar_reinicio()[1],
            "eventos": XPEvent.objects.order_by("-fecha", "-id")[:100],
            "penalizaciones": Penalty.objects.order_by("resuelta", "-fecha")[:50],
            "resumen": services.resumen_progresion(),
        },
    )


def evento(request, pk):
    """Detalle de un evento de XP: que se hizo y que se escribio entonces."""
    registro = get_object_or_404(XPEvent, pk=pk)
    return render(request, "progression/_modal_evento.html", services.detalle_de_evento(registro))


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


def recompensas(request):
    """Lo que te llevas por llegar: ganadas, por llegar y ya disfrutadas."""
    plantilla = (
        "progression/_recompensas_lista.html" if request.htmx
        else "progression/recompensas.html"
    )
    return render(request, plantilla, services.panel_de_recompensas())


@require_POST
def desbloquear_recompensa(request, pk):
    """Desbloqueo a mano de las que no dependen de nivel ni de rango."""
    services.desbloquear_recompensa(pk)
    return render(request, "progression/_recompensas_lista.html",
                  services.panel_de_recompensas())


@require_POST
def disfrutar_recompensa(request, pk):
    """La has cobrado de verdad."""
    services.disfrutar_recompensa(pk)
    return render(request, "progression/_recompensas_lista.html",
                  services.panel_de_recompensas())
