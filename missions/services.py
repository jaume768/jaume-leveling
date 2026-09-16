"""Logica de negocio de la app missions.

Que misiones tocan hoy, como se dan por hechas y cual es el dia minimo.
"""
from __future__ import annotations

import datetime as dt

from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from progression import services as progression
from progression.models import Categoria, XPEvent

from .guides import GUIAS
from .models import Mission, MissionLog


class EvidenciaRequerida(Exception):
    """La mision exige evidencia y no se ha aportado."""


class EleccionYaHecha(Exception):
    """Ya elegiste la secundaria de hoy. Una por dia: elegir es descartar."""


class VarianteYaCompletada(Exception):
    """Otra variante del mismo grupo ya se completo hoy.

    La version normal y la minima son la misma mision contada de dos maneras.
    Completar las dos el mismo dia daria XP dos veces por un solo hecho.
    """


def eleccion_del_dia(grupo: str, fecha: dt.date):
    """La mision de ese grupo de eleccion ya cerrada ese dia, si la hay."""
    if not grupo:
        return None
    return (
        MissionLog.objects.filter(
            mission__eleccion=grupo, fecha=fecha, completada=True
        )
        .select_related("mission")
        .first()
    )


def hermana_completada_hoy(mission: Mission, fecha: dt.date):
    """Otra variante del grupo ya cerrada ese dia, si la hay."""
    return (
        MissionLog.objects.filter(
            mission__grupo=mission.grupo,
            fecha=fecha,
            completada=True,
        )
        .exclude(mission_id=mission.pk)
        .select_related("mission")
        .first()
        if mission.grupo
        else None
    )


def slug_de_mision(mission: Mission) -> str:
    """Slug estable con el que la mision aparece en el registro de XP."""
    return f"mision-{mission.pk}"


# Tipos que forman el ritmo del dia: son los que cuentan en el marcador del
# panel. Mensuales y principales se pintan aparte, con su propio recuento.
TIPOS_DEL_DIA = (Mission.Tipo.DIARIA, Mission.Tipo.SEMANAL)

# Lo unico que se pide en una Semana de Reinicio (docs/sistema-v2.md, SS6):
# la accion comercial diaria, un entregable pequeno y la revision. Se
# identifican por slug: ni el titulo ni el orden son identidad.
MISIONES_DE_REINICIO = (
    "accion-comercial",
    "entregable-visible",
    "revision-semanal",
)


def disponibles_para_rango(queryset, rango):
    """Recorta un queryset de misiones a las que el rango actual permite ver.

    Una mision sin `rango_min` ni `rango_max` esta siempre disponible. Las que
    llevan rango aparecen al alcanzarlo y se retiran al superarlo, para que el
    panel no arrastre objetivos de un rango que ya cerraste.
    """
    if rango is None:
        return queryset.filter(rango_min__isnull=True, rango_max__isnull=True)
    return queryset.filter(
        Q(rango_min__isnull=True) | Q(rango_min__orden__lte=rango.orden),
        Q(rango_max__isnull=True) | Q(rango_max__orden__gte=rango.orden),
    )


def _rango_actual():
    """Rango del perfil, deducido del nivel si no esta asignado a mano."""
    from core import services as core_services
    from core.models import Profile

    perfil = Profile.get()
    return perfil.rango or core_services.rango_para_nivel(perfil.nivel)


def _semanales_pendientes(fecha: dt.date):
    lunes, domingo = progression.rango_de_la_semana(fecha)
    hechas = MissionLog.objects.filter(
        fecha__range=(lunes, domingo), completada=True
    ).values_list("mission_id", flat=True)
    return Mission.objects.filter(
        tipo=Mission.Tipo.SEMANAL, activa=True
    ).exclude(pk__in=hechas)


def _mensuales_pendientes(fecha: dt.date):
    """Mensuales que siguen sin cerrarse dentro del mes de la fecha."""
    primero = fecha.replace(day=1)
    if primero.month == 12:
        siguiente = primero.replace(year=primero.year + 1, month=1)
    else:
        siguiente = primero.replace(month=primero.month + 1)
    ultimo = siguiente - dt.timedelta(days=1)

    hechas = MissionLog.objects.filter(
        fecha__range=(primero, ultimo), completada=True
    ).values_list("mission_id", flat=True)
    return Mission.objects.filter(
        tipo=Mission.Tipo.MENSUAL, activa=True
    ).exclude(pk__in=hechas)


