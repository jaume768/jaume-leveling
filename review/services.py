"""Lógica de negocio de la app review.

Calcula sola todo lo que el sistema puede saber y deja a mano solo lo que no.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from django.db import transaction
from django.db.models import Avg, Sum
from django.utils import timezone

from progression import services as progression

from .models import HealthLog, WeeklyReview

# Objetivos del panel semanal (docs/sistema-v2.md, §12).
OBJETIVOS = {
    "m1_eur_cobrados": Decimal("1200"),
    "m2_eur_recurrentes": Decimal("450"),
    "m3_eur_vencidos": Decimal("0"),
    "m4_contactos_nuevos": 6,
    "m5_conversaciones": 1,
    "m5_propuestas": 1,
    "m6_precio_medio": Decimal("350"),  # la oferta minima, sin IVA
    "m7_tarifa_efectiva": Decimal("40"),
    "m8_wip_abierto": 2,
    "m9_entrenos": 4,
}

XP_REVISION = 60

# La mision semanal que representa esta revision. Por slug, no por titulo.
SLUG_REVISION_SEMANAL = "revision-semanal"

# Umbral para el ámbar: a partir del 60% del objetivo, la métrica va encaminada.
UMBRAL_AMBAR = Decimal("0.6")


def semaforo(clave: str, valor) -> str:
    """verde | ambar | rojo, según el objetivo del documento."""
    if valor is None:
        return "gris"
    objetivo = OBJETIVOS.get(clave)
    if objetivo is None:
        return "gris"

    valor = Decimal(str(valor))
    objetivo = Decimal(str(objetivo))

    # Métricas donde menos es mejor.
    if clave in ("m3_eur_vencidos", "m8_wip_abierto"):
        if valor <= objetivo:
            return "verde"
        return "ambar" if valor <= objetivo + 1 else "rojo"

    if valor >= objetivo:
        return "verde"
    if objetivo and valor >= objetivo * UMBRAL_AMBAR:
        return "ambar"
    return "rojo"


def metricas_calculadas(fecha: dt.date | None = None) -> dict:
    """Las ocho métricas que el sistema sabe sacar solo."""
    from business import services as business
    from business.models import Deal, Project

    fecha = fecha or timezone.localdate()
    lunes, domingo = progression.rango_de_la_semana(fecha)

    facturas = business.resumen_facturas(fecha)
    vencidas = facturas["vencidas"]

    nuevos = Deal.objects.filter(fecha_primer_contacto__range=(lunes, domingo))
    tocados = Deal.objects.filter(ultimo_toque__range=(lunes, domingo))
    contactos = nuevos.union(tocados).count()

    propuestas = Deal.objects.filter(
        estado=Deal.Estado.PROPUESTA, ultimo_toque__range=(lunes, domingo)
    ).count()
    conversaciones = Deal.objects.filter(
        estado__in=(Deal.Estado.CONVERSANDO, Deal.Estado.PROPUESTA),
        ultimo_toque__range=(lunes, domingo),
    ).count()

    precio_medio = Deal.objects.filter(
        estado__in=(Deal.Estado.PROPUESTA, Deal.Estado.GANADO), valor_potencial__gt=0
    ).aggregate(media=Avg("valor_potencial"))["media"] or Decimal("0")

    wip = Project.objects.filter(estado=Project.Estado.ACTIVO).count()
    tarifa = business.tarifa_efectiva_mes(fecha)

    return {
        "m1_eur_cobrados": facturas["cobrado_mes"],
        "m2_eur_recurrentes": business.recurrente_activo(),
        "m3_eur_vencidos": facturas["importe_vencido"],
        "m4_contactos_nuevos": contactos,
        "m5_conversaciones": conversaciones,
        "m5_propuestas": propuestas,
        "m6_precio_medio": Decimal(precio_medio).quantize(Decimal("0.01")),
        "m7_tarifa_efectiva": tarifa if tarifa is not None else Decimal("0"),
        "m8_wip_abierto": wip,
        "xp_semana": progression.xp_de_la_semana(fecha),
    }


def sugerencias_manuales(fecha: dt.date | None = None) -> dict:
    """Lo que el sistema no puede saber, pero puede adelantar del registro de salud."""
    fecha = fecha or timezone.localdate()
    lunes, domingo = progression.rango_de_la_semana(fecha)
    registros = HealthLog.objects.filter(fecha__range=(lunes, domingo))
    peso = registros.exclude(peso=None).aggregate(media=Avg("peso"))["media"]
    return {
        "m9_entrenos": registros.filter(entreno=True).count(),
        "m9_peso_medio": Decimal(peso).quantize(Decimal("0.01")) if peso else None,
    }


def revision_de_la_semana(fecha: dt.date | None = None) -> WeeklyReview | None:
    fecha = fecha or timezone.localdate()
    anio, semana = progression.semana_iso(fecha)
    return WeeklyReview.objects.filter(anio=anio, semana_iso=semana).first()


def datos_iniciales(fecha: dt.date | None = None) -> dict:
    """Valores con los que llega pre-rellenado el formulario."""
    fecha = fecha or timezone.localdate()
    anio, semana = progression.semana_iso(fecha)
    iniciales = {"anio": anio, "semana_iso": semana, "fecha": fecha}
    iniciales.update(metricas_calculadas(fecha))
    iniciales.update(sugerencias_manuales(fecha))
    return iniciales


@transaction.atomic
def crear_borrador(fecha: dt.date | None = None) -> WeeklyReview:
    """Deja la revisión de la semana creada y pre-rellenada, sin marcar hecha."""
    fecha = fecha or timezone.localdate()
    existente = revision_de_la_semana(fecha)
    if existente is not None:
        return existente
    datos = datos_iniciales(fecha)
    datos["m8_revision_hecha"] = False
    return WeeklyReview.objects.create(**datos)


@transaction.atomic
def guardar_revision(form) -> WeeklyReview:
    """Guarda la revisión y, si queda marcada como hecha, concede sus 60 XP.

    La XP se concede a través de la misión semanal S4 cuando existe, para que
    el panel y la revisión no se contradigan y no se pueda puntuar dos veces.
    """
    ya_estaba_hecha = bool(form.instance.pk) and WeeklyReview.objects.filter(
        pk=form.instance.pk, m8_revision_hecha=True
    ).exists()

    revision = form.save()
    if revision.m8_revision_hecha and not ya_estaba_hecha:
        _puntuar_revision(revision)
        _penalizar_bloques_cancelados(revision)
    return revision


def _penalizar_bloques_cancelados(revision: WeeklyReview) -> None:
    """-150 XP si la semana se cerro con un bloque con Alexandra cancelado.

    La correccion exigida es recuperarlo esa misma semana. Se aplica una sola
    vez por semana: la clave lleva el ano y la semana ISO.
    """
    if revision.m10_bloques_intactos:
        return
    progression.aplicar_penalizacion(
        progression.clave_penalizacion(
            "bloque-alexandra-cancelado",
            f"{revision.anio}w{revision.semana_iso:02d}",
        ),
        descripcion=(
            f"Semana {revision.semana_iso}/{revision.anio}: "
            "un bloque con Alexandra cancelado por trabajo"
        ),
        correccion="Recuperarlo esta misma semana. No la que viene.",
        fecha=revision.fecha,
    )


def _puntuar_revision(revision: WeeklyReview) -> None:
    from missions.models import Mission
    from missions import services as missions_services

    s4 = Mission.objects.filter(slug=SLUG_REVISION_SEMANAL, activa=True).first()
    if s4 is not None:
        missions_services.completar_mision(s4, evidencia="Revisión semanal cerrada", fecha=revision.fecha)
    else:
        progression.registrar_xp(
            "revision-semanal",
            descripcion=f"Revisión de la semana {revision.semana_iso}/{revision.anio}",
            fecha=revision.fecha,
            fuente="AUTO",
            objeto_relacionado=f"weeklyreview:{revision.pk}",
        )


# --- Histórico ---------------------------------------------------------------

# Métricas que se muestran en el histórico, con su etiqueta corta.
COLUMNAS = [
    ("m1_eur_cobrados", "€ cobrados", "mas_es_mejor"),
    ("m2_eur_recurrentes", "€ recurrentes", "mas_es_mejor"),
    ("m3_eur_vencidos", "€ vencidos", "menos_es_mejor"),
    ("m4_contactos_nuevos", "Contactos", "mas_es_mejor"),
    ("m6_precio_medio", "Precio medio", "mas_es_mejor"),
    ("m7_tarifa_efectiva", "Tarifa €/h", "mas_es_mejor"),
    ("m8_wip_abierto", "WIP", "menos_es_mejor"),
    ("m9_entrenos", "Entrenos", "mas_es_mejor"),
    ("xp_semana", "XP", "mas_es_mejor"),
]


def _tendencia(actual, anterior, sentido: str) -> str:
    """↑ mejor · ↓ peor · → igual. Vacío si no hay con qué comparar."""
    if anterior is None or actual is None:
        return ""
    if actual == anterior:
        return "igual"
    sube = actual > anterior
    mejora = sube if sentido == "mas_es_mejor" else not sube
    return "mejor" if mejora else "peor"


def historico(limite: int = 12) -> dict:
    """Revisiones recientes con la tendencia de cada métrica."""
    revisiones = list(WeeklyReview.objects.order_by("-anio", "-semana_iso")[:limite])
    filas = []
    for indice, revision in enumerate(revisiones):
        anterior = revisiones[indice + 1] if indice + 1 < len(revisiones) else None
        celdas = []
        for clave, _etiqueta, sentido in COLUMNAS:
            valor = getattr(revision, clave)
            previo = getattr(anterior, clave) if anterior else None
            celdas.append(
                {
                    "valor": valor,
                    "tendencia": _tendencia(valor, previo, sentido),
                    "semaforo": semaforo(clave, valor),
                }
            )
        filas.append({"revision": revision, "celdas": celdas})
    return {"columnas": COLUMNAS, "filas": filas}


# --- Recordatorio ------------------------------------------------------------


def aviso_revision_pendiente(fecha: dt.date | None = None) -> dict | None:
    """Aviso del panel: es domingo y la revisión de la semana sigue sin cerrar.

    El domingo no penaliza —está fuera del sistema—, así que esto es un
    recordatorio, no una falta.
    """
    fecha = fecha or timezone.localdate()
    if fecha.weekday() != progression.DOMINGO:
        return None

    revision = revision_de_la_semana(fecha)
    if revision is not None and revision.m8_revision_hecha:
        return None

    anio, semana = progression.semana_iso(fecha)
    return {
        "semana": semana,
        "anio": anio,
        "borrador": revision is not None,
        "texto": (
            f"Revisión de la semana {semana} pendiente. 40 minutos, 20:15. "
            "Ocho revisiones seguidas es lo que mueve organización."
        ),
    }


# --- Revision asistida por IA -------------------------------------------------

PROMPT_REVISION = """Eres el Sistema de Jaume, un desarrollador freelance en Mallorca que vende webs
(oferta minima: 350 EUR sin IVA por web estatica y 35 EUR/mes de mantenimiento basico).
Preparas su revision semanal del domingo para que la cierre en 10 minutos.

