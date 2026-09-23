"""Logica de negocio de la app core.

Toda la logica vive aqui: las vistas son finas y los modelos son datos.
"""
from __future__ import annotations

# XP necesaria para subir un nivel, por tramos.
#
# El unico tramo documentado es 41-60 -> 2.000 XP/nivel (docs/sistema-v2.md, §6).
# El resto son extrapolaciones coherentes con la regla "a tu nivel, subir debe
# costar": se revisan cuando el sistema llegue a esos tramos.
TRAMOS_XP = (
    (1, 20, 500),
    (21, 40, 1_000),
    (41, 60, 2_000),
    (61, 80, 3_500),
    (81, 100, 5_000),
)

NIVEL_MAXIMO = 100


def xp_por_nivel(nivel: int) -> int:
    """XP necesaria para pasar de `nivel` al siguiente."""
    for minimo, maximo, coste in TRAMOS_XP:
        if minimo <= nivel <= maximo:
            return coste
    return TRAMOS_XP[-1][2]


def xp_acumulada_hasta_nivel(nivel: int) -> int:
    """XP total acumulada necesaria para alcanzar `nivel` desde el nivel 1."""
    return sum(xp_por_nivel(n) for n in range(1, nivel))


def progreso_en_nivel(nivel: int, xp_total: int) -> tuple[int, int, int]:
    """Devuelve (xp_en_el_nivel, xp_que_faltan, porcentaje) para el nivel dado.

    El porcentaje es entero a proposito: va directo a un `style="width: N%"` y
    con el locale espanol un float se renderiza como "0,0", que es CSS invalido.
    El navegador lo descarta y la barra aparece llena estando a cero.
    """
    coste = xp_por_nivel(nivel)
    base = xp_acumulada_hasta_nivel(nivel)
    en_nivel = max(0, min(xp_total - base, coste))
    if nivel >= NIVEL_MAXIMO:
        return coste, 0, 100
    return en_nivel, coste - en_nivel, round(en_nivel / coste * 100)


def nivel_para_xp(xp_total: int) -> int:
    """Nivel que corresponde a una XP total acumulada."""
    nivel = 1
    while nivel < NIVEL_MAXIMO and xp_total >= xp_acumulada_hasta_nivel(nivel + 1):
        nivel += 1
    return nivel


def rango_para_nivel(nivel: int):
    """Rango cuyo tramo contiene el nivel dado, o None si no hay ninguno."""
    from .models import Rank

    return Rank.objects.filter(nivel_min__lte=nivel, nivel_max__gte=nivel).first()


# --- Presentacion: navegacion y jefe de rango --------------------------------

# La navegacion es la misma en la barra lateral y en la barra inferior movil.
# Se declara una vez: nombre de la url, etiqueta, icono y si sale en movil.
NAVEGACION = (
    ("core:index", "Panel", "panel", True),
    ("missions:index", "Misiones", "misiones", True),
    ("core:niveles", "Niveles", "rangos", False),
    ("core:personaje", "Personaje", "usuario", False),
    ("core:calibracion", "Calibración", "reloj", False),
    ("progression:index", "Progresión", "progresion", False),
    ("progression:recompensas", "Recompensas", "rangos", False),
    ("business:index", "Negocio", "negocio", True),
    ("review:index", "Revisión", "revision", True),
    ("notebook:index", "Cuaderno", "cuaderno", False),
    ("wisdom:index", "Consejo", "consejo", False),
    ("wisdom:maximas", "Máximas", "maximas", False),
)


def navegacion(ruta: str) -> list[dict]:
    """Entradas del menu con su estado activo para la ruta actual.

    Activa la entrada cuyo prefijo de url encaja mas largo, para que
    /negocio/facturas/ marque "Negocio" y no el panel, que cuelga de "/".
    """
    from django.urls import reverse

    entradas = [
        {
            "url": reverse(nombre),
            "etiqueta": etiqueta,
            "icono": icono,
            "movil": movil,
            "activa": False,
        }
        for nombre, etiqueta, icono, movil in NAVEGACION
    ]
    candidatas = [e for e in entradas if ruta.startswith(e["url"])]
    if candidatas:
        max(candidatas, key=lambda e: len(e["url"]))["activa"] = True
    return entradas


