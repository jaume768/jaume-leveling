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

# Contactos que levantan el bloqueo por una semana sin accion comercial.
CONTACTOS_PARA_DESBLOQUEAR = 6


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
    """Suma la XP al perfil y recalcula nivel y rango.

    El nivel se detiene en el techo del rango mientras su criterio de ascenso no
    este cumplido: el rango se verifica con numeros, no con XP acumulada. La XP
    no se pierde, sigue contando para cuando el ascenso se desbloquee.
    """
    perfil = Profile.get()
    perfil.xp_total += xp_neto
    perfil.nivel = core_services.techo_de_nivel(
        perfil, core_services.nivel_para_xp(perfil.xp_total)
    )
    rango = core_services.rango_para_nivel(perfil.nivel)
    if rango is not None:
        perfil.rango = rango
    perfil.save()
    return perfil


# --- Acciones sueltas de la tabla de XP --------------------------------------
#
# La tabla de resultados tiene acciones que no caben en un ritmo fijo: pedir un
# referido de mas, publicar algo, medir una automatizacion. Estas se registran a
# mano desde el panel. Las que ya llegan solas por otro camino (dinero cobrado,
# cierres, entregas, la accion comercial de D1 o la revision) NO estan aqui,
# para no puntuar dos veces el mismo hecho.
ACCIONES_MANUALES = (
    "propuesta-enviada",
    "conversacion-comercial",
    "peticion-referido",
    "testimonio-o-caso",
    "automatizacion-propia",
    "publicacion-contenido-real",
    "proyecto-rechazado-precio-bajo",
    "curso-con-artefacto",
    "entreno",
    "sueno-7h",
)


def acciones_registrables():
    """Reglas de XP que se pueden registrar a mano, con su tope."""
    reglas = {
        r.accion_slug: r
        for r in XPRule.objects.filter(accion_slug__in=ACCIONES_MANUALES, activa=True)
    }
    return [reglas[slug] for slug in ACCIONES_MANUALES if slug in reglas]


def xp_disponible_esta_semana(regla: XPRule, fecha: dt.date | None = None) -> int | None:
    """XP que aun cabe esta semana en esa regla. None si no tiene tope."""
    if regla.tope_semanal is None:
        return None
    fecha = fecha or timezone.localdate()
    return max(0, regla.tope_semanal - _xp_ya_concedida(regla.accion_slug, fecha))


def registrar_accion(
    slug: str, evidencia: str, fecha: dt.date | None = None
) -> XPEvent:
    """Registra a mano una accion de la tabla de XP.

    Exige evidencia escrita, como las misiones: sin evidencia no hay XP. El
    tope semanal lo aplica `registrar_xp`, asi que una accion por encima del
    tope se guarda con 0 XP neta y queda constancia igual.
    """
    evidencia = (evidencia or "").strip()
    if not evidencia:
        raise ValueError("Escribe la evidencia: a quien, que y donde queda anotado.")
    if slug not in ACCIONES_MANUALES:
        raise ValueError(f"'{slug}' no es una accion registrable a mano.")

    return registrar_xp(
        slug,
        descripcion=evidencia,
        fecha=fecha,
        fuente=XPEvent.Fuente.MANUAL,
    )


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


# --- Penalizaciones automáticas ---------------------------------------------

# La clave de idempotencia se guarda en Penalty.regla_slug con la forma
# "<regla>--<objeto>", para no aplicar dos veces la misma penalización por el
# mismo hecho. Todo son caracteres válidos de slug.
SEPARADOR_CLAVE = "--"


def clave_penalizacion(regla: str, objeto: str) -> str:
    return f"{regla}{SEPARADOR_CLAVE}{objeto}"


def regla_de(clave: str) -> str:
    """Regla base a partir de una clave de idempotencia."""
    return clave.split(SEPARADOR_CLAVE, 1)[0]


def clave_semana(fecha: dt.date) -> str:
    anio, semana = semana_iso(fecha)
    return f"{anio}w{semana:02d}"


def penalizacion_ya_aplicada(clave: str) -> bool:
    return Penalty.objects.filter(regla_slug=clave).exists()


def aplicar_penalizacion(
    clave: str,
    *,
    descripcion: str,
    correccion: str,
    xp: int | None = None,
    fecha: dt.date | None = None,
) -> Penalty | None:
    """Crea la penalización y descuenta la XP. Devuelve None si ya estaba aplicada.

    La penalización queda pendiente hasta que se marca como resuelta a mano.
    """
    if penalizacion_ya_aplicada(clave):
        return None

    fecha = fecha or timezone.localdate()
    regla = regla_de(clave)
    if xp is None:
        regla_xp = XPRule.objects.filter(accion_slug=regla).first()
        if regla_xp is None:
            raise ValueError(f"No hay regla de XP para '{regla}' y no se ha pasado xp.")
        xp = regla_xp.xp

    penalizacion = Penalty.objects.create(
        fecha=fecha,
        regla_slug=clave,
        descripcion=descripcion,
        xp=xp,
        correccion_exigida=correccion,
        resuelta=False,
    )
    registrar_xp(
        regla,
        xp=xp,
        categoria=Categoria.PENALIZACION,
        descripcion=descripcion,
        fecha=fecha,
        fuente=XPEvent.Fuente.AUTO,
        objeto_relacionado=f"penalty:{penalizacion.pk}",
    )
    return penalizacion


def bloqueo_tecnico_activo(fecha: dt.date | None = None) -> dict | None:
    """Bloqueo del trabajo técnico no facturable por una semana sin comercial.

    Sigue activo mientras la penalización esté sin resolver. Devuelve el
    progreso de los 6 contactos que lo levantan.
    """
    from business.models import Deal

    fecha = fecha or timezone.localdate()
    pendiente = (
        Penalty.objects.filter(
            regla_slug__startswith="semana-sin-comercial", resuelta=False
        )
        .order_by("-fecha")
        .first()
    )
    if pendiente is None:
        return None

    lunes, domingo = rango_de_la_semana(fecha)
    nuevos = Deal.objects.filter(fecha_primer_contacto__range=(lunes, domingo))
    tocados = Deal.objects.filter(ultimo_toque__range=(lunes, domingo))
    contactos = nuevos.union(tocados).count()

    return {
        "penalizacion": pendiente,
        "contactos": contactos,
        "objetivo": CONTACTOS_PARA_DESBLOQUEAR,
        "cumplido": contactos >= CONTACTOS_PARA_DESBLOQUEAR,
    }


def resolver_penalizacion(pk: int) -> Penalty | None:
    """Marca una penalización como resuelta. No devuelve la XP: ya está gastada."""
    penalizacion = Penalty.objects.filter(pk=pk).first()
    if penalizacion is None:
        return None
    penalizacion.resuelta = True
    penalizacion.save(update_fields=["resuelta"])
    return penalizacion
