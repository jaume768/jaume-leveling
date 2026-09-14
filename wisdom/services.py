"""Lógica de negocio de la app wisdom.

Dos formas de elegir máxima: la del día (rotación estable) y la contextual,
que responde a lo que está fallando ahora mismo.
"""
from __future__ import annotations

import datetime as dt

from django.db.models import Sum
from django.utils import timezone

from .models import Maxim

# Los diez libros son los números 1-10; del 11 en adelante, el decálogo.
ULTIMO_LIBRO = 10

# Tags con los que se filtra la vista de máximas.
TAGS = ["precio", "cobro", "pipeline", "dependencia", "negociacion", "foco", "tiempo"]

# Umbral de concentración de cliente (docs/sistema-v3-maquiavelo.md, Libro II).
CONCENTRACION_MAXIMA = 0.35


def maxima_del_dia(fecha: dt.date | None = None) -> Maxim | None:
    """Una máxima por día, sin repetir hasta agotar el ciclo completo.

    El índice avanza de uno en uno con el día, así que recorre las N máximas
    antes de volver a la primera, y el mismo día siempre da la misma.
    """
    fecha = fecha or timezone.localdate()
    total = Maxim.objects.count()
    if not total:
        return None
    return Maxim.objects.order_by("numero")[fecha.toordinal() % total]


def _libro(nombre: str) -> Maxim | None:
    """El libro, no la regla del decálogo que lo cita."""
    return Maxim.objects.filter(libro=nombre, numero__lte=ULTIMO_LIBRO).first()


def _cliente_concentrado(fecha: dt.date):
    """Cliente que pasa del 35% de lo facturado en el año, si lo hay."""
    from business.models import Client, Invoice

    cobrado_anio = Invoice.objects.filter(
        cobrada=True, fecha_cobro__year=fecha.year
    ).aggregate(total=Sum("importe"))["total"]
    if not cobrado_anio:
        return None, 0.0

    por_cliente = (
        Invoice.objects.filter(cobrada=True, fecha_cobro__year=fecha.year)
        .values("client")
        .annotate(total=Sum("importe"))
        .order_by("-total")
        .first()
    )
    if not por_cliente:
        return None, 0.0

    cuota = float(por_cliente["total"]) / float(cobrado_anio)
    if cuota <= CONCENTRACION_MAXIMA:
        return None, cuota
    return Client.objects.filter(pk=por_cliente["client"]).first(), cuota


def _contactos_de_la_semana(fecha: dt.date) -> int:
    """Contactos nuevos más oportunidades tocadas en la semana ISO en curso."""
    from business.models import Deal
    from progression import services as progression

    lunes, domingo = progression.rango_de_la_semana(fecha)
    nuevos = Deal.objects.filter(fecha_primer_contacto__range=(lunes, domingo))
    tocados = Deal.objects.filter(ultimo_toque__range=(lunes, domingo))
    return nuevos.union(tocados).count()


def maxima_contextual(fecha: dt.date | None = None) -> dict:
    """La máxima que toca hoy según lo que esté fallando.

    Orden de prioridad: dinero parado, precio por debajo del suelo, dependencia
    de un cliente y pipeline vacío. Si no falla nada, la máxima del día.
    """
    from business.models import Project
    from business.services import SUELO_PRECIO, facturas_vencidas

    fecha = fecha or timezone.localdate()

    vencidas = facturas_vencidas(fecha)
    if vencidas.exists():
        dias = max(f.dias_vencida for f in vencidas)
        return {
            "maxima": _libro("Libro VIII"),
            "motivo": f"Tienes una factura con {dias} días de retraso.",
            "contextual": True,
        }

    baratos = Project.objects.filter(
        precio__lt=SUELO_PRECIO, estado=Project.Estado.ACTIVO
    )
    if baratos.exists():
        proyecto = baratos.order_by("precio").first()
        return {
            "maxima": _libro("Libro III"),
            "motivo": f"“{proyecto.nombre}” está activo a {proyecto.precio:.0f} €, por debajo del suelo.",
            "contextual": True,
        }

    cliente, cuota = _cliente_concentrado(fecha)
    if cliente is not None:
        return {
            "maxima": _libro("Libro II"),
            "motivo": f"{cliente.nombre} es el {cuota:.0%} de lo facturado este año.",
            "contextual": True,
        }

    if _contactos_de_la_semana(fecha) == 0:
        return {
            "maxima": _libro("Libro I"),
            "motivo": "La semana lleva 0 contactos.",
            "contextual": True,
        }

    return {"maxima": maxima_del_dia(fecha), "motivo": "", "contextual": False}


