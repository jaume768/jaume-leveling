"""Escalera de hitos de los atributos: el "+10" que se reclama.

Cada atributo tiene una escalera de hitos. El primero es el "Siguiente +10"
que ya tenia; al reclamarlo, el atributo sube 10 (por Ajustes del Sistema, con
su registro historico) y aparece el siguiente escalon.

Hay dos clases de hito:
- medible: el Sistema lo comprueba con tus datos y avisa cuando esta listo;
  reclamarlo es un clic.
- con evidencia: no hay dato que lo pruebe, asi que se reclama escribiendo la
  prueba. Igual que la calibracion de siempre, pero desde Estado.
"""
from __future__ import annotations

from django.apps import apps
from django.db import transaction

from .models import Aviso, HitoAtributo

PUNTOS_POR_HITO = 10


# --- Medidas ----------------------------------------------------------------------


def _misiones(*slugs: str) -> int:
    MissionLog = apps.get_model("missions", "MissionLog")
    return MissionLog.objects.filter(completada=True, mission__slug__in=slugs).count()


def _revisiones_seguidas() -> int:
    """Semanas ISO consecutivas, hacia atras, con la revision semanal hecha."""
    MissionLog = apps.get_model("missions", "MissionLog")
    semanas = {
        f.isocalendar()[:2]
        for f in MissionLog.objects.filter(
            completada=True, mission__slug="revision-semanal"
        ).values_list("fecha", flat=True)
    }
    if not semanas:
        return 0
    import datetime as dt

    actual = max(semanas)
    lunes = dt.date.fromisocalendar(actual[0], actual[1], 1)
    seguidas = 0
    while lunes.isocalendar()[:2] in semanas:
        seguidas += 1
        lunes -= dt.timedelta(weeks=1)
    return seguidas


def _entregados():
    Project = apps.get_model("business", "Project")
    return list(
        Project.objects.filter(
            estado=Project.Estado.ENTREGADO, horas_estimadas__gt=0, horas_reales__gt=0
        ).order_by("-fecha_entrega", "-pk")
    )


def _entregas_en_alcance() -> int:
    """Entregas seguidas (las ultimas) sin pasarse de las horas estimadas."""
    seguidas = 0
    for proyecto in _entregados():
        if proyecto.horas_reales > proyecto.horas_estimadas:
            break
        seguidas += 1
    return seguidas


def _estimaciones_buenas() -> int:
    """Proyectos entregados con un error de estimacion menor del 25 %."""
    return sum(
        1 for p in _entregados()
        if abs(p.horas_reales - p.horas_estimadas) / p.horas_estimadas < 0.25
    )


def _deals(canal: str = "", ganados: bool = False) -> int:
    Deal = apps.get_model("business", "Deal")
    consulta = Deal.objects.all()
    if canal:
        consulta = consulta.filter(canal__icontains=canal)
    if ganados:
        consulta = consulta.filter(estado=Deal.Estado.GANADO)
    return consulta.count()


def _ganados_sobre_suelo() -> int:
    from business import services as business

    Deal = apps.get_model("business", "Deal")
    return Deal.objects.filter(
        estado=Deal.Estado.GANADO, valor_potencial__gte=business.suelo_precio()
    ).count()


def _rechazos_por_precio() -> int:
    Deal = apps.get_model("business", "Deal")
    return Deal.objects.filter(rechazado_por_precio=True).count()


def _sombras() -> int:
    Client = apps.get_model("business", "Client")
    return Client.objects.filter(estado=Client.Estado.ACTIVO, mrr__gt=0).count()


def _casos() -> int:
    from core import services as core

    return core.casos_publicados()


def _semanas_pipeline() -> int:
    from core import services as core

    return core.semanas_seguidas_con_pipeline()


def _mejor_racha() -> int:
    from . import services

    return services.mejor_racha()


def _referidos() -> int:
    return _misiones("secundaria-referido", "peticion-de-referido")


# --- Escaleras ----------------------------------------------------------------------
#
# (texto, medida o None, objetivo). Sin medida = se reclama con evidencia.
# El primer escalon de cada una es el "Siguiente +10" que ya tenia el atributo.

