"""Logica de negocio de la app business.

Las alertas del panel salen de aqui: dinero parado, pipeline frio y exceso de WIP.
"""
from __future__ import annotations

import datetime as dt

from decimal import Decimal

from django.db import transaction
from django.db.models import F, Q, Sum
from django.utils import timezone

from progression import services as progression
from progression.models import Penalty

from .models import Client, Deal, Invoice, Project

# Reglas duras del sistema (docs/sistema-v2.md, §6 y §9).
DIAS_SIN_SEGUIMIENTO = 7
WIP_MAXIMO = 2


def facturas_vencidas(fecha: dt.date | None = None):
    """Facturas emitidas, no cobradas y fuera de plazo."""
    fecha = fecha or timezone.localdate()
    return Invoice.objects.filter(cobrada=False, vencimiento__lt=fecha).select_related(
        "client"
    ).order_by("vencimiento")


def deals_sin_tocar(fecha: dt.date | None = None):
    """Oportunidades abiertas con mas de 7 dias sin seguimiento."""
    fecha = fecha or timezone.localdate()
    limite = fecha - dt.timedelta(days=DIAS_SIN_SEGUIMIENTO)
    abiertos = Deal.objects.filter(estado__in=Deal.ESTADOS_ABIERTOS)
    return abiertos.filter(ultimo_toque__lt=limite).union(
        abiertos.filter(ultimo_toque__isnull=True, fecha_primer_contacto__lt=limite)
    ).order_by("ultimo_toque", "fecha_primer_contacto")


def proyectos_activos():
    return Project.objects.filter(estado=Project.Estado.ACTIVO).select_related("client")


def alertas(fecha: dt.date | None = None) -> list[dict]:
    """Lo que esta costando dinero hoy. Vacia si no hay nada rojo."""
    fecha = fecha or timezone.localdate()
    avisos = []

    vencidas = list(facturas_vencidas(fecha))
    if vencidas:
        importe = sum(f.importe for f in vencidas)
        a_reclamar = [f for f in vencidas if f.hay_que_reclamar]
        avisos.append(
            {
                "clave": "facturas",
                "titulo": f"{len(vencidas)} factura(s) vencida(s): {importe:.0f} EUR",
                "detalle": (
                    f"{len(a_reclamar)} pasan de {Invoice.DIAS_PARA_RECLAMAR} dias. "
                    "Reclamacion antes que cualquier otra tarea."
                )
                if a_reclamar
                else "Todavia dentro de los 15 dias. Vigilalas.",
                "items": [f"{f.client.nombre} · {f.importe:.0f} EUR · {f.dias_vencida} d" for f in vencidas],
                "url": "/admin/business/invoice/?cobrada__exact=0",
            }
        )

    frios = list(deals_sin_tocar(fecha))
    if frios:
        avisos.append(
            {
                "clave": "pipeline",
                "titulo": f"{len(frios)} oportunidad(es) sin tocar en mas de {DIAS_SIN_SEGUIMIENTO} dias",
                "detalle": "Propuesta sin seguimiento mas de 7 dias: -100 XP. Seguimiento primero.",
                "items": [f"{d.negocio} · {d.dias_sin_toque} d" for d in frios],
                "url": "/admin/business/deal/",
            }
        )

    activos = list(proyectos_activos())
    if len(activos) > WIP_MAXIMO:
        avisos.append(
            {
                "clave": "wip",
                "titulo": f"{len(activos)} proyectos abiertos (maximo {WIP_MAXIMO})",
                "detalle": "Cerrar o congelar uno. Con 10 h/semana, el tercero garantiza incumplir los tres.",
                "items": [p.nombre for p in activos],
                "url": "/admin/business/project/?estado__exact=ACTIVO",
            }
        )
    return avisos


def recurrente_activo() -> Decimal:
    """EUR/mes recurrentes de los clientes activos.

    Decimal, no float: esto es dinero.
    """
    total = Client.objects.filter(estado=Client.Estado.ACTIVO).aggregate(
        total=Sum("mrr")
    )["total"]
    return total or Decimal("0")


# --- Suelo de precio y XP ---------------------------------------------------

# Suelo de precio (docs/sistema-v2.md, §7.4). Aceptar por debajo cuesta -250 XP.
SUELO_PRECIO = Decimal("1500")
XP_POR_EURO_COBRADO = Decimal("10")  # 1 XP por cada 10 EUR.
OBJETIVO_RECURRENTE = Decimal("450")  # EUR/mes a 90 dias.