def maximas(tag: str = ""):
    """Todas las máximas, filtrables por tag."""
    consulta = Maxim.objects.order_by("numero")
    if tag:
        consulta = consulta.filter(tags__icontains=tag)
    return consulta


# --- Consejo ----------------------------------------------------------------

# Consultas predefinidas de la vista de consejo.
CONSULTAS = {
    "ahora": {
        "etiqueta": "¿Qué hago ahora mismo?",
        "pregunta": (
            "Mirando el contexto, ¿qué hago ahora mismo? Dame como mucho tres acciones "
            "ordenadas por lo que más ingreso desbloquea, y marca cuál es la de hoy."
        ),
    },
    "semana": {
        "etiqueta": "Revisa mi semana",
        "pregunta": (
            "Revisa mi semana con los datos del contexto. Qué ha funcionado, qué no, "
            "y dónde me estoy engañando. Sé concreto con las cifras."
        ),
    },
    "propuesta": {
        "etiqueta": "Critica esta propuesta",
        "pregunta": (
            "Critica esta propuesta comercial. Mira el precio contra mi suelo, el alcance "
            "contra mis 10 h/semana y qué falta para que no se desborde:"
        ),
        "necesita_texto": True,
    },
}


def gasto_del_mes(fecha=None):
    """Gasto acumulado en consultas durante el mes en curso."""
    from django.db.models import Count, Sum

    from .models import AdviceSession

    fecha = fecha or timezone.localdate()
    sesiones = AdviceSession.objects.filter(
        fecha__year=fecha.year, fecha__month=fecha.month
    )
    agregado = sesiones.aggregate(
        total=Sum("coste_estimado"),
        tokens_in=Sum("tokens_in"),
        tokens_out=Sum("tokens_out"),
        consultas=Count("id"),
    )
    return {
        "mes": fecha.replace(day=1),
        "total": agregado["total"] or 0,
        "tokens_in": agregado["tokens_in"] or 0,
        "tokens_out": agregado["tokens_out"] or 0,
        "consultas": agregado["consultas"] or 0,
    }


def consultar(pregunta: str, fecha=None):
    """Pregunta al modelo con el contexto inyectado y guarda la sesión.

    Devuelve (sesion, error). Si algo falla, `sesion` es None y `error` es un
    texto para enseñar en pantalla: la app sigue funcionando igual.
    """
    import json

    from . import ai
    from .models import AdviceSession

    pregunta = (pregunta or "").strip()
    if not pregunta:
        return None, "Escribe una pregunta."

    prompt = ai.prompt_activo()
    if prompt is None:
        return None, "No hay ningún prompt de sistema activo. Créalo en el admin."

    contexto = ai.construir_contexto(fecha)
    mensaje = (
        "CONTEXTO DEL SISTEMA (solo lectura, generado automáticamente):\n"
        f"{json.dumps(contexto, ensure_ascii=False, indent=1)}\n\n"
        f"PREGUNTA:\n{pregunta}"
    )

    cliente = ai.ClienteIA()
    try:
        respuesta = cliente.preguntar(prompt.contenido, mensaje)
    except ai.IAError as exc:
        return None, str(exc)

    sesion = AdviceSession.objects.create(
        fecha=timezone.now(),
        pregunta=pregunta,
        contexto_json=contexto,
        respuesta=respuesta.texto,
        modelo=respuesta.modelo,
        tokens_in=respuesta.tokens_in,
        tokens_out=respuesta.tokens_out,
        coste_estimado=respuesta.coste,
        system_prompt=prompt,
    )
    return sesion, ""
