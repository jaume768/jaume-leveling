from django.shortcuts import render


def index(request):
    """Pagina de Progresion. Placeholder del esqueleto."""
    return render(request, "progression/index.html")
