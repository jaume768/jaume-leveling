"""Logica del Sistema de cazador.

Es la capa de juego encima de lo que ya existe: rangos de cazador (E a S),
avisos del Sistema, titulos, habilidades, cofre diario, escudos de racha, el
ejercito de sombras y las notificaciones al movil.

Regla de oro: aqui no se inventa XP. Todo lo que se concede (titulos,
cofres, escudos, marcos) es cosmetico o protege la racha; la XP sigue
saliendo solo de hechos registrados en las otras apps.
"""
from __future__ import annotations

import datetime as dt
import json
import random
from decimal import Decimal

from django.apps import apps
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Aviso, Cazador, Cofre, EnvioPush, Escudo, Logro, SuscripcionPush

# --- Rangos de cazador -----------------------------------------------------------
#
# Se atan al orden del rango, no a su nombre: Rank.nombre sigue siendo la etapa
# de negocio (Operador, Especialista...) y aqui vive la clase de cazador que se
# ve en pantalla. Cada ascenso concede ademas un titulo.

RANGOS_CAZADOR = {
    1: {"letra": "E", "clase": "Despertado", "color": "#9aa6b8", "titulo": "El que despierta"},
    2: {"letra": "D", "clase": "Cazador", "color": "#34d399", "titulo": "Ejecutor"},
    3: {"letra": "C", "clase": "Asesino", "color": "#38bdf8", "titulo": "Maestro del oficio"},
    4: {"letra": "B", "clase": "Invocador", "color": "#a78bfa", "titulo": "Arquitecto"},
    5: {"letra": "A", "clase": "Rompecadenas", "color": "#f59e0b", "titulo": "Cazador de rango nacional"},
    6: {"letra": "S", "clase": "Monarca", "color": "#8b5cf6", "titulo": "Soberano"},
}


def rango_cazador(orden: int | None) -> dict:
    """Letra, clase, color y titulo de ascenso de un rango. Vacio si no existe."""
    datos = RANGOS_CAZADOR.get(orden or 0)
    return {**datos, "orden": orden} if datos else {}


def retrato_de_rango(orden: int | None) -> str:
    """Retrato del personaje para ese rango, o el general si no hay uno propio.

    Basta con dejar static/img/retratos/rango-<orden>.webp para que aparezca.
    """
    from django.contrib.staticfiles import finders

    ruta = f"img/retratos/rango-{orden}.webp"
    if orden and finders.find(ruta):
        return ruta
    return "img/personaje.webp"


# --- Dias con racha ---------------------------------------------------------------


def _es_protegido(fecha: dt.date) -> bool:
    from progression import services as progression

    return progression.es_dia_protegido(fecha)


def dias_con_accion(desde: dt.date, hasta: dt.date) -> set[dt.date]:
    """Dias con alguna mision que cuenta para la racha. Una sola consulta."""
    MissionLog = apps.get_model("missions", "MissionLog")
    return set(
        MissionLog.objects.filter(
            fecha__range=(desde, hasta),
            completada=True,
            mission__cuenta_para_racha=True,
        ).values_list("fecha", flat=True)
    )


def dias_con_escudo(desde: dt.date, hasta: dt.date) -> set[dt.date]:
    return set(
        Escudo.objects.filter(usado_en__range=(desde, hasta)).values_list("usado_en", flat=True)
    )


def cadena_de_dias(fecha: dt.date | None = None, semanas: int = 6) -> list[list[dict]]:
    """Cuadricula de las ultimas semanas, de lunes a domingo, para pintar la cadena."""
    fecha = fecha or timezone.localdate()
    lunes_actual = fecha - dt.timedelta(days=fecha.weekday())
    inicio = lunes_actual - dt.timedelta(weeks=semanas - 1)
    fin = lunes_actual + dt.timedelta(days=6)
    hechos = dias_con_accion(inicio, fecha)
    escudos = dias_con_escudo(inicio, fecha)
    # Antes de que el Sistema arrancara no hubo nada que fallar.
    from core.models import Profile

    arranque = Profile.get().fecha_inicio

    filas = []
    for s in range(semanas):
        fila = []
        for d in range(7):
            dia = inicio + dt.timedelta(days=s * 7 + d)
            if dia > fin:
                break
            if dia > fecha:
                estado = "futuro"
            elif dia < arranque and dia not in hechos:
                estado = "previo"
            elif dia in hechos:
                estado = "hecho"
            elif dia in escudos:
                estado = "escudo"
            elif _es_protegido(dia):
                estado = "protegido"
            elif dia == fecha:
                estado = "hoy"
            else:
                estado = "fallado"
            fila.append({"fecha": dia, "estado": estado, "hoy": dia == fecha})
        filas.append(fila)
    return filas