def desglosar_jefe(texto: str) -> dict | None:
    """Parte el jefe de rango en nombre, prueba y plazo.

    Viene sembrado como "El Cobro Pendiente - Los 2.000 EUR ... Plazo: 4 semanas."
    Devuelve None si el rango no tiene jefe.
    """
    texto = (texto or "").strip()
    if not texto:
        return None

    nombre, _, prueba = texto.partition("·")
    nombre, prueba = nombre.strip(), prueba.strip()
    if not prueba:
        nombre, prueba = texto.rstrip("."), ""

    plazo = ""
    cuerpo, separador, cola = prueba.rpartition("Plazo:")
    if separador:
        plazo = cola.strip(" .")
        prueba = cuerpo.strip()

    return {"nombre": nombre.rstrip("."), "prueba": prueba, "plazo": plazo}


def porcentaje(valor, objetivo) -> int:
    """Porcentaje recorrido hacia un objetivo, recortado a 0-100."""
    if not objetivo:
        return 0
    return max(0, min(100, round(float(valor) / float(objetivo) * 100)))


# --- Verificacion del ascenso de rango ---------------------------------------
#
# El rango no se regala con XP: cada uno se cierra cumpliendo su criterio medido
# contra los datos reales. Los medidores viven aqui y los criterios en
# `core/ranks.py`, para que las cifras no queden dispersas.


def total_cobrado() -> float:
    """EUR cobrados en total, de todas las facturas cobradas."""
    from django.db.models import Sum

    from business.models import Invoice

    return float(
        Invoice.objects.filter(cobrada=True).aggregate(t=Sum("importe"))["t"] or 0
    )


def contratos_recurrentes() -> int:
    """Clientes activos que aportan recurrente."""
    from business.models import Client

    return Client.objects.filter(estado=Client.Estado.ACTIVO, mrr__gt=0).count()


def recurrente_mensual() -> float:
    """EUR/mes recurrentes activos."""
    from business import services as business

    return float(business.recurrente_activo())


def casos_publicados() -> int:
    """Veces que se ha cerrado la mision de caso de estudio publicado."""
    from missions.models import MissionLog

    return MissionLog.objects.filter(
        completada=True, mission__titulo__startswith="M4"
    ).count()


def semanas_seguidas_con_pipeline(fecha=None) -> int:
    """Semanas consecutivas, hacia atras, con el pipeline activo.

    Cuenta contactos nuevos y toques de cada semana ISO cerrada. La semana en
    curso no cuenta: todavia puede completarse.
    """
    import datetime as dt

    from django.utils import timezone

    from business.models import Deal
    from core.ranks import CONTACTOS_PIPELINE_ACTIVO

    fecha = fecha or timezone.localdate()
    lunes_actual = fecha - dt.timedelta(days=fecha.weekday())

    semanas = 0
    for salto in range(1, 53):
        lunes = lunes_actual - dt.timedelta(weeks=salto)
        domingo = lunes + dt.timedelta(days=6)
        nuevos = Deal.objects.filter(fecha_primer_contacto__range=(lunes, domingo))
        tocados = Deal.objects.filter(ultimo_toque__range=(lunes, domingo))
        if nuevos.union(tocados).count() < CONTACTOS_PIPELINE_ACTIVO:
            break
        semanas += 1
    return semanas


def _media_mensual(meses: int, fecha=None) -> float:
    """Media de EUR cobrados por mes en los ultimos `meses` meses cerrados."""
    import datetime as dt

    from django.db.models import Sum
    from django.utils import timezone

    from business.models import Invoice

    fecha = fecha or timezone.localdate()
    primero_de_este_mes = fecha.replace(day=1)
    desde = primero_de_este_mes
    for _ in range(meses):
        desde = (desde - dt.timedelta(days=1)).replace(day=1)

    total = Invoice.objects.filter(
        cobrada=True, fecha_cobro__gte=desde, fecha_cobro__lt=primero_de_este_mes
    ).aggregate(t=Sum("importe"))["t"] or 0
    return float(total) / meses


def media_mensual_3m(fecha=None) -> float:
    return _media_mensual(3, fecha)


def media_mensual_6m(fecha=None) -> float:
    return _media_mensual(6, fecha)


def precio_minimo_aceptado() -> float:
    """El precio mas bajo que has aceptado en un proyecto no congelado."""
    from business.models import Project

    precios = Project.objects.exclude(estado=Project.Estado.CONGELADO).values_list(
        "precio", flat=True
    )
    return float(min(precios)) if precios else 0.0