# Umbrales que suben al cambiar de rango (docs/sistema-v2.md, SS3). Solo estan
# aqui los dos que el documento nombra con cifra: al llegar a Especialista el
# suelo pasa a 1.800 EUR y el recurrente objetivo a 800 EUR/mes. Los 6
# contactos/semana y los 40 EUR/h NO suben: el documento los mantiene fijos.
SUELO_POR_RANGO = {3: Decimal("1800")}
RECURRENTE_POR_RANGO = {3: Decimal("800")}


def _rango_actual():
    """Rango del perfil, deducido del nivel si no esta asignado a mano."""
    from core import services as core_services
    from core.models import Profile

    perfil = Profile.get()
    return perfil.rango or core_services.rango_para_nivel(perfil.nivel)


def _por_rango(tabla: dict, base: Decimal, rango=None) -> Decimal:
    """El umbral mas alto de los rangos que ya has alcanzado.

    Nunca baja: un umbral que subiste no vuelve atras aunque cambie el rango.
    """
    if rango is None:
        rango = _rango_actual()
    if rango is None:
        return base
    alcanzados = [v for orden, v in tabla.items() if rango.orden >= orden]
    return max(alcanzados) if alcanzados else base


def suelo_precio(rango=None) -> Decimal:
    """Suelo de precio vigente. 1.500 EUR, 1.800 EUR desde Especialista."""
    return _por_rango(SUELO_POR_RANGO, SUELO_PRECIO, rango)


def objetivo_recurrente(rango=None) -> Decimal:
    """Recurrente objetivo. 450 EUR/mes, 800 EUR/mes desde Especialista."""
    return _por_rango(RECURRENTE_POR_RANGO, OBJETIVO_RECURRENTE, rango)

# Resaltado del pipeline: ambar a partir de 5 dias, rojo a partir de 7.
DIAS_AMBAR = 5
DIAS_ROJO = DIAS_SIN_SEGUIMIENTO  # 7


def nivel_alerta(dias: int | None) -> str:
    """Color de la fila del pipeline segun los dias sin toque."""
    if dias is None:
        return ""
    if dias >= DIAS_ROJO:
        return "rojo"
    if dias >= DIAS_AMBAR:
        return "ambar"
    return ""


@transaction.atomic
def toque_rapido(deal: Deal, fecha: dt.date | None = None) -> Deal:
    """Registra un toque de hoy en la oportunidad y puntua la accion comercial.

    La XP se concede a traves de la mision diaria D1 cuando existe, para que el
    toque cuente tambien para la racha y no se pueda puntuar dos veces el mismo
    dia. Si no hay D1, se puntua con la regla suelta.
    """
    fecha = fecha or timezone.localdate()
    deal.ultimo_toque = fecha
    deal.save(update_fields=["ultimo_toque"])

    from missions import services as missions_services
    from missions.models import Mission

    d1 = Mission.objects.filter(
        tipo=Mission.Tipo.DIARIA,
        orden=progression.ORDEN_ACCION_COMERCIAL,
        es_minima=False,
        activa=True,
    ).first()

    evidencia = f"Toque a {deal.negocio}"
    if d1 is not None:
        missions_services.completar_mision(d1, evidencia=evidencia, fecha=fecha)
    else:
        progression.registrar_xp(
            "accion-comercial",
            descripcion=evidencia,
            fecha=fecha,
            fuente="AUTO",
            objeto_relacionado=f"deal:{deal.pk}",
        )
    return deal


@transaction.atomic
def marcar_cobrada(invoice: Invoice, fecha: dt.date | None = None) -> Invoice:
    """Da una factura por cobrada y concede 1 XP por cada 10 EUR (tope 400/sem).

    Idempotente: una factura ya cobrada no vuelve a puntuar.
    """
    if invoice.cobrada:
        return invoice
    fecha = fecha or timezone.localdate()

    invoice.cobrada = True
    invoice.fecha_cobro = fecha
    invoice.save(update_fields=["cobrada", "fecha_cobro"])

    xp = int(invoice.importe / XP_POR_EURO_COBRADO)
    if xp:
        progression.registrar_xp(
            "dinero-cobrado",
            xp=xp,
            descripcion=f"{invoice.client.nombre}: {invoice.concepto}",
            fecha=fecha,
            fuente="AUTO",
            objeto_relacionado=f"invoice:{invoice.pk}",
        )
    return invoice


# --- XP por hechos comerciales ----------------------------------------------
#
# La tabla de resultados de docs/sistema-v2.md se concede aqui, cuando el hecho
# ocurre de verdad: al mover una oportunidad, al entregar un proyecto o al
# firmar un recurrente. Cada hecho puntua UNA sola vez: la idempotencia se
# comprueba contra el objeto relacionado del evento de XP.