def mejor_racha(fecha: dt.date | None = None) -> int:
    """La racha mas larga de la historia, con las mismas reglas que la actual."""
    fecha = fecha or timezone.localdate()
    MissionLog = apps.get_model("missions", "MissionLog")
    primera = (
        MissionLog.objects.filter(completada=True, mission__cuenta_para_racha=True)
        .order_by("fecha")
        .values_list("fecha", flat=True)
        .first()
    )
    if primera is None:
        return 0
    hechos = dias_con_accion(primera, fecha)
    escudos = dias_con_escudo(primera, fecha)
    mejor = actual = 0
    dia = primera
    while dia <= fecha:
        if dia in hechos:
            actual += 1
            mejor = max(mejor, actual)
        elif dia in escudos or _es_protegido(dia) or dia == fecha:
            pass  # no suma ni rompe; hoy aun no ha terminado
        else:
            actual = 0
        dia += dt.timedelta(days=1)
    return mejor


# --- Escudos de racha ------------------------------------------------------------

MAX_ESCUDOS = 2
FRAGMENTOS_POR_ESCUDO = 5
# Dias del sistema en una semana: lunes, martes, jueves, viernes y sabado.
DIAS_DEL_SISTEMA = (0, 1, 3, 4, 5)


def escudos_disponibles() -> int:
    return Escudo.objects.filter(usado_en__isnull=True).count()


def ganar_escudo(motivo: str, fecha: dt.date | None = None) -> Escudo | None:
    """Concede un escudo si queda hueco. Nunca hay mas de MAX_ESCUDOS guardados."""
    if escudos_disponibles() >= MAX_ESCUDOS:
        return None
    if Escudo.objects.filter(motivo=motivo).exists():
        return None
    escudo = Escudo.objects.create(motivo=motivo, ganado=fecha or timezone.localdate())
    avisar(
        Aviso.Tipo.ESCUDO,
        "Escudo de racha obtenido",
        f"{motivo}. Salvará un día fallado.",
        clave=f"escudo-ganado:{escudo.pk}",
    )
    return escudo


def racha_hasta(fecha: dt.date) -> int:
    """Racha que habia al terminar `fecha` (incluida), con escudos."""
    inicio = fecha - dt.timedelta(days=400)
    hechos = dias_con_accion(inicio, fecha)
    escudos = dias_con_escudo(inicio, fecha)
    dias = 0
    cursor = fecha
    while cursor >= inicio:
        if cursor in hechos:
            dias += 1
        elif not (cursor in escudos or _es_protegido(cursor)):
            break
        cursor -= dt.timedelta(days=1)
    return dias


def cerrar_dia(dia: dt.date) -> list[str]:
    """Cierre de un dia ya terminado: usa un escudo si hace falta y premia semanas.

    Idempotente: se puede llamar varias veces para el mismo dia.
    """
    hechos: list[str] = []
    if not _es_protegido(dia) and not dias_con_accion(dia, dia):
        ya_salvado = Escudo.objects.filter(usado_en=dia).exists()
        racha_previa = racha_hasta(dia - dt.timedelta(days=1))
        if not ya_salvado and racha_previa > 0:
            escudo = Escudo.objects.filter(usado_en__isnull=True).first()
            if escudo is not None:
                escudo.usado_en = dia
                escudo.save(update_fields=["usado_en"])
                avisar(
                    Aviso.Tipo.ESCUDO,
                    "Escudo de racha usado",
                    f"El {dia:%d/%m} no hubo misión de racha. El escudo salvó tus {racha_previa} días.",
                    clave=f"escudo-usado:{dia.isoformat()}",
                )
                hechos.append(f"escudo usado el {dia}")

    # El sabado cierra la semana del sistema: si los cinco dias tuvieron
    # mision de racha (sin escudos), se gana un escudo.
    if dia.weekday() == 5:
        lunes = dia - dt.timedelta(days=5)
        reales = dias_con_accion(lunes, dia)
        dias = [lunes + dt.timedelta(days=d) for d in DIAS_DEL_SISTEMA]
        if all(d in reales for d in dias):
            anio, semana, _ = dia.isocalendar()
            if ganar_escudo(f"Semana perfecta {anio}-S{semana:02d}", dia):
                hechos.append("escudo ganado por semana perfecta")

    hechos += [f"logro: {n}" for n in revisar_logros(dia)]
    return hechos


