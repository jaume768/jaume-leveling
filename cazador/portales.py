"""Portales semanales.

Cada lunes se abren tres portales (E, C y A) y eliges uno. El objetivo sale de
tus atributos mas bajos y se mide con datos reales de esa semana. Superarlo da
botin (runas y, en los dificiles, un marco); fallarlo no quita XP: el portal se
desborda y queda en el registro. No se inventa XP en ningun caso.
"""
from __future__ import annotations

import datetime as dt
import random

from django.apps import apps
from django.db import transaction
from django.utils import timezone

from .models import Aviso, Cazador, Logro, Portal

DIFICULTADES = ("E", "C", "A")


def _lunes(fecha: dt.date) -> dt.date:
    return fecha - dt.timedelta(days=fecha.weekday())


# --- Medidas de la semana ------------------------------------------------------------


def _contactos(lunes, domingo):
    Deal = apps.get_model("business", "Deal")
    return Deal.objects.filter(fecha_primer_contacto__range=(lunes, domingo)).count()


def _toques(lunes, domingo):
    Deal = apps.get_model("business", "Deal")
    return Deal.objects.filter(ultimo_toque__range=(lunes, domingo)).count()


def _misiones(lunes, domingo, *slugs):
    MissionLog = apps.get_model("missions", "MissionLog")
    return MissionLog.objects.filter(
        fecha__range=(lunes, domingo), completada=True, mission__slug__in=slugs
    ).count()


def _dias_de_racha(lunes, domingo):
    from . import services

    return len(services.dias_con_accion(lunes, domingo))


def _xp(lunes, domingo):
    from django.db.models import Sum

    XPEvent = apps.get_model("progression", "XPEvent")
    return XPEvent.objects.filter(fecha__range=(lunes, domingo), xp_neto__gt=0).aggregate(
        t=Sum("xp_neto"))["t"] or 0


def _cobros(lunes, domingo):
    Invoice = apps.get_model("business", "Invoice")
    return Invoice.objects.filter(cobrada=True, fecha_cobro__range=(lunes, domingo)).count()


# tipo: (titulo, descripcion con {n}, medida, atributo que entrena, objetivos E/C/A)
TIPOS = {
    "contactos": ("Portal de la caza", "Abre {n} contacto{s} nuevo{s} en el pipeline.",
                  _contactos, "ventas", (3, 6, 10)),
    "toques": ("Portal del seguimiento", "Da seguimiento a {n} oportunidad{es}.",
               _toques, "ventas", (3, 5, 8)),
    "referidos": ("Portal de los aliados", "Pide {n} referido{s}.",
                  lambda l, d: _misiones(l, d, "secundaria-referido", "peticion-de-referido"),
                  "red-profesional", (1, 2, 3)),
    "conversaciones": ("Portal de la palabra", "Ten {n} conversaci{ones} comercial{es} de verdad.",
                       lambda l, d: _misiones(l, d, "secundaria-conversacion"),
                       "comunicacion", (1, 2, 3)),
    "cierres": ("Portal del orden", "Haz el cierre del día {n} {veces}.",
                lambda l, d: _misiones(l, d, "cierre-del-dia", "cierre-del-dia-minima"),
                "organizacion", (3, 4, 5)),
    "racha": ("Portal de la constancia", "Cumple la misión de racha {n} día{s}.",
              _dias_de_racha, "disciplina", (3, 4, 5)),
    "casos": ("Portal del cronista", "Avanza un caso de estudio {n} {veces}.",
              lambda l, d: _misiones(l, d, "secundaria-caso"), "marca-portfolio", (1, 2, 3)),
    "plantilla": ("Portal del artesano", "Mejora la plantilla de entrega {n} {veces}.",
                  lambda l, d: _misiones(l, d, "secundaria-plantilla"), "producto", (1, 2, 3)),
    "xp": ("Portal del poder", "Gana {n} XP esta semana.", _xp, "disciplina", (400, 600, 850)),
    "cobro": ("Portal del tesoro", "Cobra {n} factura{s} esta semana.", _cobros, "finanzas", (1, 1, 2)),
}