def concentracion_maxima(fecha=None) -> float:
    """Porcentaje de lo cobrado este ano que aporta el cliente mas grande."""
    from django.db.models import Sum
    from django.utils import timezone

    from business.models import Invoice

    fecha = fecha or timezone.localdate()
    facturas = Invoice.objects.filter(cobrada=True, fecha_cobro__year=fecha.year)
    total = float(facturas.aggregate(t=Sum("importe"))["t"] or 0)
    if not total:
        return 0.0
    por_cliente = facturas.values("client").annotate(t=Sum("importe"))
    mayor = max(float(fila["t"]) for fila in por_cliente)
    return round(mayor / total * 100, 1)


def requisitos_de_ascenso(rank, fecha=None) -> list[dict]:
    """Los requisitos del rango con su valor actual y si estan cumplidos.

    Un requisito sin medidor no se puede comprobar con los datos del sistema:
    se devuelve como `medible=False` y cuenta como no cumplido.
    """
    from core.ranks import CRITERIOS, MENOS_ES_MEJOR

    requisitos = []
    for clave, texto, objetivo, medidor in CRITERIOS.get(rank.orden, ()):
        if medidor is None:
            requisitos.append(
                {
                    "clave": clave,
                    "texto": texto,
                    "objetivo": objetivo,
                    "actual": None,
                    "cumplido": False,
                    "medible": False,
                    "pct": 0,
                }
            )
            continue

        funcion = globals()[medidor]
        try:
            actual = funcion(fecha)
        except TypeError:
            actual = funcion()

        if clave in MENOS_ES_MEJOR:
            cumplido = actual <= objetivo
            pct = 100 if cumplido else 0
        else:
            cumplido = actual >= objetivo
            pct = porcentaje(actual, objetivo)

        requisitos.append(
            {
                "clave": clave,
                "texto": texto,
                "objetivo": objetivo,
                "actual": actual,
                "cumplido": cumplido,
                "medible": True,
                "pct": pct,
            }
        )
    return requisitos


def ascenso_disponible(rank, fecha=None) -> bool:
    """True si el rango cumple todos sus requisitos y puede cerrarse."""
    requisitos = requisitos_de_ascenso(rank, fecha)
    return bool(requisitos) and all(r["cumplido"] for r in requisitos)


def techo_de_nivel(perfil, nivel_por_xp: int, fecha=None) -> int:
    """El nivel se para en el techo del rango hasta cumplir su criterio.

    La XP sigue acumulandose: lo que no avanza es el nivel. En cuanto el
    criterio se cumple, el nivel salta de golpe a donde le corresponde.
    """
    rango = perfil.rango or rango_para_nivel(perfil.nivel)
    if rango is None or nivel_por_xp <= rango.nivel_max:
        return nivel_por_xp
    if ascenso_disponible(rango, fecha):
        return nivel_por_xp
    return rango.nivel_max


# --- La escalera: rangos y niveles -------------------------------------------


def escalera_de_rangos(nivel: int) -> list[dict]:
    """Los rangos con su estado respecto al nivel actual.

    Estado: "superado" si ya lo pasaste, "en_curso" el que contiene tu nivel y
    "bloqueado" los que quedan. El porcentaje es lo recorrido dentro del tramo
    de niveles del rango.
    """
    from .models import Rank

    escalera = []
    for rank in Rank.objects.all():
        if nivel > rank.nivel_max:
            estado, pct = "superado", 100
        elif nivel < rank.nivel_min:
            estado, pct = "bloqueado", 0
        else:
            estado = "en_curso"
            tramo = rank.nivel_max - rank.nivel_min + 1
            pct = porcentaje(nivel - rank.nivel_min + 1, tramo)
        requisitos = requisitos_de_ascenso(rank)
        escalera.append(
            {
                "rango": rank,
                "estado": estado,
                # La plantilla necesita un booleano suelto para el emblema.
                "bloqueado": estado == "bloqueado",
                "pct": pct,
                "jefe": desglosar_jefe(rank.jefe),
                "niveles": f"{rank.nivel_min}-{rank.nivel_max}",
                "requisitos": requisitos,
                "cumplidos": sum(1 for r in requisitos if r["cumplido"]),
                "ascenso_disponible": bool(requisitos)
                and all(r["cumplido"] for r in requisitos),
            }
        )
    return escalera


def escalera_de_niveles(nivel: int, xp_total: int) -> list[dict]:
    """Los 100 niveles agrupados por tramo de coste, con su estado.

    Cada tramo lleva lo que cuesta subir un nivel dentro de el; cada nivel, si
    esta superado, es el actual o sigue bloqueado.
    """
    tramos = []
    for minimo, maximo, coste in TRAMOS_XP:
        niveles = []
        for n in range(minimo, maximo + 1):
            if n < nivel:
                estado = "superado"
            elif n == nivel:
                estado = "actual"
            else:
                estado = "bloqueado"
            niveles.append({"nivel": n, "estado": estado})
        tramos.append(
            {
                "min": minimo,
                "max": maximo,
                "coste": coste,
                "niveles": niveles,
                "actual": minimo <= nivel <= maximo,
                "total_xp": coste * (maximo - minimo + 1),
            }
        )
    return tramos


