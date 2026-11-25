from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import services
from .forms import CALCULADAS, MANUALES, WeeklyReviewForm

# La casilla "revision hecha" ya no se marca a mano: la cierra el boton.
MANUALES_VISIBLES = [nombre for nombre in MANUALES if nombre != "m8_revision_hecha"]


def _datos_del_post(request, revision):
    """Traduce el boton pulsado a la casilla de revision hecha.

    "cerrar" la marca; "borrador" la deja sin marcar, salvo que la revision ya
    estuviera cerrada, que no se reabre por guardar un cambio. Sin boton (un
    envio antiguo), manda la casilla tal cual llega.
    """
    accion = request.POST.get("accion")
    if accion not in ("cerrar", "borrador"):
        return request.POST
    datos = request.POST.copy()
    ya_cerrada = revision is not None and revision.m8_revision_hecha
    if accion == "cerrar" or ya_cerrada:
        datos["m8_revision_hecha"] = "on"
    else:
        datos.pop("m8_revision_hecha", None)
    return datos


def index(request):
    """Revisión semanal: lo calculado a la vista, lo tuyo en tres campos."""
    fecha = timezone.localdate()
    revision = services.revision_de_la_semana(fecha)
    estaba_cerrada = bool(revision and revision.m8_revision_hecha)

    if request.method == "POST":
        form = WeeklyReviewForm(_datos_del_post(request, revision), instance=revision)
        if form.is_valid():
            guardada = services.guardar_revision(form)
            if guardada.m8_revision_hecha and not estaba_cerrada:
                messages.success(
                    request, f"Revisión de la semana {guardada.semana_iso} cerrada. +{services.XP_REVISION} XP."
                )
            elif guardada.m8_revision_hecha:
                messages.success(request, "Cambios guardados.")
            else:
                messages.success(request, "Borrador guardado.")
            return redirect("review:index")
    else:
        form = WeeklyReviewForm(
            instance=revision, initial=None if revision else services.datos_iniciales(fecha)
        )

    calculadas = services.metricas_calculadas(fecha)
    return render(
        request,
        "review/index.html",
        {
            "form": form,
            "revision": revision,
            "cerrada": estaba_cerrada,
            "semaforos": {
                clave: services.semaforo(clave, valor) for clave, valor in calculadas.items()
            },
            "campos_calculados": [form[nombre] for nombre in CALCULADAS],
            "campos_manuales": [form[nombre] for nombre in MANUALES_VISIBLES],
            "historico": services.historico(),
            "objetivos": services.OBJETIVOS,
        },
    )


@require_POST
def preparar(request):
    """Borrador de la IA para rellenar el balance. No guarda nada."""
    propuesta, error = services.preparar_con_ia(timezone.localdate())
    if error:
        return JsonResponse({"ok": False, "error": error}, status=200)
    return JsonResponse({"ok": True, **propuesta})