# --- Misiones diarias ---------------------------------------------------------------


def estado_diarias(fecha: dt.date | None = None) -> dict:
    """Las diarias de hoy (sin semanales): cuantas hay, cuantas hechas y cuales."""
    from missions import services as missions
    from missions.models import Mission

    fecha = fecha or timezone.localdate()
    panel = missions.panel_de_misiones(fecha)
    filas = [f for f in panel["filas"] if f["mision"].tipo == Mission.Tipo.DIARIA]
    elecciones = panel["elecciones"]
    total = len(filas) + len(elecciones)
    hechas = sum(1 for f in filas if f["completada"]) + sum(1 for p in elecciones if p["elegida"])
    return {
        "filas": filas,
        "elecciones": elecciones,
        "total": total,
        "hechas": hechas,
        "pendientes": total - hechas,
        "completas": total > 0 and hechas == total,
        "protegido": panel["dia_protegido"],
    }


def tras_mision(fecha: dt.date | None = None) -> None:
    """Despues de cerrar una mision: si las diarias estan completas, cofre."""
    fecha = fecha or timezone.localdate()
    if estado_diarias(fecha)["completas"]:
        Cofre.objects.get_or_create(fecha=fecha)
        avisar(
            Aviso.Tipo.COFRE,
            "Misión diaria completada",
            "Has ganado el cofre del día. Ábrelo en Hoy.",
            clave=f"cofre:{fecha.isoformat()}",
        )


# --- Cofre diario ---------------------------------------------------------------------

MARCOS = {
    "sistema": {"nombre": "Sistema", "color": "#3fc5ff"},
    "hielo": {"nombre": "Hielo", "color": "#a5f3fc"},
    "jade": {"nombre": "Jade", "color": "#34d399"},
    "carmesi": {"nombre": "Carmesí", "color": "#ff4d6d"},
    "oro": {"nombre": "Oro", "color": "#fbbf24"},
    "sombra": {"nombre": "Sombra", "color": "#8b5cf6"},
}
MARCO_INICIAL = "sistema"

# Probabilidades del botin: pagina del Codice, fragmento de runa o marco.
PESOS_BOTIN = (("codice", 45), ("fragmento", 40), ("marco", 15))


def marcos_desbloqueados() -> set[str]:
    claves = set(Logro.objects.filter(tipo=Logro.Tipo.MARCO).values_list("clave", flat=True))
    return claves | {MARCO_INICIAL}


def cofre_de_hoy(fecha: dt.date | None = None) -> dict:
    fecha = fecha or timezone.localdate()
    cofre = Cofre.objects.filter(fecha=fecha).first()
    return {"cofre": cofre, "disponible": bool(cofre and not cofre.abierto)}


def _elegir_botin(rng: random.Random) -> str:
    tipos = [t for t, _ in PESOS_BOTIN]
    pesos = [p for _, p in PESOS_BOTIN]
    if not set(MARCOS) - marcos_desbloqueados():
        i = tipos.index("marco")
        tipos.pop(i)
        pesos.pop(i)
    return rng.choices(tipos, weights=pesos, k=1)[0]