def progreso(portal: Portal) -> int:
    lunes = portal.lunes
    return int(TIPOS[portal.tipo][2](lunes, lunes + dt.timedelta(days=6)))


def _tipos_por_debilidad(rng: random.Random) -> list[str]:
    """Tipos ordenados de mas a menos necesario segun tus atributos mas bajos."""
    from core.models import Attribute

    valores = dict(Attribute.objects.values_list("slug", "valor"))
    tipos = list(TIPOS)
    rng.shuffle(tipos)  # desempate distinto cada semana
    return sorted(tipos, key=lambda t: valores.get(TIPOS[t][3], 50))


def abrir_portales(fecha: dt.date | None = None) -> list[Portal]:
    """Ofrece los tres portales de la semana si aun no estan. Idempotente."""
    fecha = fecha or timezone.localdate()
    lunes = _lunes(fecha)
    existentes = list(Portal.objects.filter(lunes=lunes))
    if existentes:
        return existentes
    rng = random.Random(lunes.toordinal())
    elegidos = _tipos_por_debilidad(rng)[:3]
    # El mas necesario va en el dificil: el gran botin esta donde mas te cuesta.
    portales = []
    for dificultad, tipo in zip(("A", "C", "E"), elegidos):
        titulo, descripcion, _, atributo, objetivos = TIPOS[tipo]
        objetivo = objetivos[DIFICULTADES.index(dificultad)]
        portales.append(Portal.objects.create(
            lunes=lunes, dificultad=dificultad, tipo=tipo, atributo=atributo,
            titulo=titulo, descripcion=redactar(descripcion, objetivo), objetivo=objetivo,
        ))
    from . import services

    services.avisar(Aviso.Tipo.SISTEMA, "Se han abierto 3 portales",
                    "Elige uno en Hoy. Se cierran el domingo a las 23:59.",
                    clave=f"portales:{lunes.isoformat()}")
    return sorted(portales, key=lambda p: DIFICULTADES.index(p.dificultad))


@transaction.atomic
def entrar(pk: int, fecha: dt.date | None = None) -> Portal:
    """Elige un portal de la semana. Los otros dos se cierran."""
    fecha = fecha or timezone.localdate()
    lunes = _lunes(fecha)
    portal = Portal.objects.select_for_update().get(pk=pk, lunes=lunes)
    if Portal.objects.filter(lunes=lunes).exclude(estado=Portal.Estado.OFRECIDO).exclude(
            estado=Portal.Estado.DESCARTADO).exists():
        raise ValueError("Esta semana ya entraste en un portal.")
    Portal.objects.filter(lunes=lunes).exclude(pk=pk).update(estado=Portal.Estado.DESCARTADO)
    portal.estado = Portal.Estado.ABIERTO
    portal.save(update_fields=["estado"])
    revisar(fecha)
    return Portal.objects.get(pk=pk)


def _botin(portal: Portal) -> str:
    from . import services

    ficha = Cazador.get()
    runas = {"E": 1, "C": 2, "A": 3}[portal.dificultad]
    ficha.fragmentos += runas
    partes = [f"{runas} runa{'s' if runas > 1 else ''}"]
    while ficha.fragmentos >= services.FRAGMENTOS_POR_ESCUDO and services.escudos_disponibles() < services.MAX_ESCUDOS:
        ficha.fragmentos -= services.FRAGMENTOS_POR_ESCUDO
        services.Escudo.objects.create(motivo=f"Forjado con runas del portal ({portal.lunes:%d/%m})")
        partes.append("un escudo forjado")
    ficha.save(update_fields=["fragmentos"])
    if portal.dificultad == "A":
        libres = sorted(set(services.MARCOS) - services.marcos_desbloqueados())
        if libres:
            clave = random.Random(portal.pk).choice(libres)
            Logro.objects.get_or_create(tipo=Logro.Tipo.MARCO, clave=clave)
            partes.append(f"marco «{services.MARCOS[clave]['nombre']}»")
    return " + ".join(partes)


