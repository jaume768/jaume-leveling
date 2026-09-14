"""Ata cada mision principal al rango que cierra.

Las cinco principales de docs/sistema-v2.md, SS5, cada una con el rango en el que
tiene sentido y del que desaparece al superarlo:

  Cobro y Cierre   II  Operador                  los 2.000 EUR + mantenimiento
  Renta            II  Operador                  450 EUR/mes recurrentes
  El Suelo         III Especialista              el rango cuyo jefe ES "El Suelo"
  Vertical         III Especialista              3 clientes del mismo sector
  Multiplicador    IV  Constructor de sistemas   plantilla + automatizacion -40%

Las diarias, semanales y mensuales se quedan sin rango: son el ritmo de base y
estan disponibles siempre.
"""
from django.db import migrations

# titulo de la mision -> (orden del rango minimo, orden del rango maximo)
PRINCIPALES = {
    "Cobro y Cierre": (2, 2),
    "Renta": (2, 2),
    "El Suelo": (3, 3),
    "Vertical": (3, 3),
    "Multiplicador": (4, 4),
}


def atar_a_su_rango(apps, schema_editor):
    Mission = apps.get_model("missions", "Mission")
    Rank = apps.get_model("core", "Rank")

    rangos = {r.orden: r for r in Rank.objects.all()}
    for titulo, (minimo, maximo) in PRINCIPALES.items():
        if minimo not in rangos or maximo not in rangos:
            continue
        Mission.objects.filter(titulo=titulo, tipo="PRINCIPAL").update(
            rango_min=rangos[minimo], rango_max=rangos[maximo]
        )


def soltar_los_rangos(apps, schema_editor):
    Mission = apps.get_model("missions", "Mission")
    Mission.objects.filter(tipo="PRINCIPAL").update(rango_min=None, rango_max=None)


class Migration(migrations.Migration):

    dependencies = [
        ("missions", "0003_mission_rango_max_mission_rango_min"),
        ("core", "0003_rangos"),
    ]

    operations = [
        migrations.RunPython(atar_a_su_rango, soltar_los_rangos),
    ]
