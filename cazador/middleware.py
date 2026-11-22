"""Tras cada peticion HTMX, si el Sistema tiene algo que decir, se lo dice.

Las acciones (completar una mision, cobrar una factura, una captura rapida)
crean avisos en la base de datos. En vez de tocar cada vista, este middleware
anade el evento `avisos` a la respuesta y la pagina pide el fragmento.
"""
import json

from .models import Aviso

EVENTO = "avisos"


class AvisosHtmxMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        respuesta = self.get_response(request)
        if request.headers.get("HX-Request") != "true" or respuesta.status_code >= 400:
            return respuesta
        if not getattr(request, "user", None) or not request.user.is_authenticated:
            return respuesta
        if not Aviso.objects.filter(visto=False).exists():
            return respuesta

        actual = respuesta.headers.get("HX-Trigger", "")
        if not actual:
            respuesta["HX-Trigger"] = EVENTO
        elif actual.lstrip().startswith("{"):
            eventos = json.loads(actual)
            eventos.setdefault(EVENTO, True)
            respuesta["HX-Trigger"] = json.dumps(eventos)
        elif EVENTO not in [e.strip() for e in actual.split(",")]:
            respuesta["HX-Trigger"] = f"{actual}, {EVENTO}"
        return respuesta