def contexto_niveles() -> dict:
    """Todo lo que pinta la pantalla de rangos y niveles."""
    from .models import Profile

    perfil = Profile.get()
    rango = perfil.rango or rango_para_nivel(perfil.nivel)
    return {
        "perfil": perfil,
        "rango": rango,
        "jefe": desglosar_jefe(rango.jefe) if rango else None,
        "rangos": escalera_de_rangos(perfil.nivel),
        "tramos": escalera_de_niveles(perfil.nivel, perfil.xp_total),
        "xp_siguiente_nivel": xp_por_nivel(perfil.nivel),
        "nivel_maximo": NIVEL_MAXIMO,
    }


# --- Hoja de personaje -------------------------------------------------------

# Orden en que se pintan las categorias de atributos.
CATEGORIAS_ATRIBUTOS = ("NEGOCIO", "TECNICA", "PERSONAL", "SALUD")


# Estado de un atributo segun su valor. Los cortes son propios: el documento
# no los define, pero separan "esto tira", "esto se sostiene" y "esto te esta
# costando dinero", que es la lectura util de la hoja.
CORTE_SUBIENDO = 60
CORTE_ESTABLE = 40


def estado_de_atributo(valor: int) -> dict:
    """Etiqueta y color con los que se lee un atributo de un vistazo."""
    if valor >= CORTE_SUBIENDO:
        return {"clave": "subiendo", "etiqueta": "Subiendo", "acento": "ok"}
    if valor >= CORTE_ESTABLE:
        return {"clave": "estable", "etiqueta": "Estable", "acento": "warn"}
    return {"clave": "riesgo", "etiqueta": "En riesgo", "acento": "bad"}


def _fila_de_atributo(atributo) -> dict:
    """Un atributo con todo lo que hace falta para pintarlo: estado y palancas."""
    from missions.services import partir_titulo

    palancas = []
    for mision in atributo.misiones.filter(activa=True).order_by("tipo", "orden")[:4]:
        codigo, titulo = partir_titulo(mision.titulo)
        palancas.append({"codigo": codigo, "titulo": titulo, "pk": mision.pk})

    return {
        "atributo": atributo,
        "estado": estado_de_atributo(atributo.valor),
        "palancas": palancas,
    }


def hoja_de_personaje() -> dict:
    """Los quince atributos agrupados por categoria, con su media.

    El documento lee el perfil por sus extremos: los tres mas altos son tus
    puntos fuertes y los tres mas bajos, los agujeros que te hacen facturar a
    saltos. Se devuelven aparte para poder senalarlos.
    """
    from .models import Attribute, Profile, Rank

    perfil = Profile.get()
    rango = perfil.rango or rango_para_nivel(perfil.nivel)
    siguiente = (
        Rank.objects.filter(orden__gt=rango.orden).order_by("orden").first()
        if rango
        else None
    )
    base = {
        "perfil": perfil,
        "rango": rango,
        "siguiente_rango": siguiente,
        "jefe": desglosar_jefe(rango.jefe) if rango else None,
    }

    atributos = list(
        Attribute.objects.prefetch_related("misiones").all()
    )
    if not atributos:
        return {**base, "grupos": [], "media": 0, "fuertes": [], "agujeros": []}

    por_categoria = []
    for clave in CATEGORIAS_ATRIBUTOS:
        del_grupo = [a for a in atributos if a.categoria == clave]
        if not del_grupo:
            continue
        del_grupo.sort(key=lambda a: -a.valor)
        etiqueta = del_grupo[0].get_categoria_display()
        por_categoria.append(
            {
                "clave": clave,
                "nombre": etiqueta,
                "atributos": del_grupo,
                "filas": [_fila_de_atributo(a) for a in del_grupo],
                "media": round(sum(a.valor for a in del_grupo) / len(del_grupo)),
            }
        )

    ordenados = sorted(atributos, key=lambda a: -a.valor)
    return {
        **base,
        "grupos": por_categoria,
        "media": round(sum(a.valor for a in atributos) / len(atributos)),
        "fuertes": ordenados[:3],
        "agujeros": list(reversed(ordenados[-3:])),
    }


