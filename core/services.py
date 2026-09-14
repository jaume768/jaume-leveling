"""Logica de negocio de la app core.

Toda la logica vive aqui: las vistas son finas y los modelos son datos.
"""
from __future__ import annotations

# XP necesaria para subir un nivel, por tramos.
#
# El unico tramo documentado es 41-60 -> 2.000 XP/nivel (docs/sistema-v2.md, §6).
# El resto son extrapolaciones coherentes con la regla "a tu nivel, subir debe
# costar": se revisan cuando el sistema llegue a esos tramos.
TRAMOS_XP = (
    (1, 20, 500),
    (21, 40, 1_000),
    (41, 60, 2_000),
    (61, 80, 3_500),
    (81, 100, 5_000),
)

NIVEL_MAXIMO = 100


def xp_por_nivel(nivel: int) -> int:
    """XP necesaria para pasar de `nivel` al siguiente."""
    for minimo, maximo, coste in TRAMOS_XP:
        if minimo <= nivel <= maximo:
            return coste
    return TRAMOS_XP[-1][2]


def xp_acumulada_hasta_nivel(nivel: int) -> int:
    """XP total acumulada necesaria para alcanzar `nivel` desde el nivel 1."""
    return sum(xp_por_nivel(n) for n in range(1, nivel))


def progreso_en_nivel(nivel: int, xp_total: int) -> tuple[int, int, float]:
    """Devuelve (xp_en_el_nivel, xp_que_faltan, porcentaje) para el nivel dado."""
    coste = xp_por_nivel(nivel)
    base = xp_acumulada_hasta_nivel(nivel)
    en_nivel = max(0, min(xp_total - base, coste))
    if nivel >= NIVEL_MAXIMO:
        return coste, 0, 100.0
    return en_nivel, coste - en_nivel, round(en_nivel / coste * 100, 1)


def nivel_para_xp(xp_total: int) -> int:
    """Nivel que corresponde a una XP total acumulada."""
    nivel = 1
    while nivel < NIVEL_MAXIMO and xp_total >= xp_acumulada_hasta_nivel(nivel + 1):
        nivel += 1
    return nivel


def rango_para_nivel(nivel: int):
    """Rango cuyo tramo contiene el nivel dado, o None si no hay ninguno."""
    from .models import Rank

    return Rank.objects.filter(nivel_min__lte=nivel, nivel_max__gte=nivel).first()


def contexto_panel(fecha=None, minimo: bool = False) -> dict:
    """Todo lo que pinta el panel principal, en una sola llamada."""
    from django.utils import timezone

    from business import services as business
    from missions import services as missions
    from progression import services as progression
    from review import services as review
    from wisdom import services as wisdom

    fecha = fecha or timezone.localdate()
    tarifa = business.tarifa_efectiva_mes(fecha)
    contexto = progression.resumen_progresion(fecha)
    contexto.update(
        {
            "hoy": fecha,
            "misiones": missions.panel_de_misiones(fecha, minimo=minimo),
            "alertas": business.alertas(fecha),
            "consejo": wisdom.maxima_contextual(fecha),
            "aviso_revision": review.aviso_revision_pendiente(fecha),
            "recurrente": business.recurrente_activo(),
            "tarifa_efectiva": tarifa,
            "hay_horas": tarifa is not None,
        }
    )
    return contexto