Reglas:
- Usa SOLO los datos del contexto. No inventes cifras, clientes ni hechos.
- Tono directo, en segunda persona, sin moralina ni frases motivacionales.
- La metrica que manda es el dinero: cobrado, recurrente, propuestas y su seguimiento.
- Una sola decision, concreta y comprobable el domingo siguiente.
- Tres objetivos para la semana que viene, cada uno con un numero o un nombre propio.

Responde UNICAMENTE con un objeto JSON valido, sin texto antes ni despues, con estas claves:
{"resumen": "2-3 frases sobre la semana",
 "funciono": "1-2 frases",
 "no_funciono": "1-2 frases",
 "decision": "una frase",
 "objetivos": ["...", "...", "..."]}"""


def _a_json(valor):
    """Decimal y fechas a tipos que entiende json."""
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, (dt.date, dt.datetime)):
        return valor.isoformat()
    return valor


def contexto_revision(fecha: dt.date | None = None) -> dict:
    """Todo lo que la IA necesita para preparar la revision. Solo lectura."""
    from business import services as business
    from business.models import Deal
    from progression.models import XPEvent

    fecha = fecha or timezone.localdate()
    lunes, domingo = progression.rango_de_la_semana(fecha)
    anio, semana = progression.semana_iso(fecha)

    metricas = {k: _a_json(v) for k, v in metricas_calculadas(fecha).items()}
    eventos = [
        {"fecha": e.fecha.isoformat(), "accion": e.descripcion or e.accion_slug, "xp": e.xp_neto}
        for e in XPEvent.objects.filter(fecha__range=(lunes, domingo)).order_by("fecha", "id")
    ]
    movidas = [
        {
            "negocio": d.negocio,
            "estado": d.get_estado_display(),
            "valor": _a_json(d.valor_potencial),
            "proximo_paso": d.proximo_paso,
        }
        for d in Deal.objects.filter(ultimo_toque__range=(lunes, domingo)).order_by("estado")
    ]
    abiertas = Deal.objects.filter(estado__in=Deal.ESTADOS_ABIERTOS)
    anterior = (
        WeeklyReview.objects.filter(m8_revision_hecha=True)
        .exclude(anio=anio, semana_iso=semana)
        .order_by("-anio", "-semana_iso")
        .first()
    )
    return {
        "semana": f"{semana}/{anio}",
        "metricas": metricas,
        "objetivos_del_panel": {k: _a_json(v) for k, v in OBJETIVOS.items()},
        "xp_de_la_semana": eventos,
        "oportunidades_movidas": movidas,
        "pipeline_abierto": {
            "total": abiertas.count(),
            "por_estado": {
                etiqueta: abiertas.filter(estado=valor).count()
                for valor, etiqueta in Deal.Estado.choices
                if valor in Deal.ESTADOS_ABIERTOS
            },
        },
        "seguimientos_pendientes": [
            {"negocio": p["deal"].negocio, "motivo": p["motivo"]}
            for p in business.seguimientos_pendientes(fecha)
        ],
        "revision_anterior": (
            {
                "decision": anterior.decision,
                "objetivos": [anterior.objetivo_1, anterior.objetivo_2, anterior.objetivo_3],
            }
            if anterior
            else None
        ),
    }


def _extraer_json(texto: str) -> dict:
    import json

    inicio, fin = texto.find("{"), texto.rfind("}")
    if inicio == -1 or fin <= inicio:
        raise ValueError("La respuesta no trae JSON.")
    datos = json.loads(texto[inicio : fin + 1])
    objetivos = [str(o).strip() for o in (datos.get("objetivos") or []) if str(o).strip()][:3]
    return {
        "resumen": str(datos.get("resumen", "")).strip(),
        "funciono": str(datos.get("funciono", "")).strip(),
        "no_funciono": str(datos.get("no_funciono", "")).strip(),
        "decision": str(datos.get("decision", "")).strip(),
        "objetivos": objetivos + [""] * (3 - len(objetivos)),
    }


def preparar_con_ia(fecha: dt.date | None = None) -> tuple[dict | None, str]:
    """Borrador de la revision escrito por la IA. Devuelve (propuesta, error).

    La IA no guarda nada: devuelve texto y tu decides que se queda. La consulta
    se anota en el historial de consejos para que su coste cuente en el gasto.
    """
    import json

    from wisdom import ai
    from wisdom.models import AdviceSession

    fecha = fecha or timezone.localdate()
    contexto = contexto_revision(fecha)
    mensaje = (
        "CONTEXTO DE LA SEMANA (solo lectura, generado automaticamente):\n"
        f"{json.dumps(contexto, ensure_ascii=False, indent=1)}"
    )
    try:
        respuesta = ai.ClienteIA().preguntar(PROMPT_REVISION, mensaje)
    except ai.IAError as exc:
        return None, str(exc)
    try:
        propuesta = _extraer_json(respuesta.texto)
    except ValueError:
        return None, "La IA no ha devuelto un borrador legible. Vuelve a probar."

    AdviceSession.objects.create(
        fecha=timezone.now(),
        pregunta=f"Revisión semanal {contexto['semana']}: preparación automática",
        contexto_json=contexto,
        respuesta=respuesta.texto,
        modelo=respuesta.modelo,
        tokens_in=respuesta.tokens_in,
        tokens_out=respuesta.tokens_out,
        coste_estimado=respuesta.coste,
    )
    return propuesta, ""