# --- Calibracion mensual -----------------------------------------------------
#
# Las tres preguntas de docs/sistema-v2.md, SS6, calculadas con los datos que el
# sistema ya tiene. La calibracion NO cambia nada sola: propone, y las decisiones
# se toman a mano. Un sistema que se recalibra solo deja de ser un espejo.

# Por encima de esta tasa de aceptacion, el precio esta bajo (docs SS6, punto 3).
TASA_ACEPTACION_ALTA = 0.8

# La revision de precio es trimestral, no mensual.
MESES_ENTRE_REVISIONES_DE_PRECIO = 3


def _limites_del_mes(fecha):
    """Primer dia de ese mes y primer dia del siguiente."""
    import datetime as dt

    primero = fecha.replace(day=1)
    if primero.month == 12:
        siguiente = primero.replace(year=primero.year + 1, month=1)
    else:
        siguiente = primero.replace(month=primero.month + 1)
    return primero, siguiente


def _mes_anterior(fecha):
    import datetime as dt

    primero, _ = _limites_del_mes(fecha)
    return primero - dt.timedelta(days=1)


def comparativa_mensual(fecha=None) -> dict:
    """Pregunta 1: la XP sube mientras el dinero no.

    Compara XP neta, euros cobrados y recurrente de este mes con el anterior.
    Si no hay mes anterior con datos, lo dice en vez de inventar una tendencia.
    """
    from django.db.models import Sum
    from django.utils import timezone

    from business.models import Invoice
    from progression.models import Categoria, XPEvent
    from review.models import WeeklyReview

    fecha = fecha or timezone.localdate()

    def _de(mes):
        desde, hasta = _limites_del_mes(mes)
        xp = XPEvent.objects.filter(fecha__gte=desde, fecha__lt=hasta).aggregate(
            t=Sum("xp_neto")
        )["t"] or 0
        soporte = XPEvent.objects.filter(
            fecha__gte=desde, fecha__lt=hasta, categoria=Categoria.SOPORTE
        ).aggregate(t=Sum("xp_neto"))["t"] or 0
        cobrado = Invoice.objects.filter(
            cobrada=True, fecha_cobro__gte=desde, fecha_cobro__lt=hasta
        ).aggregate(t=Sum("importe"))["t"] or 0
        revision = (
            WeeklyReview.objects.filter(fecha__gte=desde, fecha__lt=hasta)
            .order_by("-fecha")
            .first()
        )
        return {
            "xp": int(xp),
            "xp_soporte": int(soporte),
            "cobrado": float(cobrado),
            "recurrente": float(revision.m2_eur_recurrentes) if revision else None,
        }

    este = _de(fecha)
    anterior = _de(_mes_anterior(fecha))

    hay_con_que_comparar = anterior["xp"] > 0 or anterior["cobrado"] > 0
    subio_xp = este["xp"] > anterior["xp"]
    subio_dinero = este["cobrado"] > anterior["cobrado"]
    subio_recurrente = (
        este["recurrente"] is not None
        and anterior["recurrente"] is not None
        and este["recurrente"] > anterior["recurrente"]
    )

    return {
        "este": este,
        "anterior": anterior,
        "comparable": hay_con_que_comparar,
        # La senal del documento: XP arriba y dinero quieto.
        "alerta": hay_con_que_comparar and subio_xp and not (subio_dinero or subio_recurrente),
        "subio_xp": subio_xp,
        "subio_dinero": subio_dinero,
        "subio_recurrente": subio_recurrente,
    }


# "Dinero cobrado" es una tarifa por euro, no una accion que se haga o se deje
# de hacer: subirle la XP un 50% no significa nada. Queda fuera del repaso.
REGLAS_FUERA_DEL_REPASO = {"dinero-cobrado"}


def acciones_sin_usar() -> dict:
    """Pregunta 2: acciones de la tabla de XP que no has hecho ni una vez.

    El documento da dos salidas: borrarla porque es irrelevante, o subirle la XP
    un 50% porque es justo la que te cuesta.

    Con el historial vacio la pregunta no tiene sentido -saldrian todas- asi que
    se devuelve sin lista y marcada como no respondible todavia.
    """
    from progression.models import XPEvent, XPRule

    if not XPEvent.objects.exists():
        return {"hay_historial": False, "acciones": []}

    usados = set(XPEvent.objects.values_list("accion_slug", flat=True).distinct())
    acciones = [
        {"regla": regla, "xp_si_sube": int(round(regla.xp * 1.5))}
        for regla in XPRule.objects.filter(activa=True)
        .exclude(xp__lt=0)
        .exclude(accion_slug__in=REGLAS_FUERA_DEL_REPASO)
        .order_by("-xp")
        if regla.accion_slug not in usados
    ]
    return {"hay_historial": True, "acciones": acciones}


