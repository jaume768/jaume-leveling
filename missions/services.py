"""Logica de negocio de la app missions.

Que misiones tocan hoy, como se dan por hechas y cual es el dia minimo.
"""
from __future__ import annotations

import datetime as dt

from django.db import transaction
from django.utils import timezone

from progression import services as progression
from progression.models import Categoria, XPEvent

from .models import Mission, MissionLog


class EvidenciaRequerida(Exception):
    """La mision exige evidencia y no se ha aportado."""


def slug_de_mision(mission: Mission) -> str:
    """Slug estable con el que la mision aparece en el registro de XP."""
    return f"mision-{mission.pk}"


def _semanales_pendientes(fecha: dt.date):
    lunes, domingo = progression.rango_de_la_semana(fecha)
    hechas = MissionLog.objects.filter(
        fecha__range=(lunes, domingo), completada=True
    ).values_list("mission_id", flat=True)
    return Mission.objects.filter(
        tipo=Mission.Tipo.SEMANAL, activa=True
    ).exclude(pk__in=hechas)


def misiones_de_hoy(fecha: dt.date | None = None):
    """Misiones que tocan hoy.

    - Miercoles: ninguna. El dia esta protegido y no genera ni XP ni penalizacion.
    - Domingo: solo las semanales pendientes (la revision de las 20:15 entre ellas);
      las diarias no se piden porque el domingo esta fuera del sistema.
    - Resto de dias: las diarias activas mas las semanales aun no cerradas.
    """
    fecha = fecha or timezone.localdate()

    if fecha.weekday() == progression.MIERCOLES:
        return Mission.objects.none()

    semanales = _semanales_pendientes(fecha)
    if fecha.weekday() == progression.DOMINGO:
        return semanales.order_by("orden", "titulo")

    diarias = Mission.objects.filter(
        tipo=Mission.Tipo.DIARIA, activa=True, es_minima=False
    )
    return (diarias | semanales).order_by("tipo", "orden", "titulo")


def modo_dia_minimo():
    """Lo imprescindible de un dia malo: solo las misiones marcadas como minimas."""
    return Mission.objects.filter(activa=True, es_minima=True).order_by("orden", "titulo")


def esta_completada(mission: Mission, fecha: dt.date | None = None) -> bool:
    fecha = fecha or timezone.localdate()
    return MissionLog.objects.filter(
        mission=mission, fecha=fecha, completada=True
    ).exists()


def _categoria_de(mission: Mission) -> str:
    """Las misiones de soporte (salud, limites personales) no son resultado."""
    if mission.attribute and mission.attribute.categoria in {"SALUD", "PERSONAL"}:
        return Categoria.SOPORTE
    return Categoria.RESULTADO


@transaction.atomic
def completar_mision(
    mission: Mission, evidencia: str = "", fecha: dt.date | None = None
) -> MissionLog:
    """Da una mision por hecha y concede su XP. Idempotente dentro del mismo dia.

    Si la mision ya estaba completada hoy, devuelve el registro existente sin
    volver a puntuar.
    """
    fecha = fecha or timezone.localdate()

    registro, _ = MissionLog.objects.select_for_update().get_or_create(
        mission=mission, fecha=fecha
    )
    if registro.completada:
        return registro

    evidencia = (evidencia or "").strip()
    if mission.evidencia_requerida and not evidencia:
        raise EvidenciaRequerida(mission.definicion_terminada)

    evento = progression.registrar_xp(
        slug_de_mision(mission),
        xp=mission.xp,
        categoria=_categoria_de(mission),
        descripcion=mission.titulo,
        fecha=fecha,
        fuente=XPEvent.Fuente.MISION,
        objeto_relacionado=f"mission:{mission.pk}",
    )

    registro.completada = True
    registro.evidencia_texto = evidencia
    registro.xp_otorgado = evento.xp_neto
    registro.save(update_fields=["completada", "evidencia_texto", "xp_otorgado"])
    return registro


def panel_de_misiones(fecha: dt.date | None = None, minimo: bool = False) -> dict:
    """Contexto del bloque de misiones del panel."""
    fecha = fecha or timezone.localdate()
    protegido = fecha.weekday() == progression.MIERCOLES

    if protegido:
        misiones = Mission.objects.none()
    elif minimo:
        misiones = modo_dia_minimo()
    else:
        misiones = misiones_de_hoy(fecha)

    hechas = set(
        MissionLog.objects.filter(fecha=fecha, completada=True).values_list(
            "mission_id", flat=True
        )
    )
    filas = [
        {"mision": mision, "completada": mision.pk in hechas} for mision in misiones
    ]
    return {
        "fecha": fecha,
        "dia_protegido": protegido,
        "modo_minimo": minimo,
        "filas": filas,
        "hechas": sum(1 for fila in filas if fila["completada"]),
        "total": len(filas),
    }
