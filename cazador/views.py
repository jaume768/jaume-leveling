import json

from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from . import services
from .models import Aviso


def avisos(request):
    """Fragmento con los avisos pendientes. Cada uno se pinta una sola vez."""
    pendientes = services.recoger_avisos()
    ventanas = [a for a in pendientes if a.es_ventana]
    contexto = {
        "toasts": [a for a in pendientes if not a.es_ventana],
        "ventanas": ventanas,
    }
    if any(a.tipo == Aviso.Tipo.MISION_DIARIA for a in ventanas):
        contexto["diarias"] = services.estado_diarias()
    if any(a.tipo in (Aviso.Tipo.NIVEL, Aviso.Tipo.RANGO) for a in ventanas):
        from core.models import Profile

        perfil = Profile.get()
        contexto["perfil"] = perfil
        contexto["rango"] = perfil.rango
    return render(request, "cazador/_avisos.html", contexto)


@require_POST
def abrir_cofre(request):
    cofre = services.abrir_cofre()
    return render(request, "cazador/_cofre.html", {"cofre": {"cofre": cofre, "disponible": False},
                                                   "recien_abierto": cofre is not None})


@require_POST
def equipar_titulo(request):
    try:
        services.equipar_titulo(request.POST.get("clave", ""))
    except (ValueError, KeyError) as exc:
        return HttpResponseBadRequest(str(exc))
    return redirect("core:personaje")


@require_POST
def equipar_marco(request):
    try:
        services.equipar_marco(request.POST.get("clave", ""))
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))
    return redirect("core:personaje")


@require_POST
def alias(request):
    services.cambiar_alias(request.POST.get("alias", ""))
    return redirect("core:personaje")


# --- Notificaciones ---


@require_POST
def suscribir(request):
    try:
        datos = json.loads(request.body or b"{}")
        services.guardar_suscripcion(datos, request.headers.get("User-Agent", ""))
    except (ValueError, json.JSONDecodeError) as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    return JsonResponse({"ok": True})


@require_POST
def probar_push(request):
    llegados = services.enviar_push(
        "[SISTEMA] Prueba", "Las notificaciones del Sistema funcionan.", "/"
    )
    return HttpResponse(
        f'<p class="text-caption {"text-ok" if llegados else "text-bad"}">'
        f'{"Enviada a " + str(llegados) + " dispositivo(s)." if llegados else "No llegó a ningún dispositivo."}</p>'
    )


# --- Hitos de atributo y portales ---


@require_POST
def reclamar_hito(request):
    from django.contrib import messages
    from django.urls import reverse

    from core.models import Attribute

    from . import hitos

    try:
        hitos.reclamar_hito(request.POST.get("slug", ""), request.POST.get("evidencia", ""))
    except Attribute.DoesNotExist:
        return HttpResponseBadRequest("Atributo desconocido.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect(reverse("core:personaje") + "#atributos")


@require_POST
def entrar_portal(request, pk):
    from . import portales

    try:
        portales.entrar(pk)
    except (ValueError, portales.Portal.DoesNotExist) as exc:
        return HttpResponseBadRequest(str(exc))
    return redirect("core:index")