@transaction.atomic
def abrir_cofre(fecha: dt.date | None = None, rng: random.Random | None = None) -> Cofre | None:
    """Abre el cofre de hoy y reparte el botin. None si no hay cofre que abrir."""
    fecha = fecha or timezone.localdate()
    rng = rng or random.Random()
    cofre = Cofre.objects.select_for_update().filter(fecha=fecha, abierto=False).first()
    if cofre is None:
        return None

    tipo = _elegir_botin(rng)
    if tipo == "codice":
        Maxim = apps.get_model("wisdom", "Maxim")
        maxima = Maxim.objects.order_by("?").first()
        if maxima is None:
            tipo = "fragmento"
        else:
            cofre.titulo = f"Página del Códice · {maxima.titulo}"
            cofre.texto = maxima.texto
    if tipo == "marco":
        libres = sorted(set(MARCOS) - marcos_desbloqueados())
        clave = rng.choice(libres)
        Logro.objects.get_or_create(tipo=Logro.Tipo.MARCO, clave=clave)
        cofre.titulo = f"Marco «{MARCOS[clave]['nombre']}»"
        cofre.texto = "Nuevo marco para tu ventana de Estado. Equípalo allí."
    if tipo == "fragmento":
        ficha = Cazador.get()
        ficha.fragmentos += 1
        cofre.titulo = "Fragmento de runa"
        cofre.texto = (
            f"Llevas {ficha.fragmentos}/{FRAGMENTOS_POR_ESCUDO}. "
            f"Con {FRAGMENTOS_POR_ESCUDO} se forja un escudo de racha."
        )
        if ficha.fragmentos >= FRAGMENTOS_POR_ESCUDO and escudos_disponibles() < MAX_ESCUDOS:
            ficha.fragmentos -= FRAGMENTOS_POR_ESCUDO
            Escudo.objects.create(motivo=f"Forjado con runas ({fecha:%d/%m/%Y})", ganado=fecha)
            cofre.texto = "¡Cinco fragmentos! La runa se ha forjado en un escudo de racha."
        ficha.save(update_fields=["fragmentos"])

    cofre.tipo = tipo
    cofre.abierto = True
    cofre.save()
    revisar_logros(fecha)
    return cofre


# --- Ejercito de sombras ----------------------------------------------------------


def ejercito_de_sombras() -> dict:
    """Cada cliente con mantenimiento recurrente es una sombra a tu servicio."""
    from business import services as business
    from business.models import Client

    sombras = []
    for cliente in Client.objects.filter(estado=Client.Estado.ACTIVO, mrr__gt=0).order_by("-mrr"):
        mrr = cliente.mrr
        if mrr >= 300:
            grado = "Élite"
        elif mrr >= 150:
            grado = "Caballero"
        else:
            grado = "Soldado"
        sombras.append({"cliente": cliente, "mrr": mrr, "grado": grado})
    total = business.recurrente_activo()
    objetivo = Decimal("1200")  # docs/sistema-v2.md: 1.200 EUR/mes en el punto de decision
    return {
        "sombras": sombras,
        "total": total,
        "objetivo": objetivo,
        "pct": min(100, int(total / objetivo * 100)) if objetivo else 0,
    }


# --- Titulos y habilidades -----------------------------------------------------------
#
# Cada logro tiene una condicion que se evalua con datos reales. Una vez
# desbloqueado, queda para siempre (aunque la cifra baje despues).


def _misiones_hechas(*slugs: str) -> int:
    MissionLog = apps.get_model("missions", "MissionLog")
    return MissionLog.objects.filter(completada=True, mission__slug__in=slugs).count()


def _mejor_semana_xp() -> int:
    XPEvent = apps.get_model("progression", "XPEvent")
    semanas: dict[tuple, int] = {}
    for fecha, xp in XPEvent.objects.filter(xp_neto__gt=0).values_list("fecha", "xp_neto"):
        clave = fecha.isocalendar()[:2]
        semanas[clave] = semanas.get(clave, 0) + xp
    return max(semanas.values(), default=0)


def _rechazo_por_precio() -> bool:
    Deal = apps.get_model("business", "Deal")
    return Deal.objects.filter(rechazado_por_precio=True).exists()


def _sector_repetido() -> int:
    from django.db.models import Count

    Client = apps.get_model("business", "Client")
    fila = (
        Client.objects.exclude(sector="")
        .values("sector")
        .annotate(n=Count("pk"))
        .order_by("-n")
        .first()
    )
    return fila["n"] if fila else 0


def _orden_de_rango() -> int:
    from core import services as core
    from core.models import Profile

    perfil = Profile.get()
    rango = perfil.rango or core.rango_para_nivel(perfil.nivel)
    return rango.orden if rango else 0


def _sin_facturas_vencidas() -> bool:
    from business import services as business

    return not business.facturas_vencidas().exists()


def _cobrado() -> float:
    from core import services as core

    return core.total_cobrado()


def _semanas_pipeline() -> int:
    from core import services as core

    return core.semanas_seguidas_con_pipeline()


def _casos() -> int:
    from core import services as core

    return core.casos_publicados()


def _recurrente() -> Decimal:
    from business import services as business

    return business.recurrente_activo()