# Un cierre puntua como "proyecto cerrado" a partir del suelo de precio.
# La tabla de XP fija el cierre en 1.500 EUR y no lo sube por rango, a
# diferencia del suelo de precio. Son dos cosas distintas.
VALOR_PROYECTO_CERRADO = Decimal("1500")


def _ya_puntuado(accion_slug: str, objeto: str) -> bool:
    """True si ese hecho concreto ya concedio XP alguna vez."""
    from progression.models import XPEvent

    return XPEvent.objects.filter(
        accion_slug=accion_slug, objeto_relacionado=objeto
    ).exists()


def _puntuar_una_vez(
    accion_slug: str, objeto: str, descripcion: str, fecha: dt.date | None = None
):
    """Concede la XP de la regla si ese objeto no la habia recibido ya."""
    if _ya_puntuado(accion_slug, objeto):
        return None
    return progression.registrar_xp(
        accion_slug,
        descripcion=descripcion,
        fecha=fecha or timezone.localdate(),
        fuente="AUTO",
        objeto_relacionado=objeto,
    )


@transaction.atomic
def puntuar_deal(deal: Deal, estado_anterior: str, fecha: dt.date | None = None) -> list:
    """XP de los hechos que produce mover una oportunidad de estado.

    - A "propuesta enviada": 80 XP (tope 240/semana).
    - A "ganado" por encima del suelo: 250 XP de proyecto cerrado.
    - A "perdido" marcado como rechazo por precio bajo: 150 XP (tope 150/semana).

    Volver a un estado ya puntuado no vuelve a dar XP.
    """
    if deal.estado == estado_anterior:
        return []

    eventos = []
    objeto = f"deal:{deal.pk}"

    if deal.estado == Deal.Estado.PROPUESTA:
        eventos.append(
            _puntuar_una_vez(
                "propuesta-enviada", objeto, f"Propuesta enviada a {deal.negocio}", fecha
            )
        )

    elif deal.estado == Deal.Estado.GANADO:
        if deal.valor_potencial >= VALOR_PROYECTO_CERRADO:
            eventos.append(
                _puntuar_una_vez(
                    "proyecto-cerrado",
                    objeto,
                    f"{deal.negocio} cerrado a {deal.valor_potencial:.0f} EUR",
                    fecha,
                )
            )

    elif deal.estado == Deal.Estado.PERDIDO and deal.rechazado_por_precio:
        eventos.append(
            _puntuar_una_vez(
                "proyecto-rechazado-precio-bajo",
                objeto,
                f"{deal.negocio} rechazado por precio bajo",
                fecha,
            )
        )

    return [e for e in eventos if e is not None]


@transaction.atomic
def puntuar_proyecto(
    project: Project, estado_anterior: str, fecha: dt.date | None = None
) -> list:
    """200 XP la primera vez que un proyecto pasa a entregado."""
    if project.estado == estado_anterior or project.estado != Project.Estado.ENTREGADO:
        return []
    evento = _puntuar_una_vez(
        "entrega-aceptada",
        f"project:{project.pk}",
        f"{project.nombre} entregado y aceptado",
        fecha,
    )
    return [evento] if evento else []


@transaction.atomic
def puntuar_recurrente(
    client: Client, mrr_anterior, fecha: dt.date | None = None
) -> list:
    """350 XP la primera vez que un cliente pasa a aportar recurrente."""
    if client.mrr <= 0 or Decimal(mrr_anterior or 0) > 0:
        return []
    evento = _puntuar_una_vez(
        "contrato-recurrente-firmado",
        f"client:{client.pk}",
        f"{client.nombre}: {client.mrr:.0f} EUR/mes recurrentes",
        fecha,
    )
    return [evento] if evento else []


@transaction.atomic
def registrar_excepcion_de_suelo(project: Project, motivo: str) -> Penalty:
    """Documenta por escrito un proyecto aceptado por debajo del suelo.

    El documento no prohibe la excepcion: la cobra a -250 XP y exige motivo
    escrito. Esto es exactamente eso.
    """
    penalizacion = Penalty.objects.create(
        fecha=timezone.localdate(),
        regla_slug="proyecto-por-debajo-del-suelo",
        descripcion=f"{project.nombre}: {project.precio:.0f} EUR (suelo {suelo_precio():.0f} EUR)",
        xp=-250,
        correccion_exigida=motivo,
        resuelta=True,  # El motivo escrito ES la correccion exigida.
    )
    progression.registrar_xp(
        "proyecto-por-debajo-del-suelo",
        descripcion=penalizacion.descripcion,
        fuente="AUTO",
        objeto_relacionado=f"project:{project.pk}",
    )
    return penalizacion


# --- Resumenes para las vistas ---------------------------------------------


