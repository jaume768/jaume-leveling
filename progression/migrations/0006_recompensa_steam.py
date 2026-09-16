"""Steam en vez de Switch.

El titulo es el identificador con el que se sembro, asi que se renombra la
fila existente en lugar de crear una nueva.
"""
from django.db import migrations

VIEJO = "Un juego de Switch sin culpa"
NUEVO = "Un juego de Steam sin culpa"


def renombrar(apps, schema_editor):
    apps.get_model("progression", "Reward").objects.filter(titulo=VIEJO).update(titulo=NUEVO)


def deshacer(apps, schema_editor):
    apps.get_model("progression", "Reward").objects.filter(titulo=NUEVO).update(titulo=VIEJO)


class Migration(migrations.Migration):
    dependencies = [("progression", "0005_recompensas_reales")]
    operations = [migrations.RunPython(renombrar, deshacer)]