TITULOS = [
    {"clave": "el-que-despierta", "nombre": "El que despierta",
     "como": "Ser elegido por el Sistema.", "cond": lambda: True},
    {"clave": "primera-sangre", "nombre": "Primera sangre",
     "como": "Completar tu primera misión.",
     "cond": lambda: apps.get_model("missions", "MissionLog").objects.filter(completada=True).exists()},
    {"clave": "imparable", "nombre": "Imparable",
     "como": "Racha de 5 días.", "cond": lambda: mejor_racha() >= 5},
    {"clave": "inquebrantable", "nombre": "Inquebrantable",
     "como": "Racha de 15 días.", "cond": lambda: mejor_racha() >= 15},
    {"clave": "el-que-cobra", "nombre": "El que cobra a tiempo",
     "como": "2.000 € cobrados.", "cond": lambda: _cobrado() >= 2000},
    {"clave": "cazador-de-contactos", "nombre": "Cazador de contactos",
     "como": "4 semanas seguidas con 6 contactos.", "cond": lambda: _semanas_pipeline() >= 4},
    {"clave": "portador-de-sombras", "nombre": "Portador de sombras",
     "como": "Tu primer cliente recurrente.", "cond": lambda: _recurrente() > 0},
    {"clave": "el-que-dice-no", "nombre": "El que dice no",
     "como": "Rechazar un proyecto por precio bajo.", "cond": _rechazo_por_precio},
    {"clave": "semana-perfecta", "nombre": "Semana perfecta",
     "como": "750 XP en una semana.", "cond": lambda: _mejor_semana_xp() >= 750},
    {"clave": "coleccionista", "nombre": "Coleccionista",
     "como": "Abrir 10 cofres.", "cond": lambda: Cofre.objects.filter(abierto=True).count() >= 10},
] + [
    {"clave": f"rango-{orden}", "nombre": datos["titulo"],
     "como": f"Ascender a rango {datos['letra']}.",
     "cond": (lambda o=orden: _orden_de_rango() >= o)}
    for orden, datos in RANGOS_CAZADOR.items() if orden > 1
]

# El arbol de habilidades de docs/sistema-v2.md, §4. "esencial" son las verdes.
HABILIDADES = [
    {"clave": "ofertas-recurrentes", "nombre": "Ofertas recurrentes", "nivel": "esencial",
     "nota": "La habilidad de mayor retorno que tienes disponible hoy.",
     "como": "Firmar tu primer mantenimiento.", "cond": lambda: _recurrente() > 0},
    {"clave": "suelo-de-precio", "nombre": "Suelo de precio", "nivel": "esencial",
     "nota": "Decir el número sin justificarte.",
     "como": "Rechazar un proyecto por precio bajo.",
     "cond": lambda: _rechazo_por_precio() or _misiones_hechas("el-suelo") > 0},
    {"clave": "pipeline-sostenido", "nombre": "Pipeline sostenido", "nivel": "esencial",
     "nota": "6 contactos/semana, entregues o no.",
     "como": "4 semanas seguidas con 6 contactos.", "cond": lambda: _semanas_pipeline() >= 4},
    {"clave": "casos-de-estudio", "nombre": "Casos de estudio", "nivel": "esencial",
     "nota": "Tienes el trabajo hecho: capitalízalo.",
     "como": "Publicar un caso de estudio con número.", "cond": lambda: _casos() >= 1},
    {"clave": "plantilla-reutilizable", "nombre": "Plantilla reutilizable", "nivel": "esencial",
     "nota": "Multiplica tu tarifa efectiva sin subir el precio.",
     "como": "Actualizar la plantilla de entrega (M8).", "cond": lambda: _misiones_hechas("m8") > 0},
    {"clave": "cobrador-implacable", "nombre": "Cobrador implacable", "nivel": "esencial",
     "nota": "Cobros y seguimiento administrativo al día.",
     "como": "2.000 € cobrados y ninguna factura vencida.",
     "cond": lambda: _cobrado() >= 2000 and _sin_facturas_vencidas()},
    {"clave": "vertical", "nombre": "Vertical", "nivel": "esencial",
     "nota": "Especializar duplica la tarifa.",
     "como": "3 clientes del mismo sector.",
     "cond": lambda: _sector_repetido() >= 3 or _misiones_hechas("vertical") > 0},
    {"clave": "integraciones-ia", "nombre": "Integraciones IA", "nivel": "esencial",
     "nota": "Tu diferenciador de 12 meses.",
     "como": "Vender o medir una automatización (M7 o M11).",
     "cond": lambda: _misiones_hechas("m7", "m11") > 0},
    {"clave": "precio-por-valor", "nombre": "Precio por valor", "nivel": "despues",
     "nota": "A partir del mes 3.",
     "como": "Enviar una propuesta con 3 opciones (M6).", "cond": lambda: _misiones_hechas("m6") > 0},
    {"clave": "delegar", "nombre": "Delegar", "nivel": "despues",
     "nota": "Lo que rompe el techo de las 10 h.",
     "como": "Delegar una tarea a un colaborador (M10).",
     "cond": lambda: _misiones_hechas("m10", "el-primer-contrato-sin-ti") > 0},
    {"clave": "marca-personal", "nombre": "Marca personal", "nivel": "despues",
     "nota": "2 publicaciones/semana, 25 min. No más.",
     "como": "Cumplir 4 semanas de publicaciones.",
     "cond": lambda: _misiones_hechas("publicaciones-semana") >= 4},
]