def _rango_del_mes(fecha: dt.date) -> tuple[dt.date, dt.date]:
    primero = fecha.replace(day=1)
    if primero.month == 12:
        siguiente = primero.replace(year=primero.year + 1, month=1)
    else:
        siguiente = primero.replace(month=primero.month + 1)
    return primero, siguiente - dt.timedelta(days=1)


def filas_pipeline(estado: str = "", fecha: dt.date | None = None) -> list[dict]:
    """Pipeline ordenado por fecha del proximo paso, con su nivel de alerta."""
    fecha = fecha or timezone.localdate()
    deals = Deal.objects.all()
    if estado:
        deals = deals.filter(estado=estado)
    # Las que no tienen fecha de proximo paso van al final.
    deals = deals.order_by(F("fecha_proximo_paso").asc(nulls_last=True), "-fecha_primer_contacto")
    return [{"deal": d, "dias": d.dias_sin_toque, "alerta": nivel_alerta(d.dias_sin_toque)} for d in deals]


def resumen_pipeline(estado: str = "", fecha: dt.date | None = None) -> dict:
    filas = filas_pipeline(estado, fecha)
    abiertas = [f for f in filas if f["deal"].esta_abierto]
    return {
        "filas": filas,
        "estado_activo": estado,
        "estados": Deal.Estado.choices,
        "abiertas": len(abiertas),
        "valor_abierto": sum((f["deal"].valor_potencial for f in abiertas), Decimal("0")),
        "en_rojo": sum(1 for f in filas if f["alerta"] == "rojo"),
        "en_ambar": sum(1 for f in filas if f["alerta"] == "ambar"),
    }


def resumen_facturas(fecha: dt.date | None = None) -> dict:
    """Cobrado y pendiente del mes, mas el aviso de vencidas."""
    fecha = fecha or timezone.localdate()
    primero, ultimo = _rango_del_mes(fecha)

    cobrado = Invoice.objects.filter(
        cobrada=True, fecha_cobro__range=(primero, ultimo)
    ).aggregate(total=Sum("importe"))["total"] or Decimal("0")

    pendientes = Invoice.objects.filter(cobrada=False).select_related("client")
    pendiente = pendientes.aggregate(total=Sum("importe"))["total"] or Decimal("0")

    vencidas = list(facturas_vencidas(fecha))
    return {
        "facturas": Invoice.objects.select_related("client").order_by("-fecha_emision")[:100],
        "cobrado_mes": cobrado,
        "pendiente_total": pendiente,
        "vencidas": vencidas,
        "importe_vencido": sum((f.importe for f in vencidas), Decimal("0")),
        "a_reclamar": [f for f in vencidas if f.hay_que_reclamar],
        "mes": primero,
    }


def resumen_clientes() -> dict:
    """Clientes con su MRR y el recurrente total frente al objetivo."""
    clientes = Client.objects.annotate(
        facturado=Sum("facturas__importe", filter=Q(facturas__cobrada=True))
    ).order_by("-mrr", "nombre")
    total = recurrente_activo()
    objetivo = objetivo_recurrente()
    return {
        "clientes": clientes,
        "total_mrr": total,
        "objetivo": objetivo,
        "pct_objetivo": min(100, int(total / objetivo * 100)) if objetivo else 0,
        "falta": max(Decimal("0"), objetivo - total),
    }


def resumen_proyectos() -> dict:
    """Proyectos con horas estimadas frente a reales y tarifa efectiva."""
    proyectos = Project.objects.select_related("client").order_by("estado", "-fecha_inicio")
    activos = [p for p in proyectos if p.estado == Project.Estado.ACTIVO]
    return {
        "proyectos": proyectos,
        "activos": len(activos),
        "wip_maximo": WIP_MAXIMO,
        "wip_excedido": len(activos) > WIP_MAXIMO,
    }


def tarifa_efectiva_mes(fecha: dt.date | None = None) -> Decimal | None:
    """Metrica maestra: EUR cobrados en el mes / horas reales con actividad en el mes.

    Las horas se toman de los proyectos vivos en el mes (activos, o entregados
    dentro del propio mes), porque el modelo no fecha las horas una a una.
    """
    fecha = fecha or timezone.localdate()
    primero, ultimo = _rango_del_mes(fecha)

    cobrado = Invoice.objects.filter(
        cobrada=True, fecha_cobro__range=(primero, ultimo)
    ).aggregate(total=Sum("importe"))["total"] or Decimal("0")

    horas = Project.objects.filter(
        Q(estado=Project.Estado.ACTIVO) | Q(fecha_entrega__range=(primero, ultimo))
    ).aggregate(total=Sum("horas_reales"))["total"] or Decimal("0")

    if not horas:
        return None
    return (cobrado / horas).quantize(Decimal("0.01"))
