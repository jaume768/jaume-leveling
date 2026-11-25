from django.db import migrations, models


def marcar_existentes(apps, schema_editor):
    """Marca con el criterio nuevo los eventos que ya existian.

    Fuera del techo: hechos comerciales (RESULTADO que no viene de una mision)
    y las misiones principales o anuales, que se hacen una sola vez.
    """
    XPEvent = apps.get_model("progression", "XPEvent")
    Mission = apps.get_model("missions", "Mission")

    XPEvent.objects.filter(categoria="RESULTADO").exclude(fuente="MISION").update(
        fuera_de_techo=True
    )
    principales = Mission.objects.filter(tipo__in=("PRINCIPAL", "ANUAL")).values_list("pk", flat=True)
    XPEvent.objects.filter(
        objeto_relacionado__in=[f"mission:{pk}" for pk in principales]
    ).update(fuera_de_techo=True)


class Migration(migrations.Migration):

    dependencies = [
        ("progression", "0006_recompensa_steam"),
        ("missions", "0012_secundarias_a_eleccion"),
    ]

    operations = [
        migrations.AddField(
            model_name="xpevent",
            name="fuera_de_techo",
            field=models.BooleanField(
                default=False,
                help_text="Hechos comerciales y misiones principales: no los recorta el techo de 1.000 XP ni ocupan su hueco. Su tope por accion sigue valiendo.",
                verbose_name="fuera del techo semanal",
            ),
        ),
        migrations.RunPython(marcar_existentes, migrations.RunPython.noop),
    ]
