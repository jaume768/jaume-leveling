from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from . import services


def index(request):
    """Panel principal. La vista es fina: el contexto lo monta el servicio."""
    minimo = request.GET.get("minimo") == "1"
    return render(request, "core/panel.html", services.contexto_panel(minimo=minimo))


def niveles(request):
    """Rangos, jefes y la escalera de los 100 niveles."""
    return render(request, "core/niveles.html", services.contexto_niveles())


def personaje(request):
    """Hoja de personaje: los quince atributos y lo que mueve el siguiente +10."""
    return render(request, "core/personaje.html", services.hoja_de_personaje())


def calibracion(request):
    """Calibracion mensual: las tres preguntas y el ajuste de atributos."""
    error = ""
    hecho = ""

    if request.method == "POST":
        try:
            atributo = services.ajustar_atributo(
                request.POST.get("slug", ""),
                int(request.POST.get("valor") or 0),
                request.POST.get("nota", ""),
            )
        except (ValueError, TypeError) as exc:
            error = str(exc)
        else:
            hecho = f"{atributo.nombre} queda en {atributo.valor}."

    contexto = services.contexto_calibracion()
    contexto.update({"error": error, "hecho": hecho})
    return render(request, "core/calibracion.html", contexto)


# Clave de sesion donde se recuerda el ultimo tipo de captura usado.
SESION_ULTIMA_CAPTURA = "captura_ultimo_tipo"


@require_http_methods(["GET", "POST"])
def captura(request):
    """Captura rapida: contacto, toque, nota o entreno, en diez segundos.

    Recuerda en la sesion el ultimo tipo usado, que casi siempre es el que
    vuelves a necesitar.
    """
    recordado = request.session.get(
        SESION_ULTIMA_CAPTURA, services.TIPO_DE_CAPTURA_POR_DEFECTO
    )
    tipo = request.POST.get("tipo") or request.GET.get("tipo") or recordado
    if tipo not in services.TIPOS_DE_CAPTURA:
        tipo = services.TIPO_DE_CAPTURA_POR_DEFECTO

    contexto = services.contexto_captura(tipo)

    if request.method == "POST":
        try:
            contexto["hecho"] = services.capturar(tipo, request.POST)
        except ValueError as exc:
            contexto["error"] = str(exc)
        else:
            request.session[SESION_ULTIMA_CAPTURA] = tipo
            return render(request, "core/_captura_hecha.html", contexto)

    return render(request, "core/_modal_captura.html", contexto)
