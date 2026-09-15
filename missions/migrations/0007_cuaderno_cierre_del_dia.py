"""El cierre del día abre el cuaderno.

D2 es "5 min, 2 tareas para mañana" y su definición de terminada es "Anotadas"
(docs/sistema-v2.md, §5): lo apuntado no es una prueba de la misión, es la
misión. Por eso estas dos piden notas al completarse.
"""
from django.db import migrations

CUADERNOS = {
    "D2 · Cierre del día": "Las dos tareas de mañana",
    "D2 mínima · Dos tareas para mañana": "Las dos tareas de mañana",
}


def abrir(apps, schema_editor):
    Mission = apps.get_model("missions", "Mission")
    for titulo, etiqueta in CUADERNOS.items():
        Mission.objects.filter(titulo=titulo).update(
            pide_notas=True, etiqueta_notas=etiqueta
        )
    # Por si el título se sembró sin tilde en alguna instalación.
    Mission.objects.filter(titulo__startswith="D2", pide_notas=False).update(
        pide_notas=True, etiqueta_notas="Las dos tareas de mañana"
    )


def cerrar(apps, schema_editor):
    Mission = apps.get_model("missions", "Mission")
    Mission.objects.filter(titulo__startswith="D2").update(
        pide_notas=False, etiqueta_notas=""
    )


class Migration(migrations.Migration):
    dependencies = [("missions", "0006_mission_etiqueta_notas_mission_pide_notas")]
    operations = [migrations.RunPython(abrir, cerrar)]
