"""Identidad propia para las misiones.

Hasta ahora el codigo identificaba la accion comercial por (tipo, orden) y la
Semana de Reinicio por lo mismo. Reordenar una mision desde el admin cambiaba
en silencio que contaba como racha. El titulo y el orden pasan a ser
presentacion; la identidad es el slug.

Se hace en tres pasos porque `slug` es unico y ya hay filas: primero se crean
las columnas sin restriccion, luego se rellenan, y al final se pone el unique.
"""
from django.db import migrations, models
from django.utils.text import slugify

# Slug de cada mision sembrada, por el codigo de su titulo. Los codigos (D1,
# S4, M12...) son estables; los enunciados no.
SLUGS = {
    "D1 mínima": ("accion-comercial-minima", "accion-comercial", True),
    "D1": ("accion-comercial", "accion-comercial", True),
    "D2 mínima": ("cierre-del-dia-minima", "cierre-del-dia", False),
    "D2": ("cierre-del-dia", "cierre-del-dia", False),
    "S1": ("contactos-de-la-semana", "", False),
    "S2": ("entregable-visible", "", False),
    "S3": ("publicaciones-semana", "", False),
    "S4": ("revision-semanal", "", False),
    "S5": ("entrenos-semana", "", False),
    "S6": ("bloques-alexandra", "", False),
    "S7": ("peticion-de-referido", "", False),
    "S8": ("horas-reales-anotadas", "", False),
}


def _codigo(titulo):
    """'D1 mínima · Un mensaje' -> 'D1 mínima'. Sin punto medio, el titulo entero."""
    return titulo.split("·")[0].strip()


def rellenar(apps, schema_editor):
    Mission = apps.get_model("missions", "Mission")
    usados = set()

    for mision in Mission.objects.all().order_by("pk"):
        codigo = _codigo(mision.titulo)
        slug, grupo, racha = SLUGS.get(codigo, (None, "", False))

        if slug is None:
            # Mensuales y principales: el slug sale del codigo, o del titulo
            # cuando no lo tiene (las principales se llaman por su nombre).
            slug = slugify(codigo) or slugify(mision.titulo)[:60]

        base = slug
        sufijo = 2
        while slug in usados:
            slug = f"{base}-{sufijo}"
            sufijo += 1
        usados.add(slug)

        mision.slug = slug
        mision.grupo = grupo
        mision.cuenta_para_racha = racha
        mision.save(update_fields=["slug", "grupo", "cuenta_para_racha"])


def vaciar(apps, schema_editor):
    apps.get_model("missions", "Mission").objects.update(
        slug="", grupo="", cuenta_para_racha=False
    )


class Migration(migrations.Migration):
    dependencies = [("missions", "0007_cuaderno_cierre_del_dia")]

    operations = [
        migrations.AddField(
            model_name="mission",
            name="slug",
            # Sin indice al crearla: el unique del final ya lo aporta, y
            # declarar los dos hace que PostgreSQL choque con el indice _like.
            field=models.SlugField(
                default="",
                db_index=False,
                max_length=60,
                verbose_name="slug",
                help_text="Identidad de la mision. No se cambia una vez creada.",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="mission",
            name="grupo",
            field=models.SlugField(
                blank=True,
                max_length=60,
                verbose_name="grupo de variantes",
                help_text="Vacio = la mision es su propio grupo.",
            ),
        ),
        migrations.AddField(
            model_name="mission",
            name="cuenta_para_racha",
            field=models.BooleanField(
                default=False,
                verbose_name="cuenta para la racha",
                help_text=(
                    "Completarla mantiene viva la racha comercial. Antes esto se "
                    "deducia del orden, y reordenar en el admin lo rompia en silencio."
                ),
            ),
        ),
        migrations.RunPython(rellenar, vaciar),
        migrations.AlterField(
            model_name="mission",
            name="slug",
            field=models.SlugField(
                max_length=60,
                unique=True,
                verbose_name="slug",
                help_text="Identidad de la mision. No se cambia una vez creada.",
            ),
        ),
    ]
