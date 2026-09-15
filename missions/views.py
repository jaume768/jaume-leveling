from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from core import services as core_services

from . import services
from .models import Mission


def index(request):
    """Catalogo completo, agrupado por periodicidad y filtrable por tipo."""
    tipo = request.GET.get("tipo", "")
    if tipo not in dict(Mission.Tipo.choices):
        tipo = ""

    contexto = services.catalogo_de_misiones(tipo=tipo)
    plantilla = "missions/_catalogo.html" if request.htmx else "missions/index.html"
    return render(request, plantilla, contexto)


def _fragmento(request, error: str = "", mision=None):
    """Devuelve el bloque de misiones ya actualizado (respuesta HTMX)."""
    minimo = request.POST.get("minimo") == "1" or request.GET.get("minimo") == "1"
    contexto = core_services.contexto_panel(minimo=minimo)
    contexto.update({"error": error, "mision_con_error": mision})
    return render(request, "missions/_bloque.html", contexto)


def bloque(request):
    """Refresca el bloque de misiones: lo usa el boton de dia minimo."""
    return _fragmento(request)


@require_POST
def completar(request, pk):
    """Marca una mision como hecha y devuelve el bloque actualizado."""
    mision = get_object_or_404(Mission, pk=pk, activa=True)
    try:
        services.completar_mision(
            mision,
            evidencia=request.POST.get("evidencia", ""),
            notas=request.POST.get("notas", ""),
        )
    except services.EvidenciaRequerida:
        return _fragmento(
            request,
            error="Esa misión no se da por hecha sin evidencia.",
            mision=mision,
        )
    except services.VarianteYaCompletada as otra:
        return _fragmento(
            request,
            error=f"Hoy ya cerraste «{otra}». Es la misma misión: solo cuenta una vez.",
            mision=mision,
        )
    return _fragmento(request)


def detalle(request, pk):
    """Modal con la guia de la mision: como se hace, el atajo y lo que no cuenta."""
    mision = get_object_or_404(Mission, pk=pk, activa=True)
    contexto = services.detalle_de_mision(mision)
    contexto["modo_minimo"] = request.GET.get("minimo") == "1"
    # Solo el panel tiene #bloque-misiones para recibir la respuesta.
    contexto["puede_completar"] = request.GET.get("accion") == "1"
    return render(request, "missions/_modal_detalle.html", contexto)


def evidencia(request, pk):
    """Modal para aportar la evidencia de una mision."""
    mision = get_object_or_404(Mission, pk=pk, activa=True)
    minimo = request.GET.get("minimo") == "1"
    return render(
        request, "missions/_modal_evidencia.html", {"mision": mision, "modo_minimo": minimo}
    )


def notas(request, pk):
    """Cuaderno de la mision: apuntar, releer lo de ayer y cerrarla si toca.

    GET abre el cuaderno. POST guarda lo escrito; si ademas llega `completar`,
    da la mision por hecha en la misma accion.
    """
    mision = get_object_or_404(Mission, pk=pk, activa=True)

    if request.method == "POST":
        texto = request.POST.get("notas", "")
        if "completar" in request.POST:
            try:
                services.completar_mision(mision, notas=texto)
            except services.EvidenciaRequerida:
                return _fragmento(
                    request,
                    error="Esa misión no se da por hecha sin evidencia.",
                    mision=mision,
                )
            except services.VarianteYaCompletada as otra:
                return _fragmento(
                    request,
                    error=f"Hoy ya cerraste «{otra}». Es la misma misión: solo cuenta una vez.",
                    mision=mision,
                )
        else:
            services.guardar_notas(mision, texto)
        return _fragmento(request)

    contexto = services.cuaderno_de(mision)
    contexto["modo_minimo"] = request.GET.get("minimo") == "1"
    return render(request, "missions/_modal_notas.html", contexto)


def cerrar_modal(request):
    """Vacia el hueco del modal."""
    return render(request, "missions/_modal_vacio.html")
