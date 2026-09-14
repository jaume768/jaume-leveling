from django.shortcuts import render

from . import services


def index(request):
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