def tasa_de_aceptacion() -> dict:
    """Pregunta 3: si te aceptan mas de 8 de cada 10, tu precio es bajo.

    Se calcula sobre las oportunidades ya cerradas (ganadas frente a perdidas).
    Con menos de cinco cerradas la muestra no dice nada y se avisa.
    """
    from business.models import Deal

    ganados = Deal.objects.filter(estado=Deal.Estado.GANADO).count()
    perdidos = Deal.objects.filter(estado=Deal.Estado.PERDIDO).count()
    cerrados = ganados + perdidos
    tasa = ganados / cerrados if cerrados else 0.0

    return {
        "ganados": ganados,
        "perdidos": perdidos,
        "cerrados": cerrados,
        "tasa": round(tasa * 100),
        "fiable": cerrados >= 5,
        "alerta": cerrados >= 5 and tasa > TASA_ACEPTACION_ALTA,
        "umbral": int(TASA_ACEPTACION_ALTA * 100),
    }


def ajustar_atributo(slug: str, valor: int, nota: str, fecha=None):
    """Cambia el valor de un atributo y deja constancia del motivo.

    Es el unico camino para mover un atributo: escribe el valor y el registro
    historico en la misma transaccion, para que no puedan desincronizarse.
    """
    from django.db import transaction
    from django.utils import timezone

    from .models import Attribute, AttributeLog

    nota = (nota or "").strip()
    if not nota:
        raise ValueError("Escribe por que sube o baja. Sin motivo no se guarda.")
    if not 0 <= valor <= 100:
        raise ValueError("El valor de un atributo va de 0 a 100.")

    fecha = fecha or timezone.localdate()
    atributo = Attribute.objects.filter(slug=slug).first()
    if atributo is None:
        raise ValueError(f"No existe el atributo '{slug}'.")
    if atributo.valor == valor:
        raise ValueError(f"{atributo.nombre} ya vale {valor}.")

    with transaction.atomic():
        atributo.valor = valor
        atributo.save(update_fields=["valor"])
        AttributeLog.objects.create(
            attribute=atributo, fecha=fecha, valor=valor, nota=nota
        )
    return atributo


def contexto_calibracion(fecha=None) -> dict:
    """Todo lo que pinta la pantalla de calibracion."""
    from django.utils import timezone

    from .models import AttributeLog

    fecha = fecha or timezone.localdate()
    return {
        "hoy": fecha,
        "comparativa": comparativa_mensual(fecha),
        "sin_usar": acciones_sin_usar(),
        "aceptacion": tasa_de_aceptacion(),
        "hoja": hoja_de_personaje(),
        "historial": (
            AttributeLog.objects.select_related("attribute").order_by("-fecha", "-id")[:15]
        ),
    }


# --- Grafica de la tarifa efectiva ------------------------------------------
#
# Una muestra por semana de la ventana de 90 dias: cada punto es la tarifa
# efectiva que habia ese dia, medida igual que la cifra grande del panel.

MUESTRAS_TARIFA = 13
# Lienzo del SVG. Las coordenadas se calculan aqui para que la plantilla solo
# pinte; el SVG se estira al ancho de la tarjeta.
ANCHO_GRAFICA = 600
ALTO_GRAFICA = 120


