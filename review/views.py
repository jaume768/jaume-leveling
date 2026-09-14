from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone

from . import services
from .forms import CALCULADAS, MANUALES, WeeklyReviewForm


def index(request):
    """Revisión semanal: formulario de la semana en curso más el histórico."""
    fecha = timezone.localdate()
    revision = services.revision_de_la_semana(fecha)

    if request.method == "POST":
        form = WeeklyReviewForm(request.POST, instance=revision)
        if form.is_valid():
            guardada = services.guardar_revision(form)
            if guardada.m8_revision_hecha:
                messages.success(
                    request, f"Revisión de la semana {guardada.semana_iso} cerrada. +{services.XP_REVISION} XP."
                )
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
            "semaforos": {
                clave: services.semaforo(clave, valor) for clave, valor in calculadas.items()
            },
            "campos_calculados": [form[nombre] for nombre in CALCULADAS],
            "campos_manuales": [form[nombre] for nombre in MANUALES],
            "historico": services.historico(),
            "objetivos": services.OBJETIVOS,
        },
    )
