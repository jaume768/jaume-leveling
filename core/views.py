from django.shortcuts import render

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