ESCALERAS = {
    "finanzas": [
        ("Saber tu margen por proyecto y apartar el 35%", lambda: _misiones("m13"), 1),
        ("Apartar el 35% tres meses", lambda: _misiones("m13"), 3),
        ("Colchón de 20.000 €", None, None),
        ("Seis meses de gastos cubiertos solo con el freelance", None, None),
    ],
    "gestion-proyectos": [
        ("3 entregas seguidas sin horas fuera de alcance", _entregas_en_alcance, 3),
        ("Plantilla de entrega actualizada dos veces", lambda: _misiones("m8"), 2),
        ("5 entregas seguidas dentro de alcance", _entregas_en_alcance, 5),
        ("Un proyecto entregado sin escribir tú el código principal", lambda: _misiones("el-primer-contrato-sin-ti"), 1),
    ],
    "ventas": [
        ("Pipeline sostenido 8 semanas mientras entregas", _semanas_pipeline, 8),
        ("2 proyectos ganados por encima del suelo", _ganados_sobre_suelo, 2),
        ("5 proyectos ganados por encima del suelo", _ganados_sobre_suelo, 5),
        ("Pipeline sostenido 16 semanas", _semanas_pipeline, 16),
    ],
    "marca-portfolio": [
        ("Web propia con 3 casos y resultados", _casos, 3),
        ("1 testimonio conseguido", lambda: _misiones("m9"), 1),
        ("3 testimonios conseguidos", lambda: _misiones("m9"), 3),
        ("5 casos publicados con número", _casos, 5),
    ],
    "marketing": [
        ("3 casos publicados + 1 lead entrante", lambda: min(_casos() >= 3, _deals("entrante") >= 1), 1),
        ("8 semanas con 2 publicaciones", lambda: _misiones("publicaciones-semana"), 8),
        ("3 leads entrantes", lambda: _deals("entrante"), 3),
        ("Un cliente ganado que llegó solo", lambda: _deals("entrante", ganados=True), 1),
    ],
    "red-profesional": [
        ("15 dueños de negocio a los que puedas escribir sin presentarte", None, None),
        ("3 referidos pedidos", _referidos, 3),
        ("1 oportunidad ganada por referido", lambda: _deals("referido", ganados=True), 1),
        ("10 referidos pedidos", _referidos, 10),
    ],
    "producto": [
        ("Vender dos veces el mismo paquete sin tocar el alcance", None, None),
        ("Mantenimiento vendido a 3 clientes", _sombras, 3),
        ("Problema productizable identificado", lambda: _misiones("m14"), 1),
        ("6 clientes con el mismo paquete", _sombras, 6),
    ],
    "relaciones": [
        ("Mantenerlos 12 semanas con carga alta de trabajo", lambda: _misiones("bloques-alexandra"), 12),
        ("24 semanas sin cancelar un bloque", lambda: _misiones("bloques-alexandra"), 24),
    ],
    "disciplina": [
        ("Cumplir el bloque comercial sin estructura externa", _mejor_racha, 15),
        ("Racha de 30 días", _mejor_racha, 30),
        ("Racha de 60 días", _mejor_racha, 60),
        ("Racha de 100 días", _mejor_racha, 100),
    ],
    "comunicacion": [
        ("Decir un precio y callarse", None, None),
        ("Rechazar un proyecto por precio sin justificarte", _rechazos_por_precio, 1),
        ("Propuesta con 3 opciones enviada", lambda: _misiones("m6"), 1),
        ("Subir el precio a un cliente actual", None, None),
    ],
    "organizacion": [
        ("8 revisiones semanales seguidas", _revisiones_seguidas, 8),
        ("16 revisiones semanales seguidas", _revisiones_seguidas, 16),
        ("26 revisiones semanales seguidas", _revisiones_seguidas, 26),
        ("Un año de revisiones", _revisiones_seguidas, 52),
    ],
    "salud-fisica": [
        ("78,5 kg manteniendo marcas de fuerza", None, None),
        ("12 semanas con tus 4 entrenos", lambda: _misiones("entrenos-semana"), 12),
        ("Cintura −3 cm y marcas de fuerza mantenidas", None, None),
    ],
    "energia-descanso": [
        ("Sueño medio de 7 h o más con energía 4/5 cinco días de siete", None, None),
        ("Un mes entero con 7 h de sueño de media", None, None),
        ("Tres meses sin semana de agotamiento", None, None),
    ],
    "tecnica": [
        ("Estimar 3 proyectos con error menor del 25%", _estimaciones_buenas, 3),
        ("6 proyectos estimados con error menor del 25%", _estimaciones_buenas, 6),
        ("Una plantilla técnica reutilizada en 3 proyectos", None, None),
    ],
    "ia-automatizacion": [
        ("1 automatización cobrada con ahorro medido", lambda: _misiones("m7"), 1),
        ("3 automatizaciones internas medidas", lambda: _misiones("m11"), 3),
        ("3 automatizaciones vendidas", lambda: _misiones("m7"), 3),
    ],
}


