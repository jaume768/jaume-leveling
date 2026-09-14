from django.shortcuts import render

from . import ai, services
from .models import AdviceSession


def consejo(request):
    """Chat con el consejero. El contexto se inyecta solo."""
    error = ""
    sesion = None

    if request.method == "POST":
        clave = request.POST.get("consulta", "")
        predefinida = services.CONSULTAS.get(clave)
        if predefinida:
            pregunta = predefinida["pregunta"]
            extra = (request.POST.get("texto", "") or "").strip()
            if predefinida.get("necesita_texto"):
                if not extra:
                    error = "Pega la propuesta que quieres que critique."
                else:
                    pregunta = f"{pregunta}\n\n{extra}"
        else:
            pregunta = request.POST.get("pregunta", "")

        if not error:
            sesion, error = services.consultar(pregunta)

    contexto = {
        "consultas": services.CONSULTAS,
        "sesion": sesion,
        "error": error,
        "historial": AdviceSession.objects.order_by("-fecha")[:10],
        "gasto": services.gasto_del_mes(),
        "ia_configurada": ai.ClienteIA().configurado,
        "modelo": ai.ClienteIA().modelo,
    }
    plantilla = "wisdom/_conversacion.html" if request.htmx else "wisdom/consejo.html"
    return render(request, plantilla, contexto)


def maximas(request):
    """Todas las máximas, filtrables por tag."""
    tag = request.GET.get("tag", "")
    contexto = {
        "maximas": services.maximas(tag),
        "tags": services.TAGS,
        "tag_activo": tag,
        "ultimo_libro": services.ULTIMO_LIBRO,
        "contexto_actual": services.maxima_contextual(),
    }
    plantilla = "wisdom/_lista.html" if request.htmx else "wisdom/index.html"
    return render(request, plantilla, contexto)


def gasto(request):
    """Gasto acumulado del mes en consultas al modelo."""
    return render(
        request,
        "wisdom/gasto.html",
        {
            "gasto": services.gasto_del_mes(),
            "sesiones": AdviceSession.objects.order_by("-fecha")[:50],
        },
    )