def revisar(fecha: dt.date | None = None) -> list[str]:
    """Cierra lo que toque: superado en cuanto se cumple, desbordado al acabar la semana."""
    from . import services

    fecha = fecha or timezone.localdate()
    hechos = []
    for portal in Portal.objects.filter(estado=Portal.Estado.ABIERTO):
        domingo = portal.lunes + dt.timedelta(days=6)
        if progreso(portal) >= portal.objetivo:
            portal.estado = Portal.Estado.SUPERADO
            portal.botin = _botin(portal)
            portal.cerrado = fecha
            portal.save()
            services.avisar(Aviso.Tipo.COFRE, f"Portal {portal.dificultad} superado",
                            f"{portal.titulo}. Botín: {portal.botin}.", clave=f"portal-superado:{portal.pk}")
            hechos.append(f"portal {portal.pk} superado")
        elif fecha > domingo:
            portal.estado = Portal.Estado.DESBORDADO
            portal.cerrado = domingo
            portal.save()
            services.avisar(Aviso.Tipo.PENALIZACION, "Portal desbordado",
                            f"{portal.titulo} se cerró sin completar. Sin pérdida de XP.",
                            clave=f"portal-desbordado:{portal.pk}")
            hechos.append(f"portal {portal.pk} desbordado")
    # Los ofrecidos que nadie eligio caducan con su semana.
    Portal.objects.filter(estado=Portal.Estado.OFRECIDO, lunes__lt=_lunes(fecha)).update(
        estado=Portal.Estado.DESCARTADO)
    if hechos and desbordados_seguidos() >= 3:
        services.avisar(Aviso.Tipo.SISTEMA, "Tres portales desbordados seguidos",
                        "Elige el portal E la próxima semana: el objetivo es volver a ganar.",
                        clave=f"tres-desbordados:{fecha.isoformat()}")
    return hechos


def desbordados_seguidos() -> int:
    seguidos = 0
    for estado in Portal.objects.filter(
            estado__in=(Portal.Estado.SUPERADO, Portal.Estado.DESBORDADO)
    ).order_by("-lunes").values_list("estado", flat=True):
        if estado != Portal.Estado.DESBORDADO:
            break
        seguidos += 1
    return seguidos


def superados(dificultad: str | None = None) -> int:
    consulta = Portal.objects.filter(estado=Portal.Estado.SUPERADO)
    if dificultad:
        consulta = consulta.filter(dificultad=dificultad)
    return consulta.count()


def contexto(fecha: dt.date | None = None) -> dict:
    """Lo que pinta la ventana de portales en Hoy."""
    fecha = fecha or timezone.localdate()
    portales = abrir_portales(fecha)
    revisar(fecha)
    lunes = _lunes(fecha)
    semana = list(Portal.objects.filter(lunes=lunes))
    activo = next((p for p in semana if p.estado != Portal.Estado.OFRECIDO
                   and p.estado != Portal.Estado.DESCARTADO), None)
    domingo = lunes + dt.timedelta(days=6)
    filas = []
    for p in sorted(portales if not activo else [activo], key=lambda p: DIFICULTADES.index(p.dificultad)):
        actual = progreso(p)
        filas.append({"portal": p, "actual": actual,
                      "pct": min(100, int(actual * 100 / p.objetivo)) if p.objetivo else 0})
    return {
        "activo": activo,
        "filas": filas,
        "dias_restantes": (domingo - fecha).days + 1,
        "superados": superados(),
    }


def redactar(plantilla: str, n: int) -> str:
    """Rellena la descripcion de un portal con singular o plural segun n."""
    uno = n == 1
    return plantilla.format(
        n=n, s="" if uno else "s", es="" if uno else "es",
        veces="vez" if uno else "veces", ones="ón" if uno else "ones",
    )
