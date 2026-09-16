"""Las secundarias diarias: mismo objetivo, distinta ruta.

El sistema decia que hacer hasta en lo accesorio. Esto deja lo obligatorio
donde estaba —la accion comercial y el cierre del dia— y abre una eleccion:
cuatro rutas que empujan el mismo trimestre, y eliges una cada dia.

Cada una se puntua bajo su regla de la tabla de XP (docs/sistema-v2.md, SS6),
asi que heredan su tope semanal: elegir siempre la misma ruta deja de rentar
sola, sin necesidad de prohibirla.
"""
from django.db import migrations

GRUPO = "secundaria-diaria"

SECUNDARIAS = [
    {
        "slug": "secundaria-referido",
        "titulo": "Pedir un referido",
        "descripcion": "A un cliente, a alguien de tu gimnasio, a quien te deba un favor.",
        "definicion_terminada": "Petición enviada y anotada",
        "tiempo_estimado_min": 10,
        "xp": 50,
        "regla_xp": "peticion-referido",
        "motivo": "Tus cuatro clientes y tres gimnasios son red. Solo hay que preguntar.",
        "atributo": "red-profesional",
        "orden": 10,
    },
    {
        "slug": "secundaria-caso",
        "titulo": "Avanzar un caso de estudio",
        "descripcion": "Media hora sobre una de tus webs entregadas: el problema, lo que hiciste, el número.",
        "definicion_terminada": "Un avance real escrito, no planeado",
        "tiempo_estimado_min": 30,
        "xp": 40,
        "regla_xp": "publicacion-contenido-real",
        "motivo": "Cuatro webs live y cero casos es marca gratis tirada a la basura.",
        "atributo": "marca-portfolio",
        "orden": 11,
    },
    {
        "slug": "secundaria-plantilla",
        "titulo": "Mejorar la plantilla de entrega",
        "descripcion": "Extrae del último proyecto algo que no quieras volver a escribir.",
        "definicion_terminada": "Una pieza reutilizable guardada",
        "tiempo_estimado_min": 30,
        "xp": 40,
        "regla_xp": "automatizacion-propia",
        "motivo": "Con 10 h/semana, la velocidad es dinero. Multiplica sin subir precio.",
        "atributo": "producto",
        "orden": 12,
    },
    {
        "slug": "secundaria-conversacion",
        "titulo": "Una conversación comercial de verdad",
        "descripcion": "Diez minutos o más con alguien que puede comprarte. Llamada, café o visita.",
        "definicion_terminada": "Conversación tenida y anotada",
        "tiempo_estimado_min": 20,
        "xp": 60,
        "regla_xp": "conversacion-comercial",
        "motivo": "Un mensaje no es una conversación. Aquí es donde se cierra.",
        "atributo": "ventas",
        "orden": 13,
    },
]


def sembrar(apps, schema_editor):
    Mission = apps.get_model("missions", "Mission")
    Attribute = apps.get_model("core", "Attribute")
    atributos = {a.slug: a for a in Attribute.objects.all()}

    for datos in SECUNDARIAS:
        slug_atributo = datos.pop("atributo")
        Mission.objects.update_or_create(
            slug=datos["slug"],
            defaults={
                **datos,
                "tipo": "DIARIA",
                "eleccion": GRUPO,
                "activa": True,
                "evidencia_requerida": True,
                "attribute": atributos.get(slug_atributo),
            },
        )
        datos["atributo"] = slug_atributo


def borrar(apps, schema_editor):
    Mission = apps.get_model("missions", "Mission")
    Mission.objects.filter(eleccion=GRUPO).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("missions", "0011_eleccion_y_recompensas"),
        ("core", "0005_hoja_de_personaje"),
    ]
    operations = [migrations.RunPython(sembrar, borrar)]