def _reclamados(slug: str) -> int:
    return HitoAtributo.objects.filter(slug=slug).count()


def estado_de_hito(atributo) -> dict:
    """El escalon en el que esta el atributo y si se puede reclamar ya."""
    escalera = ESCALERAS.get(atributo.slug, [])
    indice = _reclamados(atributo.slug)
    if indice >= len(escalera) or atributo.valor >= 100:
        return {"completo": True, "indice": indice, "total": len(escalera)}
    texto, medida, objetivo = escalera[indice]
    medible = medida is not None
    actual = int(medida()) if medible else None
    return {
        "completo": False,
        "indice": indice,
        "total": len(escalera),
        "texto": texto,
        "medible": medible,
        "actual": actual,
        "objetivo": objetivo,
        "listo": medible and actual >= objetivo,
        "puntos": min(PUNTOS_POR_HITO, 100 - atributo.valor),
    }


@transaction.atomic
def reclamar_hito(slug: str, evidencia: str = "") -> HitoAtributo:
    """Sube el atributo +10 por el hito actual y deja el siguiente a la vista."""
    from core import services as core
    from core.models import Attribute

    from . import services

    atributo = Attribute.objects.select_for_update().get(slug=slug)
    estado = estado_de_hito(atributo)
    if estado["completo"]:
        raise ValueError("Este atributo ya no tiene hitos pendientes.")
    evidencia = (evidencia or "").strip()
    if estado["medible"]:
        if not estado["listo"]:
            raise ValueError("El Sistema todavía no ve cumplido este hito.")
        nota = f"Hito cumplido (detectado por el Sistema): {estado['texto']}"
    else:
        if len(evidencia) < 10:
            raise ValueError("Escribe la prueba del hito: sin evidencia no se sube.")
        nota = f"Hito cumplido: {estado['texto']}. Evidencia: {evidencia}"

    nuevo = min(100, atributo.valor + PUNTOS_POR_HITO)
    core.ajustar_atributo(slug, nuevo, nota)
    hito = HitoAtributo.objects.create(
        slug=slug, indice=estado["indice"], texto=estado["texto"],
        evidencia=evidencia, automatico=estado["medible"],
    )
    # El "Siguiente +10" pasa al escalon siguiente.
    escalera = ESCALERAS.get(slug, [])
    siguiente = escalera[estado["indice"] + 1][0] if estado["indice"] + 1 < len(escalera) else (
        "Escalera completa. Nuevos hitos en la próxima calibración."
    )
    Attribute.objects.filter(slug=slug).update(siguiente_hito=siguiente)
    services.avisar(
        Aviso.Tipo.HABILIDAD, f"{atributo.nombre} +{nuevo - atributo.valor}",
        f"{atributo.nombre} sube a {nuevo}", clave=f"hito-reclamado:{slug}:{estado['indice']}",
    )
    return hito


def revisar_hitos() -> list[str]:
    """Avisa (una vez) de cada hito medible que ya se puede reclamar."""
    from core.models import Attribute

    from . import services

    listos = []
    for atributo in Attribute.objects.all():
        estado = estado_de_hito(atributo)
        if not estado["completo"] and estado.get("listo"):
            aviso = services.avisar(
                Aviso.Tipo.SISTEMA, f"{atributo.nombre}: +10 disponible",
                f"Hito cumplido: {estado['texto']}. Reclámalo en Estado.",
                clave=f"hito-listo:{atributo.slug}:{estado['indice']}",
            )
            if aviso:
                listos.append(atributo.nombre)
    return listos


def hitos_listos() -> int:
    from core.models import Attribute

    return sum(1 for a in Attribute.objects.all() if estado_de_hito(a).get("listo"))
