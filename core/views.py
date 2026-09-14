from django.shortcuts import render

from . import services


def index(request):
    """Panel principal. La vista es fina: el contexto lo monta el servicio."""
    minimo = request.GET.get("minimo") == "1"
    return render(request, "core/panel.html", services.contexto_panel(minimo=minimo))