def grafica_tarifa(fecha, objetivo) -> dict:
    """Serie, escala y variacion de la tarifa efectiva para el panel.

    Los puntos sin proyectos entregados en su ventana se saltan: no hay dato,
    y un cero pintaria una caida que no ha ocurrido.
    """
    import datetime as dt

    from business import services as business

    fechas = [
        fecha - dt.timedelta(weeks=MUESTRAS_TARIFA - 1 - i) for i in range(MUESTRAS_TARIFA)
    ]
    valores = [business.tarifa_efectiva_mes(f) for f in fechas]
    con_dato = [(i, float(v)) for i, v in enumerate(valores) if v is not None]

    # Techo de la escala en multiplos de 20, nunca por debajo de objetivo x 1,5.
    maximo = max([float(objetivo) * 1.5] + [v for _, v in con_dato])
    techo = int(-(-maximo // 20) * 20)
    marcas = [
        {"valor": v, "top": round((1 - v / techo) * 100, 1)}
        for v in (techo, round(techo * 2 / 3), round(techo / 3))
    ]

    puntos = [
        (
            round(i / (MUESTRAS_TARIFA - 1) * ANCHO_GRAFICA, 1),
            round((1 - v / techo) * ALTO_GRAFICA, 1),
        )
        for i, v in con_dato
    ]
    linea = " ".join(f"{x},{y}" for x, y in puntos)
    area = ""
    if len(puntos) >= 2:
        area = (
            f"M{puntos[0][0]},{ALTO_GRAFICA} L"
            + " L".join(f"{x},{y}" for x, y in puntos)
            + f" L{puntos[-1][0]},{ALTO_GRAFICA} Z"
        )

    actual = valores[-1]
    anterior = business.tarifa_efectiva_mes(fecha - dt.timedelta(days=business.VENTANA_TARIFA_DIAS))
    variacion = None
    if actual is not None and anterior:
        variacion = round((float(actual) - float(anterior)) / float(anterior) * 100)

    return {
        "linea": linea if len(puntos) >= 2 else "",
        "area": area,
        "ultimo": puntos[-1] if puntos else None,
        "marcas": marcas,
        "ancho": ANCHO_GRAFICA,
        "alto": ALTO_GRAFICA,
        "variacion": variacion,
        "variacion_abs": abs(variacion) if variacion is not None else None,
        # Barra del objetivo: la escala llega al techo de la grafica.
        "barra_pct": porcentaje(actual or 0, techo),
        "objetivo_pct": porcentaje(objetivo, techo),
    }


def contexto_panel(fecha=None, minimo: bool = False) -> dict:
    """Todo lo que pinta el panel principal, en una sola llamada."""
    from django.utils import timezone

    from business import services as business
    from missions import services as missions
    from progression import services as progression
    from review import services as review
    from wisdom import services as wisdom

    fecha = fecha or timezone.localdate()
    tarifa = business.tarifa_efectiva_mes(fecha)
    contexto = progression.resumen_progresion(fecha)
    perfil = contexto["perfil"]
    # El perfil puede no tener rango asignado a mano: se deduce del nivel.
    rango = perfil.rango or rango_para_nivel(perfil.nivel)
    recurrente = business.recurrente_activo()
    # El objetivo de recurrente sube con el rango: lo manda business, que es
    # donde vive el umbral. Aqui no se duplica la cifra.
    objetivo_recurrente = business.objetivo_recurrente(rango)
    objetivo_tarifa = review.OBJETIVOS["m7_tarifa_efectiva"]
    contexto.update(
        {
            "hoy": fecha,
            "rango": rango,
            "jefe": desglosar_jefe(rango.jefe) if rango else None,
            "misiones": missions.panel_de_misiones(fecha, minimo=minimo),
            "alertas": business.alertas(fecha),
            "consejo": wisdom.maxima_contextual(fecha),
            "recompensas": progression.panel_de_recompensas(fecha),
            "aviso_revision": review.aviso_revision_pendiente(fecha),
            "bloqueo": progression.bloqueo_tecnico_activo(fecha),
            "recurrente": recurrente,
            "objetivo_recurrente": objetivo_recurrente,
            "recurrente_pct": porcentaje(recurrente, objetivo_recurrente),
            "tarifa_efectiva": tarifa,
            "hay_horas": tarifa is not None,
            "objetivo_tarifa": objetivo_tarifa,
            "grafica_tarifa": grafica_tarifa(fecha, objetivo_tarifa),
            # El jefe se vence con los mismos numeros que cierran el rango.
            "requisitos_jefe": requisitos_de_ascenso(rango, fecha) if rango else [],
            "embudo": business.embudo_pipeline(),
        }
    )
    return contexto


# --- Captura rapida ----------------------------------------------------------
#
# Cuatro cosas que uno quiere anotar de pie y en diez segundos: un contacto
# nuevo, un toque a algo que ya esta en el pipeline, una idea suelta y un
# entreno. Cada una acaba en el servicio de su dominio; aqui solo se reparte.

TIPOS_DE_CAPTURA = {
    "contacto": {
        "etiqueta": "Contacto",
        "icono": "negocio",
        "acento": "xp",
        "ayuda": "Alguien nuevo en el pipeline. Cuenta como acción comercial del día.",
    },
    "toque": {
        "etiqueta": "Toque",
        "icono": "fuego",
        "acento": "warn",
        "ayuda": "Seguimiento de algo que ya está abierto.",
    },
    "nota": {
        "etiqueta": "Nota",
        "icono": "cuaderno",
        "acento": "ink",
        "ayuda": "Lo que se te acaba de ocurrir. No puntúa.",
    },
    "entreno": {
        "etiqueta": "Entreno",
        "icono": "rayo",
        "acento": "ok",
        "ayuda": "Sesión hecha. 20 XP, con tope de 80 a la semana.",
    },
}

TIPO_DE_CAPTURA_POR_DEFECTO = "contacto"


def _capturar_contacto(datos) -> str:
    from business.models import Deal
    from business.services import toque_rapido

    negocio = (datos.get("negocio") or "").strip()
    if not negocio:
        raise ValueError("Escribe al menos el nombre del negocio.")

    deal = Deal.objects.create(
        negocio=negocio,
        contacto=(datos.get("contacto") or "").strip(),
        canal=(datos.get("canal") or "").strip(),
        proximo_paso=(datos.get("proximo_paso") or "").strip(),
    )
    toque_rapido(deal)
    return f"{negocio} entra en el pipeline. Cuenta como acción comercial de hoy."


def _capturar_toque(datos) -> str:
    from business.models import Deal
    from business.services import toque_rapido

    deal = Deal.objects.filter(pk=datos.get("deal") or 0).first()
    if deal is None:
        raise ValueError("Elige a quién has tocado.")

    paso = (datos.get("proximo_paso") or "").strip()
    if paso:
        deal.proximo_paso = paso
        deal.save(update_fields=["proximo_paso"])

    toque_rapido(deal)
    return f"Toque anotado en {deal.negocio}."


def _capturar_nota(datos) -> str:
    from notebook.services import crear_nota

    nota = crear_nota(datos.get("contenido", ""), titulo=datos.get("titulo", ""))
    if nota is None:
        raise ValueError("Escribe algo antes de guardar.")
    return "Apuntado en el cuaderno."


def _capturar_entreno(datos) -> str:
    from django.utils import timezone

    from progression.services import registrar_accion
    from review.models import HealthLog

    tipo = (datos.get("tipo_entreno") or "").strip()
    if not tipo:
        raise ValueError("¿Qué has entrenado? Fuerza, Muay Thai, jiu-jitsu…")

    hoy = timezone.localdate()
    registro, _ = HealthLog.objects.get_or_create(fecha=hoy)
    registro.entreno = True
    registro.tipo_entreno = tipo
    registro.save(update_fields=["entreno", "tipo_entreno"])

    evento = registrar_accion("entreno", f"Entreno: {tipo}")
    if evento.xp_neto:
        return f"{tipo} anotado. +{evento.xp_neto} XP."
    return f"{tipo} anotado. Esta semana ya has llegado al tope de entrenos."


CAPTURADORES = {
    "contacto": _capturar_contacto,
    "toque": _capturar_toque,
    "nota": _capturar_nota,
    "entreno": _capturar_entreno,
}


def capturar(tipo: str, datos) -> str:
    """Ejecuta una captura rapida. Devuelve el mensaje de confirmacion.

    Lanza ValueError con un texto que se puede enseñar tal cual si falta algo.
    """
    capturador = CAPTURADORES.get(tipo)
    if capturador is None:
        raise ValueError("Ese tipo de captura no existe.")
    return capturador(datos)


def contexto_captura(tipo: str) -> dict:
    """Lo que necesita pintar el formulario de captura."""
    from business.models import Deal

    return {
        "tipos": TIPOS_DE_CAPTURA,
        "tipo": tipo,
        "abiertos": Deal.objects.filter(estado__in=Deal.ESTADOS_ABIERTOS).order_by(
            "ultimo_toque", "negocio"
        )[:15],
    }


# --- Emblemas de rango -------------------------------------------------------
#
# Un .webp por rango en static/img/rangos/rango-<orden>.webp. Se comprueba que
# el fichero exista antes de devolverlo: en produccion {% static %} revienta
# con un fichero ausente, porque el manifiesto no lo encuentra.

_EMBLEMAS_DISPONIBLES: set[int] | None = None


def _emblemas_disponibles() -> set[int]:
    global _EMBLEMAS_DISPONIBLES
    if _EMBLEMAS_DISPONIBLES is None:
        from django.contrib.staticfiles import finders

        encontrados = set()
        for orden in range(1, 21):
            if finders.find(f"img/rangos/rango-{orden}.webp"):
                encontrados.add(orden)
        _EMBLEMAS_DISPONIBLES = encontrados
    return _EMBLEMAS_DISPONIBLES


def emblema_de_rango(orden: int) -> str:
    """Ruta estatica del emblema de ese rango, o "" si no hay imagen."""
    if orden in _emblemas_disponibles():
        return f"img/rangos/rango-{orden}.webp"
    return ""
