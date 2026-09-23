from django.conf import settings
from django.contrib.auth.decorators import login_not_required
from django.http import JsonResponse
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


# --- App instalable (PWA y APK) ----------------------------------------------
#
# Las cuatro rutas son publicas: el navegador las pide antes de que haya sesion.


@login_not_required
def manifiesto(request):
    """Lo que Android lee para instalar la web como app."""
    return render(
        request, "core/manifest.webmanifest", content_type="application/manifest+json"
    )


@login_not_required
def service_worker(request):
    """Desde la raiz, para que su alcance cubra toda la aplicacion."""
    respuesta = render(request, "core/sw.js", content_type="application/javascript")
    # Nunca en cache: si no, un cambio del worker tardaria dias en llegar.
    respuesta["Cache-Control"] = "no-cache"
    return respuesta


@login_not_required
def sin_conexion(request):
    """Pantalla que el service worker ensena cuando no hay red."""
    return render(request, "core/sin_conexion.html")


@login_not_required
def assetlinks(request):
    """Prueba de que el APK y el dominio son del mismo dueno.

    Con ella la app se abre a pantalla completa; sin ella, con barra de Chrome.
    """
    enlaces = [
        {
            "relation": ["delegate_permission/common.handle_all_urls"],
            "target": {
                "namespace": "android_app",
                "package_name": settings.ANDROID_PACKAGE,
                "sha256_cert_fingerprints": settings.ANDROID_SHA256,
            },
        }
    ] if settings.ANDROID_SHA256 else []
    return JsonResponse(enlaces, safe=False)
