"""Los quince atributos de la hoja de personaje.

Valores, evidencia y "que mueve el siguiente +10" salen tal cual de la tabla de
docs/sistema-v2.md, SS2 (hoja de personaje v2).

Lectura del perfil segun el documento: los tres puntos fuertes son tecnica,
finanzas y limites personales; los tres agujeros son producto (28),
organizacion (25) e IA aplicada (38).
"""
from django.db import migrations

# (slug, nombre, valor, categoria, evidencia, siguiente +10)
ATRIBUTOS = [
    ("tecnica", "Técnica", 62, "TECNICA",
     "4 proyectos live incluido ecommerce, stack amplio, despliegues",
     "Estimar 3 proyectos con error menor del 25%"),
    ("ia-automatizacion", "IA y automatización", 38, "TECNICA",
     "Sin evidencia de uso comercial",
     "1 automatización cobrada con ahorro medido"),
    ("producto", "Producto", 28, "NEGOCIO",
     "Entregas a medida, sin paquete ni precio fijo",
     "Vender dos veces el mismo paquete sin tocar el alcance"),
    ("ventas", "Ventas", 38, "NEGOCIO",
     "Cierres reales, tickets de 700 a 4.000 €",
     "Pipeline sostenido 8 semanas mientras entregas"),
    ("marketing", "Marketing", 30, "NEGOCIO",
     "Sabe SEO, no lo aplica a sí mismo",
     "3 casos publicados + 1 lead entrante"),
    ("comunicacion", "Comunicación", 50, "PERSONAL",
     "Ha negociado y cerrado con desconocidos",
     "Decir un precio y callarse"),
    ("gestion-proyectos", "Gestión de proyectos", 45, "NEGOCIO",
     "Proyectos entregados, cobro pendiente de 2.000 €",
     "3 entregas seguidas sin horas fuera de alcance"),
    ("organizacion", "Organización", 25, "PERSONAL",
     "Sin cambios. Sigue siendo tu talón de Aquiles",
     "8 revisiones semanales seguidas"),
    ("disciplina", "Disciplina", 58, "PERSONAL",
     "Entrena y compagina empleo + freelance",
     "Cumplir el bloque comercial sin estructura externa"),
    ("finanzas", "Finanzas", 62, "NEGOCIO",
     "13.000 €, sin deuda, 1.080 €/mes de ahorro, autónomo",
     "Saber tu margen por proyecto y apartar el 35%"),
    ("red-profesional", "Red profesional", 28, "NEGOCIO",
     "4 clientes, 3 gimnasios, 0 red sistemática",
     "15 dueños de negocio a los que puedas escribir sin presentarte"),
    ("marca-portfolio", "Marca y portfolio", 32, "NEGOCIO",
     "3 webs públicas, 0 casos, 0 testimonios",
     "Web propia con 3 casos y resultados"),
    ("salud-fisica", "Salud física", 68, "SALUD",
     "175 cm / 81 kg, 4 disciplinas activas",
     "78,5 kg manteniendo marcas de fuerza"),
    ("energia-descanso", "Energía y descanso", 55, "SALUD",
     "Autorreporte 3-4 sobre 5",
     "Sueño medio de 7 h o más con energía 4/5 cinco días de siete"),
    ("relaciones", "Relaciones y equilibrio", 72, "PERSONAL",
     "Límites explícitos y defendidos con Alexandra",
     "Mantenerlos 12 semanas con carga alta de trabajo"),
]

# Que atributo mueve cada mision. El atributo decide ademas si la XP cuenta
# como SOPORTE (salud y limites personales) o como RESULTADO.
MISION_ATRIBUTO = {
    "D1 · Acción comercial": "ventas",
    "D1 mínima · Un mensaje de tres líneas": "ventas",
    "D2 · Cierre del día": "organizacion",
    "D2 mínima · Dos tareas para mañana": "organizacion",
    "S1 · 6 contactos acumulados": "ventas",
    "S2 · 1 entregable visible": "gestion-proyectos",
    "S3 · 2 publicaciones sobre trabajo real": "marca-portfolio",
    "S4 · Revisión semanal (domingo 20:15)": "organizacion",
    "S5 · 4 entrenos": "salud-fisica",
    "S6 · Bloques con Alexandra intactos": "relaciones",
    "S7 · Petición de referido": "red-profesional",
    "S8 · Horas reales anotadas por proyecto": "finanzas",
    "M1 · 2 propuestas formales enviadas": "ventas",
    "M2 · 1 cierre o renovación": "ventas",
    "M3 · 0 EUR pendientes de cobro fuera de plazo": "finanzas",
    "M4 · 1 caso de estudio publicado con número": "marca-portfolio",
    "M5 · Calibración del sistema": "organizacion",
    "M6 · 1 propuesta con 3 opciones": "producto",
    "M7 · 1 upsell de automatización": "ia-automatizacion",
    "M8 · Plantilla de entrega actualizada": "producto",
    "M9 · 1 testimonio conseguido": "marca-portfolio",
    "M10 · 1 tarea delegada a un colaborador": "gestion-proyectos",
    "M11 · 1 automatización interna medida": "ia-automatizacion",
    "M12 · Ningún cliente por encima del 35%": "finanzas",
    "M13 · El 35% del mes apartado": "finanzas",
    "M14 · ¿Hay problema productizable?": "producto",
    "Cobro y Cierre": "finanzas",
    "Renta": "producto",
    "El Suelo": "comunicacion",
    "Vertical": "marketing",
    "Multiplicador": "ia-automatizacion",
    "El Salto": "finanzas",
    "El Primer Contrato sin Ti": "gestion-proyectos",
}


def sembrar(apps, schema_editor):
    Attribute = apps.get_model("core", "Attribute")
    Mission = apps.get_model("missions", "Mission")

    for slug, nombre, valor, categoria, evidencia, hito in ATRIBUTOS:
        Attribute.objects.update_or_create(
            slug=slug,
            defaults={
                "nombre": nombre,
                "valor": valor,
                "categoria": categoria,
                "evidencia": evidencia,
                "siguiente_hito": hito,
            },
        )

    por_slug = {a.slug: a for a in Attribute.objects.all()}
    for titulo, slug in MISION_ATRIBUTO.items():
        if slug in por_slug:
            Mission.objects.filter(titulo=titulo).update(attribute=por_slug[slug])


def borrar(apps, schema_editor):
    Attribute = apps.get_model("core", "Attribute")
    Mission = apps.get_model("missions", "Mission")
    Mission.objects.update(attribute=None)
    Attribute.objects.filter(slug__in=[a[0] for a in ATRIBUTOS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_attribute_evidencia_attribute_siguiente_hito"),
        ("missions", "0005_misiones_por_rango"),
    ]

    operations = [
        migrations.RunPython(sembrar, borrar),
    ]