TITULOS_POR_CLAVE = {t["clave"]: t for t in TITULOS}


def revisar_logros(fecha: dt.date | None = None) -> list[str]:
    """Desbloquea los titulos y habilidades cuya condicion ya se cumple."""
    fecha = fecha or timezone.localdate()
    tengo = set(Logro.objects.values_list("tipo", "clave"))
    nuevos = []
    for tipo, lista in ((Logro.Tipo.TITULO, TITULOS), (Logro.Tipo.HABILIDAD, HABILIDADES)):
        for logro in lista:
            if (tipo, logro["clave"]) in tengo or not logro["cond"]():
                continue
            try:
                with transaction.atomic():
                    Logro.objects.create(tipo=tipo, clave=logro["clave"], fecha=fecha)
            except IntegrityError:
                continue
            nuevos.append(logro["nombre"])
            if tipo == Logro.Tipo.TITULO:
                avisar(Aviso.Tipo.TITULO, "Título obtenido", logro["nombre"],
                       clave=f"titulo:{logro['clave']}")
            else:
                avisar(Aviso.Tipo.HABILIDAD, "Habilidad desbloqueada", logro["nombre"],
                       clave=f"habilidad:{logro['clave']}")
    return nuevos


def titulos() -> list[dict]:
    tengo = dict(Logro.objects.filter(tipo=Logro.Tipo.TITULO).values_list("clave", "fecha"))
    return [{**{k: v for k, v in t.items() if k != "cond"}, "fecha": tengo.get(t["clave"]),
             "desbloqueado": t["clave"] in tengo} for t in TITULOS]


def habilidades() -> list[dict]:
    tengo = dict(Logro.objects.filter(tipo=Logro.Tipo.HABILIDAD).values_list("clave", "fecha"))
    return [{**{k: v for k, v in h.items() if k != "cond"}, "fecha": tengo.get(h["clave"]),
             "desbloqueada": h["clave"] in tengo} for h in HABILIDADES]


def equipar_titulo(clave: str) -> str:
    """Equipa un titulo desbloqueado. Cadena vacia lo quita."""
    ficha = Cazador.get()
    if clave and not Logro.objects.filter(tipo=Logro.Tipo.TITULO, clave=clave).exists():
        raise ValueError("Ese título aún no está desbloqueado.")
    ficha.titulo_equipado = TITULOS_POR_CLAVE[clave]["nombre"] if clave else ""
    ficha.save(update_fields=["titulo_equipado"])
    return ficha.titulo_equipado


def equipar_marco(clave: str) -> None:
    if clave not in MARCOS or clave not in marcos_desbloqueados():
        raise ValueError("Ese marco aún no está desbloqueado.")
    ficha = Cazador.get()
    ficha.marco = clave
    ficha.save(update_fields=["marco"])


def cambiar_alias(alias: str) -> str:
    ficha = Cazador.get()
    ficha.alias = (alias or "").strip()[:40]
    ficha.save(update_fields=["alias"])
    return ficha.alias


# --- Avisos del Sistema --------------------------------------------------------------


