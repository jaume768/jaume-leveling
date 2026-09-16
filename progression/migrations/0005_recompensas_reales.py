"""Las recompensas de verdad.

El modelo Reward existia vacio. Estas son las que dan sentido a subir de
nivel: cosas del mundo, no insignias. Se siembran como propuesta; se
cambian, se borran y se anaden desde el admin sin tocar codigo.

Las que dependen de nivel o de rango se desbloquean solas. Las demas las
marcas tu, porque solo tu sabes si has vencido al jefe o si el pipeline
lleva ocho semanas vivo.
"""
from django.db import migrations

# (titulo, descripcion, nivel, orden_de_rango)
RECOMPENSAS = [
    (
        "Un juego de Switch sin culpa",
        "Lo compras y lo juegas sin dar cuentas a nadie. Te lo has ganado por "
        "nivel, que es la única métrica que no admite excusas.",
        50,
        None,
    ),
    (
        "Cena especial por El Cobro Pendiente",
        "Cuando los 2.000 € estén en tu cuenta y haya un mantenimiento firmado. "
        "Se marca a mano: solo tú sabes cuándo has vencido al jefe.",
        None,
        None,
    ),
    (
        "Presupuesto libre por 8 semanas de pipeline",
        "Ocho semanas seguidas con seis contactos, entregando o no. Es tu fuga "
        "histórica: si la cierras dos meses, te has cambiado a ti mismo.",
        None,
        None,
    ),
    (
        "Nueva ilustración del personaje",
        "Al ascender a Especialista. Otro rango, otra imagen: el personaje "
        "cambia cuando cambias tú.",
        None,
        3,
    ),
    (
        "Una pieza física para el escritorio",
        "Figura, trofeo o placa, al llegar a Constructor de Sistemas. Algo que "
        "se vea desde la silla todos los días.",
        None,
        4,
    ),
    (
        "El salto: dejar Corsoft",
        "La recompensa de verdad. Seis meses por encima de 1.320 €/mes netos y "
        "20.000 € de colchón. No es un premio: es la salida.",
        None,
        5,
    ),
]


def sembrar(apps, schema_editor):
    Reward = apps.get_model("progression", "Reward")
    Rank = apps.get_model("core", "Rank")
    rangos = {r.orden: r for r in Rank.objects.all()}

    for titulo, descripcion, nivel, orden_rango in RECOMPENSAS:
        Reward.objects.update_or_create(
            titulo=titulo,
            defaults={
                "descripcion": descripcion,
                "nivel_requerido": nivel,
                "rango": rangos.get(orden_rango) if orden_rango else None,
            },
        )


def borrar(apps, schema_editor):
    Reward = apps.get_model("progression", "Reward")
    Reward.objects.filter(titulo__in=[r[0] for r in RECOMPENSAS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("progression", "0004_eleccion_y_recompensas"),
        ("core", "0003_rangos"),
    ]
    operations = [migrations.RunPython(sembrar, borrar)]
