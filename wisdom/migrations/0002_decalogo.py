"""Carga el decálogo operativo de docs/sistema-v3-maquiavelo.md."""
from django.db import migrations

MAXIMAS = [
    (1, "Libro III", "Un solo movimiento de precio, y silencio",
     "Las ofensas de golpe, los beneficios a gotas",
     "Sube el precio una vez y cállate. Justificarse es confesar que no lo vales.",
     "Suelo 1.500 EUR. No se justifica, no se sube por partes.",
     "precio,negociacion"),
    (2, "Libro IV", "50% por adelantado, sin excepción",
     "Temido o amado",
     "Que tus condiciones den un poco de respeto y tus entregas ninguna duda.",
     "La excepción es lo que convierte una regla en una sugerencia.",
     "condiciones,cobro"),
    (3, "Libro II", "Ningún cliente por encima del 35%",
     "Las armas propias",
     "Depender de un solo cliente es servir a un señor y llamarlo libertad.",
     "La dependencia se corrige sumando clientes, no despidiendo.",
     "concentración,riesgo"),
    (4, "Libro I", "Seis contactos por semana, entregues o no",
     "Virtù y fortuna",
     "Los diques se construyen cuando no hace falta. El que espera a la crecida ya perdió.",
     "La fortuna solo entra por las puertas que dejas abiertas.",
     "pipeline"),
    (5, "Libro V", "Antes del precio: quien firma, que teme, que haria sin ti",
     "El león y el zorro",
     "Antes de decir el precio, averigua quien firma, que teme y que haria sin ti.",
     "Tu precio se fija contra su alternativa, no contra tus horas.",
     "venta,precio"),
    (6, "Libro VI", "Un sector, no diez",
     "El principado nuevo",
     "No conquistes diez sectores. Habita uno.",
     "Colonia, no guarnicion: un caso del sector, una oferta con su nombre dentro.",
     "vertical"),
    (7, "Libro VII", "Ármate antes de exigir",
     "Los profetas desarmados",
     "Nunca pidas un precio que no puedas permitirte que rechacen.",
     "Recurrente y casos primero; precio alto despues.",
     "precio,recurrente"),
    (8, "Libro VIII", "Reclamar al día quince, no al noventa",
     "La tisis: prever el mal a distancia",
     "El problema barato y el problema caro son el mismo problema en dos momentos.",
     "Cinco días de retraso se corrigen con un email. Dos mil euros, con un abogado.",
     "cobro"),
    (9, "Libro IX", "Pregunta a los que dijeron que no",
     "Los consejeros y la adulación",
     "Cobra por tu trabajo, escucha a los que te rechazaron y no discutas con la hoja de calculo.",
     "Cada presupuesto rechazado exige una pregunta de seguimiento.",
     "aprendizaje,venta"),
    (10, "Libro IX", "Mide la tarifa efectiva cada mes",
     "Los consejeros y la adulación",
     "La tarifa efectiva no adula. Es la única métrica que no puedes convencer de nada.",
     "EUR del mes dividido por horas del mes. El único juez incorruptible.",
     "métricas"),
    (11, "Libro IV", "Fiabilidad absoluta",
     "Temido o amado",
     "Un proveedor duro y puntual es un socio. Un proveedor duro e impuntual es un enemigo.",
     "Todo lo anterior solo funciona si entregas cuando dices.",
     "entrega,reputacion"),
    (12, "Libro II", "Los miércoles y el domingo no se tocan",
     "Las armas propias",
     "El príncipe que pierde su base no gobierna nada.",
     "Días protegidos: ni XP obligatoria, ni penalización, ni racha que romper.",
     "límites,descanso"),
]


def cargar(apps, schema_editor):
    Maxim = apps.get_model("wisdom", "Maxim")
    for numero, libro, titulo, principio, texto, aplicacion, tags in MAXIMAS:
        Maxim.objects.update_or_create(
            numero=numero,
            defaults={
                "libro": libro,
                "titulo": titulo,
                "principio": principio,
                "texto": texto,
                "aplicacion": aplicacion,
                "tags": tags,
            },
        )


def borrar(apps, schema_editor):
    Maxim = apps.get_model("wisdom", "Maxim")
    Maxim.objects.filter(numero__in=[m[0] for m in MAXIMAS]).delete()


class Migration(migrations.Migration):
    dependencies = [("wisdom", "0001_initial")]
    operations = [migrations.RunPython(cargar, borrar)]