def avisar(tipo: str, titulo: str, texto: str = "", valor: int = 0, clave: str | None = None):
    """Crea un aviso. Con clave, el mismo hecho solo avisa una vez."""
    if clave and Aviso.objects.filter(clave=clave).exists():
        return None
    try:
        with transaction.atomic():
            return Aviso.objects.create(tipo=tipo, titulo=titulo, texto=texto, valor=valor, clave=clave)
    except IntegrityError:
        return None


def hay_avisos_pendientes() -> bool:
    return Aviso.objects.filter(visto=False).exists()


def recoger_avisos() -> list[Aviso]:
    """Los avisos sin ver, ya marcados como vistos: cada uno se pinta una vez."""
    pendientes = list(Aviso.objects.filter(visto=False)[:12])
    if pendientes:
        Aviso.objects.filter(pk__in=[a.pk for a in pendientes]).update(visto=True)
    return pendientes


def tras_xp(evento, nivel_antes: int, orden_rango_antes: int) -> None:
    """Gancho de progression.registrar_xp: avisos de XP, nivel, rango y logros."""
    from core.models import Profile

    if evento.xp_neto > 0:
        avisar(Aviso.Tipo.XP, f"+{evento.xp_neto} XP", evento.descripcion[:255], valor=evento.xp_neto)
    elif evento.xp_neto < 0:
        avisar(Aviso.Tipo.PENALIZACION, f"{evento.xp_neto} XP", evento.descripcion[:255],
               valor=evento.xp_neto)

    perfil = Profile.get()
    if perfil.nivel > nivel_antes:
        avisar(Aviso.Tipo.NIVEL, "¡Has subido de nivel!", f"Nivel {perfil.nivel}",
               valor=perfil.nivel, clave=f"nivel:{perfil.nivel}")
    orden = perfil.rango.orden if perfil.rango else 0
    if orden > orden_rango_antes and orden in RANGOS_CAZADOR:
        datos = RANGOS_CAZADOR[orden]
        avisar(Aviso.Tipo.RANGO, f"Ascenso a rango {datos['letra']}",
               f"Clase: {datos['clase']}", valor=orden, clave=f"rango:{orden}")
    revisar_logros(evento.fecha)


# --- Hoy y Estado -----------------------------------------------------------------------


def contexto_hoy(fecha: dt.date | None = None) -> dict:
    """Lo que añade el Sistema a la pantalla de Hoy."""
    from progression import services as progression

    fecha = fecha or timezone.localdate()
    diarias = estado_diarias(fecha)
    if diarias["total"] and not diarias["protegido"]:
        avisar(
            Aviso.Tipo.MISION_DIARIA,
            "La misión diaria ha llegado",
            f"{diarias['total']} misiones · se reinicia a las 00:00",
            valor=diarias["total"],
            clave=f"mision-diaria:{fecha.isoformat()}",
        )
    racha = progression.racha_actual(fecha)
    hecho_hoy = bool(dias_con_accion(fecha, fecha))
    return {
        "diarias": diarias,
        "cadena": cadena_de_dias(fecha),
        "mejor_racha": mejor_racha(fecha),
        "escudos": escudos_disponibles(),
        "max_escudos": MAX_ESCUDOS,
        "fragmentos": Cazador.get().fragmentos,
        "fragmentos_por_escudo": FRAGMENTOS_POR_ESCUDO,
        "racha_en_juego": racha > 0 and not hecho_hoy and not _es_protegido(fecha),
        "racha_asegurada": hecho_hoy,
        "cofre": cofre_de_hoy(fecha),
        "zona_segura": _es_protegido(fecha),
        "cazador": Cazador.get(),
    }


def contexto_estado() -> dict:
    """Lo que añade el Sistema a la ventana de Estado (antes, Personaje)."""
    ficha = Cazador.get()
    lista_titulos = titulos()
    lista_habilidades = habilidades()
    desbloqueados = marcos_desbloqueados()
    return {
        "cazador": ficha,
        "titulos": lista_titulos,
        "titulos_obtenidos": sum(1 for t in lista_titulos if t["desbloqueado"]),
        "habilidades": lista_habilidades,
        "habilidades_obtenidas": sum(1 for h in lista_habilidades if h["desbloqueada"]),
        "marcos": [{"clave": c, **d, "desbloqueado": c in desbloqueados} for c, d in MARCOS.items()],
        "marco": MARCOS.get(ficha.marco, MARCOS[MARCO_INICIAL]),
        "sombras": ejercito_de_sombras(),
        "mejor_racha": mejor_racha(),
        "escudos": escudos_disponibles(),
        "cofres_abiertos": Cofre.objects.filter(abierto=True).count(),
    }


