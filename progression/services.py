"""Logica de negocio de la app progression.

Concede XP aplicando, en este orden: multiplicador de racha y tope semanal.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from django.apps import apps
from django.db.models import Sum
from django.utils import timezone

from core import services as core_services
from core.models import Profile

from .models import Categoria, Penalty, XPEvent, XPRule

# Objetivo semanal del sistema (docs/sistema-v2.md, §6): 500-750 XP, techo 1.000.
OBJETIVO_XP_SEMANAL = 750
TECHO_XP_SEMANAL = 1_000

# Dias fuera del sistema: no cuentan para racha ni para penalizaciones.
# Miercoles (2) y domingo (6) en la numeracion de datetime.weekday().
MIERCOLES = 2
DOMINGO = 6
DIAS_PROTEGIDOS = (MIERCOLES, DOMINGO)

# Rachas (docs/sistema-v2.md, §6): dia 5 -> x1,10 · dia 15 -> x1,25 (tope).
ESCALONES_RACHA = ((15, Decimal("1.25")), (5, Decimal("1.10")))

# La racha cuenta dias consecutivos con accion comercial: la mision diaria D1,
# identificada por su orden dentro del tipo DIARIA (su variante minima incluida).
ORDEN_ACCION_COMERCIAL = 1

# Cuantos dias hacia atras se recorre como maximo al calcular la racha.
MAX_DIAS_RACHA = 400


def es_dia_protegido(fecha: dt.date) -> bool:
    """Miercoles y domingo estan fuera del sistema."""
    return fecha.weekday() in DIAS_PROTEGIDOS


def semana_iso(fecha: dt.date) -> tuple[int, int]:
    anio, semana, _ = fecha.isocalendar()
    return anio, semana


def rango_de_la_semana(fecha: dt.date) -> tuple[dt.date, dt.date]:
    """Lunes y domingo de la semana ISO a la que pertenece la fecha."""
    lunes = fecha - dt.timedelta(days=fecha.weekday())
    return lunes, lunes + dt.timedelta(days=6)


def _hubo_accion_comercial(fecha: dt.date) -> bool:
    MissionLog = apps.get_model("missions", "MissionLog")
    return MissionLog.objects.filter(
        fecha=fecha,
        completada=True,
        mission__tipo="DIARIA",
        mission__orden=ORDEN_ACCION_COMERCIAL,
    ).exists()


def racha_actual(fecha: dt.date | None = None) -> int:
    """Dias consecutivos con accion comercial, saltando los dias protegidos.

    Se cuenta hacia atras desde `fecha`. Si hoy todavia no hay accion comercial
    la racha no se rompe: se mide desde ayer, porque el dia aun no ha terminado.
    """
    fecha = fecha or timezone.localdate()
    dias = 0
    cursor = fecha

    if not es_dia_protegido(cursor) and not _hubo_accion_comercial(cursor):
        cursor -= dt.timedelta(days=1)

    for _ in range(MAX_DIAS_RACHA):
        if es_dia_protegido(cursor):
            cursor -= dt.timedelta(days=1)
            continue
        if not _hubo_accion_comercial(cursor):
            break
        dias += 1
        cursor -= dt.timedelta(days=1)
    return dias


def multiplicador_racha(fecha: dt.date | None = None) -> Decimal:
    """Multiplicador de XP que corresponde a la racha vigente."""
    dias = racha_actual(fecha)
    for minimo, multiplicador in ESCALONES_RACHA:
        if dias >= minimo:
            return multiplicador
    return Decimal("1.00")


def xp_de_la_semana(fecha: dt.date | None = None) -> int:
    """XP neta acumulada en la semana ISO de la fecha, penalizaciones incluidas."""
    fecha = fecha or timezone.localdate()
    lunes, domingo = rango_de_la_semana(fecha)
    total = XPEvent.objects.filter(fecha__range=(lunes, domingo)).aggregate(
        total=Sum("xp_neto")
    )["total"]
    return total or 0


def _xp_ya_concedida(accion_slug: str, fecha: dt.date) -> int:
    lunes, domingo = rango_de_la_semana(fecha)
    total = XPEvent.objects.filter(
        accion_slug=accion_slug, fecha__range=(lunes, domingo), xp_neto__gt=0
    ).aggregate(total=Sum("xp_neto"))["total"]
    return total or 0


def registrar_xp(
    accion_slug: str,
    *,
    xp: int | None = None,
    categoria: str | None = None,
    descripcion: str = "",
    fecha: dt.date | None = None,
    fuente: str = XPEvent.Fuente.MANUAL,
    objeto_relacionado: str = "",
    aplicar_racha: bool = True,
) -> XPEvent:
    """Concede XP y deja constancia del tope y la racha aplicados.

    Si existe una XPRule con ese slug, manda la regla salvo que se pasen
    `xp` o `categoria` explicitos.
    """
    fecha = fecha or timezone.localdate()
    regla = XPRule.objects.filter(accion_slug=accion_slug, activa=True).first()

    if xp is None:
        if regla is None:
            raise ValueError(f"No hay regla de XP para la accion '{accion_slug}'.")
        xp = regla.xp
    if categoria is None:
        categoria = regla.categoria if regla else Categoria.RESULTADO

    xp_bruto = int(xp)

    # La racha solo premia: nunca agrava una penalizacion.
    multiplicador = Decimal("1.00")
    if aplicar_racha and xp_bruto > 0 and categoria != Categoria.PENALIZACION:
        multiplicador = multiplicador_racha(fecha)
    xp_con_racha = int((Decimal(xp_bruto) * multiplicador).to_integral_value())

    xp_neto = xp_con_racha
    tope_aplicado = False
    tope = regla.tope_semanal if regla else None
    if tope is not None and xp_con_racha > 0:
        disponible = max(0, tope - _xp_ya_concedida(accion_slug, fecha))
        if xp_con_racha > disponible:
            xp_neto = disponible
            tope_aplicado = True

    evento = XPEvent.objects.create(
        fecha=fecha,
        categoria=categoria,
        accion_slug=accion_slug,
        descripcion=descripcion,
        xp_bruto=xp_bruto,
        xp_neto=xp_neto,
        tope_aplicado=tope_aplicado,
        multiplicador_racha=multiplicador,
        fuente=fuente,
        objeto_relacionado=objeto_relacionado,
    )
    if xp_neto:
        _actualizar_perfil(xp_neto)
    return evento


def _actualizar_perfil(xp_neto: int) -> Profile:
    """Suma la XP al perfil y recalcula nivel y rango."""
    perfil = Profile.get()
    perfil.xp_total += xp_neto
    perfil.nivel = core_services.nivel_para_xp(perfil.xp_total)
    rango = core_services.rango_para_nivel(perfil.nivel)
    if rango is not None:
        perfil.rango = rango
    perfil.save()
    return perfil


def penalizaciones_pendientes():
    """Penalizaciones sin resolver, las mas recientes primero."""
    return Penalty.objects.filter(resuelta=False).order_by("-fecha")


def resumen_progresion(fecha: dt.date | None = None) -> dict:
    """Todo lo que el panel necesita saber sobre el estado de progresion."""
    fecha = fecha or timezone.localdate()
    perfil = Profile.get()
    xp_semana = xp_de_la_semana(fecha)
    return {
        "perfil": perfil,
        "rango": perfil.rango,
        "racha": racha_actual(fecha),
        "multiplicador": multiplicador_racha(fecha),
        "xp_semana": xp_semana,
        "objetivo_xp_semanal": OBJETIVO_XP_SEMANAL,
        "xp_semana_pct": min(100, round(max(0, xp_semana) / OBJETIVO_XP_SEMANAL * 100)),
        "penalizaciones": penalizaciones_pendientes(),
    }
