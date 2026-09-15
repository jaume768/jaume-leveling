from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from . import services
from .models import Note


def _lista(request, error: str = ""):
    """Devuelve el cuaderno entero ya actualizado (respuesta HTMX)."""
    busqueda = request.POST.get("q") or request.GET.get("q", "")
    contexto = services.cuaderno(busqueda)
    contexto["error"] = error
    return render(request, "notebook/_lista.html", contexto)


def index(request):
    """El cuaderno: notas sueltas y lo apuntado en las misiones, por día."""
    busqueda = request.GET.get("q", "")
    contexto = services.cuaderno(busqueda)
    if request.htmx:
        return render(request, "notebook/_lista.html", contexto)
    return render(request, "notebook/index.html", contexto)


@require_POST
def crear(request):
    """Apunta una nota nueva."""
    nota = services.crear_nota(
        contenido=request.POST.get("contenido", ""),
        titulo=request.POST.get("titulo", ""),
    )
    if nota is None:
        return _lista(request, error="Escribe algo antes de guardar.")
    return _lista(request)


def editar(request, pk):
    """Formulario de edición de una nota, o su guardado."""
    nota = get_object_or_404(Note, pk=pk)
    if request.method == "POST":
        services.actualizar_nota(
            nota,
            contenido=request.POST.get("contenido", ""),
            titulo=request.POST.get("titulo", ""),
        )
        return _lista(request)
    return render(request, "notebook/_nota_form.html", {"nota": nota})


def cancelar_edicion(request, pk):
    """Vuelve a pintar la nota sin guardar los cambios."""
    entrada = services._entrada_de_nota(get_object_or_404(Note, pk=pk))
    return render(request, "notebook/_entrada.html", {"entrada": entrada})


@require_POST
def fijar(request, pk):
    services.alternar_fijada(get_object_or_404(Note, pk=pk))
    return _lista(request)


@require_POST
def borrar(request, pk):
    services.borrar_nota(get_object_or_404(Note, pk=pk))
    return _lista(request)
