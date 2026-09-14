"""Carga los seis rangos de docs/sistema-v2.md, sección 3.

Los tramos de nivel salen de la escala de niveles del documento: el nivel 45
cae en Operador, que es el rango en curso. Los tramos exactos de los rangos
que aun no se han alcanzado son una lectura razonable del documento.
"""
from django.db import migrations

RANGOS = [
    (1, "Aspirante", 1, 20,
     "Oferta, entrega y primer cobro.",
     "Superado.",
     ""),
    (2, "Operador", 21, 50,
     "Cobrar de forma repetible y no perder dinero por gestion.",
     "Cobrar los 2.000 EUR de Felycampo, 1 contrato recurrente firmado, "
     "2 casos publicados y 4 semanas seguidas con pipeline activo.",
     "El Cobro Pendiente · Los 2.000 EUR en tu cuenta y un mantenimiento firmado. Plazo: 4 semanas."),
    (3, "Especialista", 51, 65,
     "Vertical definida, precios subidos, ingreso predecible.",
     "1.500 EUR/mes de media 3 meses seguidos, 800 EUR/mes recurrentes, precio mínimo 1.800 EUR.",
     "El Suelo · Rechazar un proyecto de 900 EUR teniendo el mes vacio."),
    (4, "Constructor de sistemas", 66, 80,
     "Que 10 h/semana produzcan lo que hoy producirian 25.",
     "2.500 EUR/mes, tiempo de entrega -40%, 2 automatizaciones internas midiendo horas.",
     "La Maquina · Entregar un proyecto de 2.500 EUR en menos horas que el de 700 EUR."),
    (5, "Independiente", 81, 92,
     "Vivir del negocio propio.",
     "6 meses con ingresos >= 1.320 EUR/mes netos, colchon >= 20.000 EUR, ningún cliente > 35%.",
     "El Salto · Presentar la baja con los tres números, no con hartazgo."),
    (6, "Fundador", 93, 100,
     "Una empresa que funciona sin ti en el camino critico.",
     "8.000-15.000 EUR/mes, 1-3 colaboradores, SL constituida, linea de producto validada.",
     "El Primer Contrato sin Ti."),
]


def cargar(apps, schema_editor):
    Rank = apps.get_model("core", "Rank")
    Profile = apps.get_model("core", "Profile")
    for orden, nombre, nmin, nmax, objetivo, criterio, jefe in RANGOS:
        Rank.objects.update_or_create(
            orden=orden,
            defaults={
                "nombre": nombre,
                "nivel_min": nmin,
                "nivel_max": nmax,
                "objetivo": objetivo,
                "criterio_ascenso": criterio,
                "jefe": jefe,
            },
        )
    # Si ya hay perfil, se le asigna el rango que le corresponde por nivel.
    perfil = Profile.objects.first()
    if perfil is not None and perfil.rango_id is None:
        perfil.rango = Rank.objects.filter(
            nivel_min__lte=perfil.nivel, nivel_max__gte=perfil.nivel
        ).first()
        perfil.save()


def borrar(apps, schema_editor):
    Rank = apps.get_model("core", "Rank")
    Rank.objects.filter(orden__in=[r[0] for r in RANGOS]).delete()


class Migration(migrations.Migration):
    dependencies = [("core", "0002_alter_profile_fecha_inicio")]
    operations = [migrations.RunPython(cargar, borrar)]