# --- Notificaciones al movil (Web Push) -------------------------------------------------


def push_configurado() -> bool:
    return bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY)


def guardar_suscripcion(datos: dict, agente: str = "") -> SuscripcionPush:
    claves = datos.get("keys") or {}
    endpoint = datos.get("endpoint", "")
    if not endpoint or not claves.get("p256dh") or not claves.get("auth"):
        raise ValueError("Suscripción incompleta.")
    suscripcion, _ = SuscripcionPush.objects.update_or_create(
        endpoint=endpoint,
        defaults={"p256dh": claves["p256dh"], "auth": claves["auth"], "agente": agente[:200]},
    )
    return suscripcion


def enviar_push(titulo: str, cuerpo: str, url: str = "/", clave: str | None = None) -> int:
    """Envia una notificacion a todos los dispositivos. Devuelve a cuantos llego.

    Con clave, cada aviso programado sale una sola vez aunque el cron repita.
    """
    if not push_configurado():
        return 0
    if clave and EnvioPush.objects.filter(clave=clave).exists():
        return 0
    from pywebpush import WebPushException, webpush

    carga = json.dumps({"titulo": titulo, "cuerpo": cuerpo, "url": url})
    llegados = 0
    for suscripcion in SuscripcionPush.objects.all():
        try:
            webpush(
                subscription_info={
                    "endpoint": suscripcion.endpoint,
                    "keys": {"p256dh": suscripcion.p256dh, "auth": suscripcion.auth},
                },
                data=carga,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": settings.VAPID_SUBJECT},
                ttl=6 * 3600,
            )
            llegados += 1
        except WebPushException as exc:
            # 404/410: el navegador retiro la suscripcion. Se borra.
            estado = getattr(getattr(exc, "response", None), "status_code", None)
            if estado in (404, 410):
                suscripcion.delete()
    if clave:
        EnvioPush.objects.get_or_create(clave=clave, defaults={"destinos": llegados})
    return llegados


HORA_MANANA = 8
HORA_NOCHE = 21


def pulso(ahora: dt.datetime | None = None) -> list[str]:
    """Lo que el Sistema hace cada hora (cron horario): cierres y notificaciones.

    Va por hora local, asi que el cambio de horario no lo descuadra.
    """
    from progression import services as progression

    ahora = timezone.localtime(ahora)
    fecha = ahora.date()
    hechos = cerrar_dia(fecha - dt.timedelta(days=1))

    if ahora.hour == HORA_MANANA:
        if fecha.weekday() == progression.MIERCOLES:
            titulo, cuerpo = "Zona segura", "Hoy es miércoles: no hay misiones. Descansa."
        elif fecha.weekday() == progression.DOMINGO:
            titulo, cuerpo = "Domingo", "Hoy solo cuentan las semanales. Revisión a las 20:15."
        else:
            diarias = estado_diarias(fecha)
            titulo = "La misión diaria ha llegado"
            cuerpo = f"{diarias['total']} misiones te esperan. Se reinicia a las 00:00."
        if enviar_push(titulo, cuerpo, "/", clave=f"manana:{fecha.isoformat()}"):
            hechos.append("aviso de la mañana enviado")

    if ahora.hour == HORA_NOCHE and not _es_protegido(fecha):
        diarias = estado_diarias(fecha)
        racha = progression.racha_actual(fecha)
        if diarias["pendientes"]:
            cuerpo = f"Quedan 3 h. Te faltan {diarias['pendientes']} de {diarias['total']}."
            if racha and not dias_con_accion(fecha, fecha):
                cuerpo += f" Tu racha de {racha} días está en juego."
            enviado = enviar_push("[SISTEMA] Aviso", cuerpo, "/", clave=f"noche:{fecha.isoformat()}")
        elif cofre_de_hoy(fecha)["disponible"]:
            enviado = enviar_push("Cofre sin abrir", "Completaste la misión diaria. Tu cofre te espera.",
                                  "/", clave=f"noche:{fecha.isoformat()}")
        else:
            enviado = 0
        if enviado:
            hechos.append("aviso de la noche enviado")
    return hechos
