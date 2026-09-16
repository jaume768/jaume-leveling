"""Devuelve las tildes y la ñ que se comió el sembrado inicial.

La migracion 0002 se escribio en ASCII y el repaso posterior de tildes no
cubrio esta palabra, asi que el cierre del dia se leia "Dos tareas para
manana". El origen ya esta corregido; esto arregla las instalaciones que
sembraron los datos antes.

Se referencia por slug, no por titulo: el titulo es justo lo que cambia.
"""
from django.db import migrations

ARREGLOS = {
    "cierre-del-dia-minima": {
        "titulo": "D2 mínima · Dos tareas para mañana",
        "motivo": "Que mañana no empiece en blanco.",
    },
    "cierre-del-dia": {
        "descripcion": "5 min, 2 tareas para mañana.",
        "motivo": "Ataca tu atributo más bajo: organización.",
    },
    # De paso, las tildes que se comió el mismo repaso incompleto.
    "m2": {"titulo": "M2 · 1 cierre o renovación"},
    "revision-semanal": {
        "motivo": "8 revisiones seguidas es lo que mueve organización.",
    },
}


def arreglar(apps, schema_editor):
    Mission = apps.get_model("missions", "Mission")
    for slug, campos in ARREGLOS.items():
        Mission.objects.filter(slug=slug).update(**campos)


def deshacer(apps, schema_editor):
    Mission = apps.get_model("missions", "Mission")
    for slug, campos in ARREGLOS.items():
        Mission.objects.filter(slug=slug).update(
            **{
                k: v.replace("mañana", "manana")
                   .replace("organización", "organizacion")
                   .replace("renovación", "renovacion")
                for k, v in campos.items()
            }
        )


class Migration(migrations.Migration):
    dependencies = [("missions", "0008_identidad_de_mision")]
    operations = [migrations.RunPython(arreglar, deshacer)]