def _principales_pendientes(rango):
    """Principales del rango actual que no se han cerrado nunca.

    No son periodicas: cada una se completa una vez en la vida del sistema.
    """
    hechas = MissionLog.objects.filter(completada=True).values_list(
        "mission_id", flat=True
    )
    pendientes = Mission.objects.filter(
        tipo=Mission.Tipo.PRINCIPAL, activa=True
    ).exclude(pk__in=hechas)
    return disponibles_para_rango(pendientes, rango)


def misiones_de_hoy(fecha: dt.date | None = None):
    """Misiones que tocan hoy, escaladas al rango actual.

    - Miercoles: ninguna. El dia esta protegido y no genera ni XP ni penalizacion.
    - Domingo: solo las semanales pendientes (la revision de las 20:15 entre ellas);
      las diarias no se piden porque el domingo esta fuera del sistema.
    - Resto de dias: diarias, semanales sin cerrar esta semana, mensuales sin
      cerrar este mes y las principales del rango que sigan abiertas.
    """
    fecha = fecha or timezone.localdate()

    if fecha.weekday() == progression.MIERCOLES:
        return Mission.objects.none()

    rango = _rango_actual()

    # Semana de Reinicio: solo lo imprescindible, nada mas.
    if progression.semana_de_reinicio(fecha) is not None:
        return Mission.objects.filter(
            slug__in=MISIONES_DE_REINICIO, activa=True
        ).order_by("tipo", "orden")

    semanales = _semanales_pendientes(fecha)
    if fecha.weekday() == progression.DOMINGO:
        return disponibles_para_rango(semanales, rango).order_by("orden", "titulo")

    diarias = Mission.objects.filter(
        tipo=Mission.Tipo.DIARIA, activa=True, es_minima=False
    )
    del_ritmo = disponibles_para_rango(diarias | semanales, rango)
    mensuales = disponibles_para_rango(_mensuales_pendientes(fecha), rango)
    principales = _principales_pendientes(rango)

    pks = list(del_ritmo.values_list("pk", flat=True))
    pks += list(mensuales.values_list("pk", flat=True))
    pks += list(principales.values_list("pk", flat=True))
    return Mission.objects.filter(pk__in=pks).order_by("tipo", "orden", "titulo")


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
    mission: Mission,
    evidencia: str = "",
    fecha: dt.date | None = None,
    notas: str = "",
) -> MissionLog:
    """Da una mision por hecha y concede su XP. Idempotente dentro del mismo dia.

    Si la mision ya estaba completada hoy, devuelve el registro existente sin
    volver a puntuar, pero las notas si se actualizan: el cuaderno se puede
    seguir escribiendo despues de haber marcado la mision.
    """
    fecha = fecha or timezone.localdate()

    registro, _ = MissionLog.objects.select_for_update().get_or_create(
        mission=mission, fecha=fecha
    )
    notas = (notas or "").strip()
    if registro.completada:
        if notas and notas != registro.notas:
            registro.notas = notas
            registro.save(update_fields=["notas"])
        return registro

    # Una sola variante del grupo puede puntuar cada dia. La comprobacion va
    # dentro de la transaccion, despues del select_for_update de arriba.
    hermana = hermana_completada_hoy(mission, fecha)
    if hermana is not None:
        raise VarianteYaCompletada(hermana.mission.titulo)

    # Eleccion controlada: una secundaria al dia. Elegir implica renunciar.
    elegida = eleccion_del_dia(mission.eleccion, fecha)
    if elegida is not None and elegida.mission_id != mission.pk:
        raise EleccionYaHecha(elegida.mission.titulo)

    evidencia = (evidencia or "").strip()
    if mission.evidencia_requerida and not evidencia:
        raise EvidenciaRequerida(mission.definicion_terminada)

    # Con `regla_xp` la XP entra por la tabla y hereda su tope semanal; sin
    # ella, la mision puntua por su cuenta. Las secundarias usan lo primero
    # para que elegir la misma ruta cinco dias no sea una mina de XP.
    evento = progression.registrar_xp(
        mission.regla_xp or slug_de_mision(mission),
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
    if notas:
        registro.notas = notas
    registro.save(update_fields=["completada", "evidencia_texto", "xp_otorgado", "notas"])
    return registro


# --- Cuaderno ----------------------------------------------------------------
#
# Algunas misiones no se prueban con evidencia: se hacen escribiendo. El cierre
# del dia es la principal —"2 tareas para manana", terminada cuando estan
# "Anotadas"—, asi que lo apuntado se guarda en MissionLog.notas y se puede
# releer al dia siguiente, que es para lo que sirve.


@transaction.atomic
def guardar_notas(
    mission: Mission, notas: str, fecha: dt.date | None = None
) -> MissionLog:
    """Escribe en el cuaderno del dia sin completar la mision ni dar XP.

    Sirve para apuntar a media tarde y cerrar la mision mas tarde, y para
    corregir lo anotado despues de haberla dado por hecha.
    """
    fecha = fecha or timezone.localdate()
    registro, _ = MissionLog.objects.select_for_update().get_or_create(
        mission=mission, fecha=fecha
    )
    registro.notas = (notas or "").strip()
    registro.save(update_fields=["notas"])
    return registro


def notas_de(mission: Mission, fecha: dt.date | None = None) -> str:
    """Lo apuntado hoy en esa mision."""
    fecha = fecha or timezone.localdate()
    registro = MissionLog.objects.filter(mission=mission, fecha=fecha).first()
    return registro.notas if registro else ""


def ultimas_notas(mission: Mission, fecha: dt.date | None = None) -> MissionLog | None:
    """El ultimo dia anterior con algo escrito. Lo de ayer, normalmente.

    Es el motivo de que el cuaderno exista: por la manana quieres leer las dos
    tareas que dejaste apuntadas anoche.
    """
    fecha = fecha or timezone.localdate()
    return (
        MissionLog.objects.filter(mission=mission, fecha__lt=fecha)
        .exclude(notas="")
        .order_by("-fecha")
        .first()
    )


def cuaderno_de(mission: Mission, fecha: dt.date | None = None) -> dict:
    """Contexto del cuaderno de una mision."""
    fecha = fecha or timezone.localdate()
    codigo, titulo = partir_titulo(mission.titulo)
    return {
        "mision": mission,
        "codigo": codigo,
        "titulo": titulo,
        "fecha": fecha,
        "notas": notas_de(mission, fecha),
        "anteriores": ultimas_notas(mission, fecha),
        "completada": esta_completada(mission, fecha),
        "etiqueta": mission.etiqueta_notas or "Notas",
    }


# --- Presentacion del panel de misiones --------------------------------------
#
# El titulo de cada mision viene sembrado como "D1 - Accion comercial": el
# codigo va delante, separado por el punto medio. El panel los pinta separados,
# asi que aqui se parten una sola vez y de forma pura.

SEPARADOR_CODIGO = "·"

# Cada grupo del panel: el orden en que se pintan, su subtitulo y el color del
# filo lateral. Los tokens (warn/ok/xp) son los del sistema de diseno.
GRUPOS = (
    (Mission.Tipo.DIARIA, "Diarias", "Haz lo esencial. Avanza cada dia.", "warn"),
    (Mission.Tipo.SEMANAL, "Semanales", "Construye resultados a medio plazo.", "ok"),
    (Mission.Tipo.MENSUAL, "Mensuales", "El mes se gana con cifras, no con horas.", "xp"),
    (Mission.Tipo.PRINCIPAL, "Principales", "Cierran tu rango. Se completan una vez.", "ink"),
    (Mission.Tipo.ANUAL, "Anuales", "La direccion, no la semana.", "xp"),
)


def partir_titulo(titulo: str) -> tuple[str, str]:
    """Separa el codigo del titulo: "D1 - Accion comercial" -> ("D1", "...").

    Si la mision no lleva codigo, devuelve ("", titulo).
    """
    codigo, separador, resto = titulo.partition(SEPARADOR_CODIGO)
    if not separador or not resto.strip():
        return "", titulo.strip()
    return codigo.strip(), resto.strip()


def agrupar_filas(filas: list[dict]) -> list[dict]:
    """Agrupa las filas del panel por tipo de mision, en el orden de GRUPOS.

    Cada grupo lleva su recuento hecho/total para poder pintar "(0/2)" sin
    recalcular nada en la plantilla. Los grupos vacios no se devuelven.
    """
    grupos = []
    for tipo, titulo, subtitulo, acento in GRUPOS:
        del_tipo = [fila for fila in filas if fila["mision"].tipo == tipo]
        if not del_tipo:
            continue
        grupos.append(
            {
                "tipo": tipo,
                "titulo": titulo,
                "subtitulo": subtitulo,
                "acento": acento,
                "filas": del_tipo,
                "hechas": sum(1 for fila in del_tipo if fila["completada"]),
                "total": len(del_tipo),
            }
        )
    return grupos


def guia_de(mission: Mission) -> dict:
    """Guia operativa de una mision: como se hace, el atajo y lo que no cuenta.

    Busca en GUIAS por el codigo ("D1", "S4") y, si la mision no lleva codigo,
    por su titulo. Cuando no hay guia escrita devuelve una generica construida
    con los propios campos de la mision, para que el detalle nunca salga vacio.
    """
    codigo, titulo = partir_titulo(mission.titulo)
    guia = GUIAS.get(codigo) or GUIAS.get(titulo)
    if guia is not None:
        return {"generica": False, **guia}

    pasos = []
    if mission.descripcion:
        pasos.append(mission.descripcion)
    pasos.append(f"Terminada cuando: {mission.definicion_terminada.lower()}.")
    if mission.evidencia_requerida:
        pasos.append("Anota la evidencia al darla por hecha: sin evidencia no cuenta.")
    return {"generica": True, "pasos": pasos, "nota": mission.motivo}


def detalle_de_mision(mission: Mission, fecha: dt.date | None = None) -> dict:
    """Contexto del detalle de una mision: la mision, su guia y si esta hecha."""
    fecha = fecha or timezone.localdate()
    codigo, titulo = partir_titulo(mission.titulo)
    return {
        "mision": mission,
        "codigo": codigo,
        "titulo": titulo,
        "guia": guia_de(mission),
        "completada": esta_completada(mission, fecha),
        "notas": notas_de(mission, fecha),
    }


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

    cerradas = MissionLog.objects.filter(fecha=fecha, completada=True).select_related(
        "mission"
    )
    hechas = {registro.mission_id for registro in cerradas}
    # Grupos ya cerrados hoy: su otra variante deja de ofrecerse.
    grupos_hechos = {
        registro.mission.grupo for registro in cerradas if registro.mission.grupo
    }
    notas_del_dia = dict(
        MissionLog.objects.filter(fecha=fecha)
        .exclude(notas="")
        .values_list("mission_id", "notas")
    )
    # Las de eleccion salen del listado normal: van en su propio bloque.
    elecciones: dict[str, dict] = {}
    for mision in misiones:
        if not mision.eleccion:
            continue
        pool = elecciones.setdefault(
            mision.eleccion, {"clave": mision.eleccion, "opciones": [], "elegida": None}
        )
        codigo, titulo = partir_titulo(mision.titulo)
        opcion = {
            "mision": mision,
            "codigo": codigo,
            "titulo": titulo,
            "completada": mision.pk in hechas,
        }
        pool["opciones"].append(opcion)
        if opcion["completada"]:
            pool["elegida"] = opcion

    filas = []
    for mision in misiones:
        if mision.eleccion:
            continue
        if mision.grupo and mision.grupo in grupos_hechos and mision.pk not in hechas:
            continue
        codigo, titulo = partir_titulo(mision.titulo)
        filas.append(
            {
                "mision": mision,
                "completada": mision.pk in hechas,
                "codigo": codigo,
                "titulo": titulo,
                "notas": notas_del_dia.get(mision.pk, ""),
                # Lo de ayer solo se pinta en las misiones de cuaderno, que es
                # donde tiene sentido releerlo por la manana.
                "anteriores": ultimas_notas(mision, fecha) if mision.pide_notas else None,
            }
        )
    # El marcador de arriba cuenta solo el ritmo del dia (diarias y semanales).
    # Mensuales y principales son de otro plazo: llevan su propio recuento por
    # grupo y meterlas aqui haria que el panel pareciera peor de lo que va.
    del_dia = [f for f in filas if f["mision"].tipo in TIPOS_DEL_DIA]
    # Cada grupo de eleccion cuenta como una sola casilla del dia: elegir una
    # ruta no puede penalizar frente a quien no elige.
    hechas_dia = sum(1 for fila in del_dia if fila["completada"])
    hechas_dia += sum(1 for pool in elecciones.values() if pool["elegida"])
    total_dia = len(del_dia) + len(elecciones)
    return {
        "fecha": fecha,
        "dia_protegido": protegido,
        "modo_minimo": minimo,
        "reinicio": progression.semana_de_reinicio(fecha),
        "filas": filas,
        "grupos": agrupar_filas(filas),
        "elecciones": sorted(elecciones.values(), key=lambda p: p["clave"]),
        "pct": round(hechas_dia / total_dia * 100) if total_dia else 0,
        "hechas": hechas_dia,
        "total": total_dia,
    }


# --- Catalogo completo -------------------------------------------------------
#
# La pantalla de misiones enseña TODAS las activas, no solo las de hoy. Se
# agrupan por periodicidad en el orden real (diarias, semanales, mensuales,
# principales, anuales), no por el alfabeto del valor guardado, que era lo que
# pasaba: "MENSUAL" va antes que "SEMANAL" si ordenas por texto.


def _cerradas_por_periodo(fecha: dt.date) -> set[int]:
    """Misiones ya cerradas dentro de su propio periodo.

    Una diaria cuenta si se hizo hoy; una semanal, si se hizo esta semana; una
    mensual, este mes; una principal, alguna vez. Compararlas todas contra hoy
    daria una foto falsa del catalogo.
    """
    lunes, domingo = progression.rango_de_la_semana(fecha)
    primero = fecha.replace(day=1)
    if primero.month == 12:
        siguiente = primero.replace(year=primero.year + 1, month=1)
    else:
        siguiente = primero.replace(month=primero.month + 1)
    ultimo_del_mes = siguiente - dt.timedelta(days=1)

    hechas: set[int] = set()
    periodos = (
        (Mission.Tipo.DIARIA, (fecha, fecha)),
        (Mission.Tipo.SEMANAL, (lunes, domingo)),
        (Mission.Tipo.MENSUAL, (primero, ultimo_del_mes)),
    )
    for tipo, (desde, hasta) in periodos:
        hechas |= set(
            MissionLog.objects.filter(
                completada=True, fecha__range=(desde, hasta), mission__tipo=tipo
            ).values_list("mission_id", flat=True)
        )

    # Principales y anuales: se cierran una vez en la vida del sistema.
    hechas |= set(
        MissionLog.objects.filter(
            completada=True,
            mission__tipo__in=(Mission.Tipo.PRINCIPAL, Mission.Tipo.ANUAL),
        ).values_list("mission_id", flat=True)
    )
    return hechas


def _estado_de_disponibilidad(mission: Mission, rango) -> dict:
    """Si la mision esta disponible para el rango actual, y si no, por que."""
    if rango is None or (mission.rango_min_id is None and mission.rango_max_id is None):
        return {"disponible": True, "motivo": ""}

    if mission.rango_min and mission.rango_min.orden > rango.orden:
        return {
            "disponible": False,
            "motivo": f"Se desbloquea en {mission.rango_min.nombre}",
        }
    if mission.rango_max and mission.rango_max.orden < rango.orden:
        return {
            "disponible": False,
            "motivo": f"Cerrada al superar {mission.rango_max.nombre}",
        }
    return {"disponible": True, "motivo": ""}


def catalogo_de_misiones(fecha: dt.date | None = None, tipo: str = "") -> dict:
    """Todas las misiones activas, agrupadas por periodicidad y en orden."""
    fecha = fecha or timezone.localdate()
    rango = _rango_actual()

    consulta = Mission.objects.filter(activa=True).select_related(
        "attribute", "rango_min", "rango_max"
    )
    if tipo:
        consulta = consulta.filter(tipo=tipo)

    # La variante minima va justo detras de su version normal.
    misiones = list(consulta.order_by("orden", "es_minima", "titulo"))
    hechas = _cerradas_por_periodo(fecha)

    filas = []
    for mision in misiones:
        codigo, titulo = partir_titulo(mision.titulo)
        filas.append(
            {
                "mision": mision,
                "codigo": codigo,
                "titulo": titulo,
                "completada": mision.pk in hechas,
                **_estado_de_disponibilidad(mision, rango),
            }
        )

    grupos = agrupar_filas(filas)
    # El recuento de cada pestaña se calcula sobre el catalogo entero, no sobre
    # lo filtrado: si no, al filtrar las demas pestañas marcarian cero.
    totales = dict(
        Mission.objects.filter(activa=True)
        .values_list("tipo")
        .annotate(n=models.Count("pk"))
    )

    return {
        "grupos": grupos,
        "tipo_activo": tipo,
        "pestanas": [
            {"clave": clave, "etiqueta": etiqueta, "total": totales.get(clave, 0)}
            for clave, etiqueta, _sub, _acento in GRUPOS
            if totales.get(clave)
        ],
        "total": sum(totales.values()),
        "hechas": sum(1 for f in filas if f["completada"]),
        "rango": rango,
    }
