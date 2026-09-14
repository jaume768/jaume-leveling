"""Cliente de IA reutilizable: contexto compacto + prompt versionado + coste.

Este módulo es deliberadamente extraíble. Para llevarlo a otro proyecto basta
con cambiar `construir_contexto()`, que es la única función que conoce el
dominio; todo lo demás (cliente, resolución del prompt, cálculo de coste y
manejo de errores) es genérico.

REGLA ESTRICTA: la IA nunca escribe en la base de datos. No se le pasan
herramientas, no se le da acceso a los modelos y no se ejecuta nada de lo que
responde. Lee un contexto ya construido y devuelve texto. Quien escribe en la
base de datos es esta aplicación, nunca el modelo.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.utils import timezone

# --- Errores ----------------------------------------------------------------


class IAError(Exception):
    """Cualquier fallo al consultar al modelo. Nunca debe tumbar la app."""


class IANoConfigurada(IAError):
    """No hay ANTHROPIC_API_KEY, o falta el SDK."""


# --- Precios ----------------------------------------------------------------

# USD por millón de tokens (tarifas de la API de Anthropic).
PRECIOS_USD = {
    "claude-opus-5": (Decimal("5.00"), Decimal("25.00")),
    "claude-sonnet-5": (Decimal("2.00"), Decimal("10.00")),
    "claude-haiku-4-5": (Decimal("1.00"), Decimal("5.00")),
    "claude-fable-5-1": (Decimal("10.00"), Decimal("50.00")),
}
PRECIO_POR_DEFECTO = (Decimal("2.00"), Decimal("10.00"))

MILLON = Decimal("1000000")

# Cambio aproximado para guardar el coste en euros. Ajustable desde settings.
TIPO_CAMBIO_USD_EUR = Decimal(str(getattr(settings, "TIPO_CAMBIO_USD_EUR", "0.92")))


def coste_estimado(modelo: str, tokens_in: int, tokens_out: int) -> Decimal:
    """Coste aproximado en euros de una llamada."""
    precio_in, precio_out = PRECIOS_USD.get(modelo, PRECIO_POR_DEFECTO)
    usd = (Decimal(tokens_in) * precio_in + Decimal(tokens_out) * precio_out) / MILLON
    return (usd * TIPO_CAMBIO_USD_EUR).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


# --- Respuesta --------------------------------------------------------------


@dataclass
class RespuestaIA:
    texto: str
    modelo: str
    tokens_in: int = 0
    tokens_out: int = 0
    coste: Decimal = field(default_factory=lambda: Decimal("0"))


# --- Cliente ----------------------------------------------------------------


class ClienteIA:
    """Envoltorio fino sobre el SDK oficial de Anthropic.

    No guarda nada: devuelve la respuesta y deja que quien llama decida.
    """

    MAX_TOKENS = 4000

    def __init__(self, api_key: str | None = None, modelo: str | None = None):
        self.api_key = api_key if api_key is not None else getattr(settings, "ANTHROPIC_API_KEY", "")
        self.modelo = modelo or getattr(settings, "ANTHROPIC_MODEL", "") or "claude-sonnet-5"

    @property
    def configurado(self) -> bool:
        return bool(self.api_key)

    def _cliente(self):
        if not self.configurado:
            raise IANoConfigurada(
                "Falta ANTHROPIC_API_KEY. El consejo está apagado; el resto del sistema funciona igual."
            )
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - el SDK está en requirements
            raise IANoConfigurada("El SDK de anthropic no está instalado.") from exc
        return anthropic.Anthropic(api_key=self.api_key)

    def preguntar(self, system: str, mensaje: str) -> RespuestaIA:
        """Una pregunta, una respuesta. Sin herramientas: el modelo solo lee."""
        cliente = self._cliente()
        try:
            import anthropic

            respuesta = cliente.messages.create(
                model=self.modelo,
                max_tokens=self.MAX_TOKENS,
                system=system,
                messages=[{"role": "user", "content": mensaje}],
            )
        except Exception as exc:  # el SDK agrupa muchos errores distintos
            raise IAError(_mensaje_de_error(exc)) from exc

        texto = "\n".join(b.text for b in respuesta.content if b.type == "text").strip()
        tokens_in = respuesta.usage.input_tokens
        tokens_out = respuesta.usage.output_tokens
        return RespuestaIA(
            texto=texto or "El modelo no ha devuelto texto.",
            modelo=respuesta.model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            coste=coste_estimado(respuesta.model, tokens_in, tokens_out),
        )


def _mensaje_de_error(exc: Exception) -> str:
    """Traduce el error del SDK a algo que se pueda enseñar en pantalla."""
    try:
        import anthropic
    except ImportError:  # pragma: no cover
        return str(exc)

    if isinstance(exc, anthropic.AuthenticationError):
        return "La clave de la API no es válida."
    if isinstance(exc, anthropic.RateLimitError):
        return "Se ha alcanzado el límite de peticiones. Prueba en un minuto."
    if isinstance(exc, anthropic.APIConnectionError):
        return "No se ha podido conectar con la API."
    if isinstance(exc, anthropic.APIStatusError):
        return f"La API ha respondido con un error {exc.status_code}."
    return f"Fallo al consultar al modelo: {exc}"


# --- Prompt versionado ------------------------------------------------------

SLUG_PROMPT_CONSEJO = "consejo"


def prompt_activo(slug: str = SLUG_PROMPT_CONSEJO):
    """Última versión activa del prompt. Editable desde el admin, no desde el código."""
    from .models import SystemPrompt

    return SystemPrompt.objects.filter(slug=slug, activo=True).order_by("-version").first()


# --- Capa de dominio: lo único que hay que cambiar al reutilizar el módulo ---


def construir_contexto(fecha: dt.date | None = None) -> dict:
    """Retrato compacto del sistema, pensado para caber de sobra en 2.000 tokens.

    Solo lee. Devuelve tipos serializables para que se pueda guardar tal cual
    en AdviceSession.contexto_json.
    """
    from business import services as business
    from business.models import Deal, Invoice
    from missions import services as missions
    from progression import services as progression
    from review.models import WeeklyReview

    fecha = fecha or timezone.localdate()
    resumen = progression.resumen_progresion(fecha)
    perfil = resumen["perfil"]

    panel = missions.panel_de_misiones(fecha)
    pendientes = [
        f["mision"].titulo for f in panel["filas"] if not f["completada"]
    ][:8]

    pipeline = {}
    for valor, etiqueta in Deal.Estado.choices:
        pipeline[etiqueta] = Deal.objects.filter(estado=valor).count()

    vencidos = [
        {
            "negocio": d.negocio,
            "estado": d.get_estado_display(),
            "proximo_paso": d.proximo_paso or "sin definir",
            "dias_sin_toque": d.dias_sin_toque,
        }
        for d in Deal.objects.filter(estado__in=Deal.ESTADOS_ABIERTOS)
        if (d.dias_sin_toque or 0) > business.DIAS_SIN_SEGUIMIENTO
    ][:6]

    facturas = business.resumen_facturas(fecha)
    tarifa = business.tarifa_efectiva_mes(fecha)

    revisiones = [
        {
            "semana": f"{r.semana_iso}/{r.anio}",
            "cobrado": float(r.m1_eur_cobrados),
            "contactos": r.m4_contactos_nuevos,
            "tarifa_efectiva": float(r.m7_tarifa_efectiva),
            "decision": r.decision[:160],
        }
        for r in WeeklyReview.objects.order_by("-anio", "-semana_iso")[:3]
    ]

    return {
        "fecha": fecha.isoformat(),
        "dia_semana": fecha.strftime("%A"),
        "dia_protegido": progression.es_dia_protegido(fecha),
        "nivel": perfil.nivel,
        "rango": perfil.rango.nombre if perfil.rango else None,
        "jefe_activo": perfil.rango.jefe if perfil.rango else None,
        "xp_semana": resumen["xp_semana"],
        "objetivo_xp_semanal": resumen["objetivo_xp_semanal"],
        "racha_dias": resumen["racha"],
        "misiones_pendientes_hoy": pendientes,
        "pipeline_por_estado": pipeline,
        "deals_sin_seguimiento": vencidos,
        "facturas": {
            "pendiente_total": float(facturas["pendiente_total"]),
            "vencido": float(facturas["importe_vencido"]),
            "vencidas": [
                {
                    "cliente": f.client.nombre,
                    "importe": float(f.importe),
                    "dias_vencida": f.dias_vencida,
                }
                for f in facturas["vencidas"][:6]
            ],
            "cobrado_mes": float(facturas["cobrado_mes"]),
        },
        "recurrente": {
            "actual": float(business.recurrente_activo()),
            "objetivo": float(business.OBJETIVO_RECURRENTE),
        },
        "tarifa_efectiva_mes": float(tarifa) if tarifa is not None else None,
        "ultimas_revisiones": revisiones,
        "alertas": [a["titulo"] for a in business.alertas(fecha)],
        "penalizaciones_pendientes": [p.descripcion for p in resumen["penalizaciones"][:5]],
    }
