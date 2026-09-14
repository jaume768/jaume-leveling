"""Las misiones que desbloquea cada rango, de Especialista a Fundador.

Todas salen de docs/sistema-v2.md, SS3 (lo que desbloquea cada rango) y SS4
(arbol de habilidades), salvo "S8 - Horas reales anotadas", que es propia: sin
horas por proyecto la tarifa efectiva -la metrica maestra- no se puede calcular
y el objetivo "tiempo de entrega -40%" del rango IV no es medible.

Las semanales y mensuales llevan solo `rango_min`: se desbloquean al llegar al
rango y no se retiran nunca, porque son habitos que se conservan. Las dos
principales llevan tambien `rango_max`: cierran su rango y desaparecen al
superarlo, como el resto de principales.
"""
from django.db import migrations

# (titulo, tipo, xp, definicion_terminada, minutos, evidencia, orden,
#  rango_min, rango_max, descripcion, motivo)
MISIONES = [
    # --- Rango III - Especialista -------------------------------------------
    (
        "S7 · Petición de referido", "SEMANAL", 50,
        "Pedido por escrito a un cliente concreto y anotado", 10, True, 7, 3, None,
        "Una petición por semana, a un cliente concreto.",
        "Tu red no crece sola: el referido lo pides tú, cada semana.",
    ),
    (
        "M6 · 1 propuesta con 3 opciones", "MENSUAL", 150,
        "Enviada con tres precios y la de en medio destacada", 45, False, 6, 3, None,
        "Tres opciones de precio en la misma propuesta.",
        "Tres opciones convierten un sí o no en un cuál.",
    ),
    (
        "M7 · 1 upsell de automatización", "MENSUAL", 150,
        "Ofrecido por escrito a un cliente activo", 30, False, 7, 3, None,
        "Una automatización ofrecida a alguien que ya te paga.",
        "Vender a quien ya confía cuesta la décima parte.",
    ),
    (
        "M8 · Plantilla de entrega actualizada", "MENSUAL", 120,
        "Guardada y reutilizable, con lo aprendido del último proyecto", 60, False, 8, 3, None,
        "Lo aprendido del último proyecto, guardado para el siguiente.",
        "Multiplica tu tarifa efectiva sin subir el precio.",
    ),
    (
        "M9 · 1 testimonio conseguido", "MENSUAL", 100,
        "Testimonio por escrito, con permiso para publicarlo", 20, True, 9, 3, None,
        "Un cliente contento diciéndolo por escrito.",
        "Lo que dices tú es marketing; lo que dicen ellos es prueba.",
    ),
    # --- Rango IV - Constructor de sistemas ---------------------------------
    (
        "M10 · 1 tarea delegada a un colaborador", "MENSUAL", 200,
        "Entregada por otra persona, con su coste y las horas que te ahorró anotadas",
        0, True, 10, 4, None,
        "Diseño, textos o soporte: lo que no es tu ventaja.",
        "Delegar es lo que rompe el techo de las 10 h/semana.",
    ),
    (
        "M11 · 1 automatización interna medida", "MENSUAL", 120,
        "Funcionando, con las horas de antes y de después anotadas", 0, True, 11, 4, None,
        "Una automatización tuya, con el ahorro medido.",
        "Sin medir las horas no sabes si has automatizado o jugado.",
    ),
    (
        "S8 · Horas reales anotadas por proyecto", "SEMANAL", 40,
        "Todas las horas de la semana asignadas a su proyecto", 10, False, 8, 4, None,
        "Diez minutos el sábado. Las horas de la semana, a su proyecto.",
        "Sin horas no hay tarifa efectiva, y la tarifa efectiva preside el panel.",
    ),
    # --- Rango V - Independiente --------------------------------------------
    (
        "El Salto", "PRINCIPAL", 1800,
        "Baja presentada con los tres números encima de la mesa", 0, True, 6, 5, 5,
        "Seis meses de ingresos, colchón y concentración de clientes. Los tres.",
        "Se sale con números, no con hartazgo.",
    ),
    (
        "M12 · Ningún cliente por encima del 35%", "MENSUAL", 150,
        "Comprobado; si alguno pasa, plan escrito para bajarlo", 20, False, 12, 5, None,
        "Revisión de la concentración de tu facturación.",
        "Un cliente que es el 40% no es un cliente: es un jefe.",
    ),
    (
        "M13 · El 35% del mes apartado", "MENSUAL", 100,
        "Transferido a la cuenta separada", 10, False, 13, 5, None,
        "IVA, IRPF y cuota, fuera de la cuenta de gastar.",
        "El dinero de Hacienda nunca fue tuyo.",
    ),
    # --- Rango VI - Fundador -------------------------------------------------
    (
        "El Primer Contrato sin Ti", "PRINCIPAL", 2000,
        "Proyecto entregado y cobrado en el que no escribiste el código principal",
        0, True, 7, 6, 6,
        "Entregado por tu equipo, cobrado por tu empresa.",
        "Si todo pasa por tus manos, no tienes una empresa: tienes un empleo caro.",
    ),
    (
        "M14 · ¿Hay problema productizable?", "MENSUAL", 150,
        "Revisado si 3 clientes distintos han pagado por lo mismo; anotado cuál",
        30, False, 14, 6, None,
        "El mismo problema cobrado tres veces a mano ya es un producto.",
        "Un SaaS antes de eso es una corazonada con servidor.",
    ),
]


def crear(apps, schema_editor):
    Mission = apps.get_model("missions", "Mission")
    Rank = apps.get_model("core", "Rank")
    rangos = {r.orden: r for r in Rank.objects.all()}

    for (titulo, tipo, xp, dod, minutos, evidencia, orden, r_min, r_max,
         descripcion, motivo) in MISIONES:
        Mission.objects.update_or_create(
            titulo=titulo,
            defaults={
                "tipo": tipo,
                "xp": xp,
                "definicion_terminada": dod,
                "tiempo_estimado_min": minutos,
                "evidencia_requerida": evidencia,
                "orden": orden,
                "activa": True,
                "es_minima": False,
                "descripcion": descripcion,
                "motivo": motivo,
                "rango_min": rangos.get(r_min),
                "rango_max": rangos.get(r_max) if r_max else None,
            },
        )


def borrar(apps, schema_editor):
    Mission = apps.get_model("missions", "Mission")
    Mission.objects.filter(titulo__in=[m[0] for m in MISIONES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("missions", "0004_principales_por_rango"),
    ]

    operations = [
        migrations.RunPython(crear, borrar),
    ]
