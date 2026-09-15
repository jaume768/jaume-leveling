from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from business.models import Client, Deal, Invoice
from core.models import Attribute, Profile
from core import services as core_services


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name",
    [
        "core:index",
        "missions:index",
        "progression:index",
        "business:index",
        "review:index",
        "wisdom:index",
    ],
)
def test_las_secciones_responden(client, name):
    # business:index redirige al pipeline, de ahi el follow.
    assert client.get(reverse(name), follow=True).status_code == 200


@pytest.mark.django_db
class TestProfile:
    def test_get_crea_el_perfil_una_sola_vez(self):
        primero = Profile.get()
        assert Profile.get().pk == primero.pk
        assert Profile.objects.count() == 1

    def test_no_se_puede_crear_un_segundo_perfil(self):
        primero = Profile.get()
        Profile.objects.create(nivel=10)
        assert Profile.objects.count() == 1
        assert Profile.objects.first().pk == primero.pk

    def test_progreso_de_nivel_en_el_tramo_41_60(self):
        # Tramo 41-60: 2.000 XP por nivel (docs/sistema-v2.md, §6).
        perfil = Profile.get()
        assert perfil.xp_para_siguiente_nivel == 2000
        assert perfil.progreso_nivel_pct == 0.0

        perfil.xp_total += 500
        assert perfil.xp_en_nivel == 500
        assert perfil.xp_para_siguiente_nivel == 1500
        assert perfil.progreso_nivel_pct == 25.0


@pytest.mark.django_db
class TestFacturas:
    @pytest.fixture
    def cliente(self):
        return Client.objects.create(nombre="Felycampo", slug="felycampo")

    def _factura(self, cliente, dias_desde_vencimiento, **extra):
        hoy = timezone.localdate()
        return Invoice.objects.create(
            client=cliente,
            concepto="Proyecto",
            importe=2000,
            fecha_emision=hoy - timedelta(days=dias_desde_vencimiento + 30),
            vencimiento=hoy - timedelta(days=dias_desde_vencimiento),
            **extra,
        )

    def test_dias_vencida_cuenta_el_retraso(self, cliente):
        assert self._factura(cliente, 18).dias_vencida == 18

    def test_una_factura_en_plazo_no_esta_vencida(self, cliente):
        assert self._factura(cliente, -5).dias_vencida == 0

    def test_una_factura_cobrada_nunca_esta_vencida(self, cliente):
        factura = self._factura(cliente, 40, cobrada=True, fecha_cobro=timezone.localdate())
        assert factura.dias_vencida == 0
        assert factura.hay_que_reclamar is False

    def test_hay_que_reclamar_al_dia_15(self, cliente):
        assert self._factura(cliente, 14).hay_que_reclamar is False
        assert self._factura(cliente, 15).hay_que_reclamar is True


@pytest.mark.django_db
class TestPipeline:
    def _deal(self, **extra):
        hoy = timezone.localdate()
        datos = {
            "negocio": "Gimnasio",
            "fecha_primer_contacto": hoy - timedelta(days=20),
            "ultimo_toque": hoy - timedelta(days=9),
        }
        datos.update(extra)
        return Deal.objects.create(**datos)

    def test_dias_sin_toque(self):
        assert self._deal().dias_sin_toque == 9

    def test_sin_toque_cuenta_desde_el_primer_contacto(self):
        assert self._deal(ultimo_toque=None).dias_sin_toque == 20

    def test_una_oportunidad_cerrada_no_cuenta_dias(self):
        assert self._deal(estado=Deal.Estado.PERDIDO).dias_sin_toque is None
        assert self._deal(estado=Deal.Estado.GANADO).dias_sin_toque is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "ruta",
    [
        "core_profile",
        "core_rank",
        "core_attribute",
        "core_attributelog",
        "missions_mission",
        "missions_missionlog",
        "progression_xprule",
        "progression_xpevent",
        "progression_penalty",
        "progression_reward",
        "business_client",
        "business_deal",
        "business_invoice",
        "business_project",
        "review_weeklyreview",
        "review_healthlog",
        "wisdom_maxim",
        "wisdom_systemprompt",
        "wisdom_advicesession",
    ],
)
def test_el_admin_lista_todos_los_modelos(client, ruta):
    get_user_model().objects.create_superuser("jaume", "jaume@example.com", "x")
    client.login(username="jaume", password="x")
    assert client.get(reverse(f"admin:{ruta}_changelist")).status_code == 200


# --- Presentacion: jefe de rango, porcentajes y navegacion -------------------


@pytest.mark.parametrize(
    "texto, esperado",
    [
        (
            "El Cobro Pendiente · Los 2.000 EUR en tu cuenta y un mantenimiento "
            "firmado. Plazo: 4 semanas.",
            {
                "nombre": "El Cobro Pendiente",
                "prueba": "Los 2.000 EUR en tu cuenta y un mantenimiento firmado.",
                "plazo": "4 semanas",
            },
        ),
        # Sin plazo: la prueba se queda entera.
        (
            "El Suelo · Rechazar un proyecto de 900 EUR teniendo el mes vacio.",
            {
                "nombre": "El Suelo",
                "prueba": "Rechazar un proyecto de 900 EUR teniendo el mes vacio.",
                "plazo": "",
            },
        ),
        # Sin separador: todo es nombre.
        (
            "El Primer Contrato sin Ti.",
            {"nombre": "El Primer Contrato sin Ti", "prueba": "", "plazo": ""},
        ),
    ],
)
def test_desglosar_jefe_separa_nombre_prueba_y_plazo(texto, esperado):
    assert core_services.desglosar_jefe(texto) == esperado


def test_desglosar_jefe_sin_jefe_devuelve_nada():
    assert core_services.desglosar_jefe("") is None
    assert core_services.desglosar_jefe(None) is None


@pytest.mark.parametrize(
    "valor, objetivo, esperado",
    [
        (0, 450, 0),
        (225, 450, 50),
        (450, 450, 100),
        (900, 450, 100),  # no se pasa de 100
        (-50, 450, 0),  # ni baja de 0
        (100, 0, 0),  # sin objetivo no hay porcentaje
    ],
)
def test_porcentaje_se_recorta_entre_0_y_100(valor, objetivo, esperado):
    assert core_services.porcentaje(valor, objetivo) == esperado


@pytest.mark.django_db
def test_navegacion_marca_la_entrada_mas_especifica():
    entradas = {e["etiqueta"]: e for e in core_services.navegacion("/negocio/facturas/")}
    assert entradas["Negocio"]["activa"] is True
    # El panel cuelga de "/" y no debe activarse con cualquier ruta.
    assert entradas["Panel"]["activa"] is False


@pytest.mark.django_db
def test_navegacion_activa_el_panel_en_la_raiz():
    entradas = {e["etiqueta"]: e for e in core_services.navegacion("/")}
    assert entradas["Panel"]["activa"] is True


# --- La escalera de rangos y niveles -----------------------------------------


@pytest.mark.django_db
def test_escalera_de_rangos_marca_superado_en_curso_y_bloqueado():
    estados = {
        paso["rango"].nombre: paso["estado"]
        for paso in core_services.escalera_de_rangos(45)
    }
    # El nivel 45 cae dentro de Operador (21-50).
    assert estados["Aspirante"] == "superado"
    assert estados["Operador"] == "en_curso"
    assert estados["Especialista"] == "bloqueado"


@pytest.mark.django_db
def test_el_rango_en_curso_lleva_su_jefe_desglosado():
    en_curso = next(
        paso for paso in core_services.escalera_de_rangos(45) if paso["estado"] == "en_curso"
    )
    assert en_curso["jefe"]["nombre"] == "El Cobro Pendiente"
    assert en_curso["jefe"]["plazo"] == "4 semanas"
    assert 0 < en_curso["pct"] <= 100


def test_escalera_de_niveles_cubre_los_cien_niveles():
    tramos = core_services.escalera_de_niveles(45, 38_000)

    assert sum(len(t["niveles"]) for t in tramos) == core_services.NIVEL_MAXIMO

    # Solo un tramo es el actual, y es el que contiene el nivel 45.
    actuales = [t for t in tramos if t["actual"]]
    assert len(actuales) == 1
    assert (actuales[0]["min"], actuales[0]["max"], actuales[0]["coste"]) == (41, 60, 2_000)

    todos = [n for t in tramos for n in t["niveles"]]
    assert [n["nivel"] for n in todos if n["estado"] == "actual"] == [45]
    assert all(n["estado"] == "superado" for n in todos if n["nivel"] < 45)
    assert all(n["estado"] == "bloqueado" for n in todos if n["nivel"] > 45)


@pytest.mark.django_db
def test_la_pantalla_de_niveles_responde(client):
    respuesta = client.get(reverse("core:niveles"))

    assert respuesta.status_code == 200
    assert "El Cobro Pendiente".encode() in respuesta.content
    assert "Estás aquí".encode() in respuesta.content


# --- Verificacion del ascenso de rango ---------------------------------------


@pytest.mark.django_db
class TestAscensoDeRango:
    """El rango se cierra con numeros. La XP sola no basta."""

    def _operador(self):
        from core.models import Rank

        return Rank.objects.get(orden=2)

    def test_sin_datos_no_hay_ascenso(self):
        assert core_services.ascenso_disponible(self._operador()) is False

    def test_los_requisitos_dicen_cuanto_llevas(self):
        requisitos = {r["clave"]: r for r in core_services.requisitos_de_ascenso(self._operador())}

        assert set(requisitos) == {"cobrado", "recurrente", "casos", "pipeline"}
        assert requisitos["cobrado"]["objetivo"] == 2_000
        assert requisitos["cobrado"]["actual"] == 0
        assert requisitos["cobrado"]["cumplido"] is False

    def test_la_xp_sola_no_sube_de_rango(self):
        from progression import services as progression

        perfil = Profile.objects.first() or Profile.get()
        perfil.nivel = 45
        perfil.xp_total = core_services.xp_acumulada_hasta_nivel(45)
        perfil.rango = self._operador()
        perfil.save()

        # XP de sobra para llegar al nivel 54, pero sin cumplir nada. Se pone
        # directa porque el techo semanal de 1.000 XP no deja concederla de
        # golpe; lo que se prueba aqui es el techo de rango, no el semanal.
        perfil.xp_total = core_services.xp_acumulada_hasta_nivel(54)
        perfil.save()
        progression.registrar_xp(
            "regalo", xp=1, descripcion="prueba", aplicar_racha=False
        )

        perfil = Profile.get()
        assert perfil.nivel == 50  # techo del rango Operador
        assert perfil.rango.orden == 2
        # La XP no se ha perdido: sigue acumulada esperando el ascenso.
        assert perfil.xp_total >= core_services.xp_acumulada_hasta_nivel(54)

    def test_cumpliendo_el_criterio_el_nivel_salta(self):
        import datetime as dt

        from business.models import Client, Deal, Invoice
        from missions.models import Mission, MissionLog
        from progression import services as progression

        hoy = timezone.localdate()
        cliente = Client.objects.create(
            nombre="Felycampo", slug="felycampo", mrr=139, estado=Client.Estado.ACTIVO
        )
        Invoice.objects.create(
            client=cliente, concepto="Web", importe=2_500,
            vencimiento=hoy, cobrada=True, fecha_cobro=hoy,
        )
        caso = Mission.objects.create(
            titulo="M4 · 1 caso publicado", tipo=Mission.Tipo.MENSUAL,
            definicion_terminada="Publicado", xp=150,
        )
        for dia in range(2):
            MissionLog.objects.create(
                mission=caso, fecha=hoy - dt.timedelta(days=dia * 40), completada=True
            )
        # Cuatro semanas cerradas con 6 contactos cada una.
        lunes_actual = hoy - dt.timedelta(days=hoy.weekday())
        for semana in range(1, 5):
            lunes = lunes_actual - dt.timedelta(weeks=semana)
            for i in range(6):
                Deal.objects.create(
                    negocio=f"s{semana}-{i}", fecha_primer_contacto=lunes
                )

        operador = self._operador()
        assert core_services.ascenso_disponible(operador) is True

        perfil = Profile.get()
        perfil.nivel = 50
        perfil.xp_total = core_services.xp_acumulada_hasta_nivel(54)
        perfil.rango = operador
        perfil.save()

        progression.registrar_xp("regalo", xp=1, descripcion="prueba", aplicar_racha=False)

        perfil = Profile.get()
        assert perfil.nivel == 54
        assert perfil.rango.orden == 3  # Especialista


@pytest.mark.django_db
def test_la_pantalla_de_niveles_muestra_el_criterio(client):
    respuesta = client.get(reverse("core:niveles"))

    assert "Se asciende con".encode() in respuesta.content
    assert "2.000 € cobrados".encode() in respuesta.content
    assert "el nivel se queda en el 50".encode() in respuesta.content



# --- Hoja de personaje -------------------------------------------------------


@pytest.mark.django_db
class TestHojaDePersonaje:
    def test_los_quince_atributos_estan_sembrados(self):
        from core.models import Attribute

        assert Attribute.objects.count() == 15

    def test_la_hoja_agrupa_y_calcula_la_media(self):
        hoja = core_services.hoja_de_personaje()

        assert [g["clave"] for g in hoja["grupos"]] == [
            "NEGOCIO", "TECNICA", "PERSONAL", "SALUD"
        ]
        assert 0 < hoja["media"] <= 100

    def test_senala_los_tres_fuertes_y_los_tres_agujeros(self):
        hoja = core_services.hoja_de_personaje()

        # Del documento: relaciones 72, salud 68 arriba; organizacion 25 abajo.
        assert hoja["fuertes"][0].slug == "relaciones"
        assert hoja["agujeros"][0].slug == "organizacion"
        assert [a.slug for a in hoja["agujeros"]] == [
            "organizacion", "producto", "red-profesional"
        ]

    def test_la_pantalla_responde(self, client):
        respuesta = client.get(reverse("core:personaje"))

        assert respuesta.status_code == 200
        assert "Red profesional".encode() in respuesta.content
        assert "15 dueños de negocio".encode() in respuesta.content



# --- Calibracion mensual -----------------------------------------------------


@pytest.mark.django_db
class TestAjustarAtributo:
    """Mover un atributo escribe valor e historial a la vez, o no escribe nada."""

    def test_sube_el_valor_y_deja_constancia(self):
        from core.models import AttributeLog

        core_services.ajustar_atributo(
            "organizacion", 35, "8 revisiones semanales seguidas"
        )

        atributo = Attribute.objects.get(slug="organizacion")
        log = AttributeLog.objects.get(attribute=atributo)
        assert atributo.valor == 35
        assert log.valor == 35
        assert log.nota == "8 revisiones semanales seguidas"

    def test_sin_motivo_no_se_guarda(self):
        from core.models import AttributeLog

        with pytest.raises(ValueError):
            core_services.ajustar_atributo("organizacion", 35, "   ")

        assert Attribute.objects.get(slug="organizacion").valor == 25
        assert not AttributeLog.objects.exists()

    def test_rechaza_valores_fuera_de_rango(self):
        with pytest.raises(ValueError):
            core_services.ajustar_atributo("organizacion", 140, "me vengo arriba")

    def test_rechaza_el_mismo_valor(self):
        with pytest.raises(ValueError):
            core_services.ajustar_atributo("organizacion", 25, "sin cambio")

    def test_rechaza_un_atributo_inexistente(self):
        with pytest.raises(ValueError):
            core_services.ajustar_atributo("telequinesis", 50, "ojalá")


@pytest.mark.django_db
class TestPreguntasDeCalibracion:
    def test_sin_historial_la_pregunta_2_no_se_responde(self):
        resultado = core_services.acciones_sin_usar()

        assert resultado["hay_historial"] is False
        assert resultado["acciones"] == []

    def test_con_historial_lista_las_que_faltan(self):
        from progression import services as progression

        progression.registrar_accion("peticion-referido", "Referido a Ana")
        resultado = core_services.acciones_sin_usar()

        assert resultado["hay_historial"] is True
        usadas = [i["regla"].accion_slug for i in resultado["acciones"]]
        assert "peticion-referido" not in usadas
        assert "testimonio-o-caso" in usadas
        # Dinero cobrado es una tarifa por euro, no una accion del repaso.
        assert "dinero-cobrado" not in usadas

    def test_la_propuesta_de_subida_es_un_50_por_ciento(self):
        from progression import services as progression

        progression.registrar_accion("peticion-referido", "Referido a Ana")
        testimonio = next(
            i for i in core_services.acciones_sin_usar()["acciones"]
            if i["regla"].accion_slug == "testimonio-o-caso"
        )
        assert testimonio["regla"].xp == 100
        assert testimonio["xp_si_sube"] == 150

    def test_la_tasa_de_aceptacion_avisa_de_que_no_es_fiable(self):
        from business.models import Deal

        Deal.objects.create(negocio="uno", estado=Deal.Estado.GANADO)
        resultado = core_services.tasa_de_aceptacion()

        assert resultado["fiable"] is False
        assert resultado["alerta"] is False

    def test_aceptar_mas_de_8_de_cada_10_dispara_el_aviso(self):
        from business.models import Deal

        for i in range(9):
            Deal.objects.create(negocio=f"ganado {i}", estado=Deal.Estado.GANADO)
        Deal.objects.create(negocio="perdido", estado=Deal.Estado.PERDIDO)

        resultado = core_services.tasa_de_aceptacion()
        assert resultado["tasa"] == 90
        assert resultado["fiable"] is True
        assert resultado["alerta"] is True

    def test_sin_mes_anterior_no_se_inventa_tendencia(self):
        comparativa = core_services.comparativa_mensual()

        assert comparativa["comparable"] is False
        assert comparativa["alerta"] is False


@pytest.mark.django_db
class TestPantallaDeCalibracion:
    def test_responde(self, client):
        respuesta = client.get(reverse("core:calibracion"))

        assert respuesta.status_code == 200
        assert "Calibración mensual".encode() in respuesta.content
        assert "Red profesional".encode() in respuesta.content

    def test_el_post_sube_el_atributo(self, client):
        respuesta = client.post(
            reverse("core:calibracion"),
            {"slug": "producto", "valor": "38", "nota": "Paquete vendido dos veces"},
        )

        assert respuesta.status_code == 200
        assert "Producto queda en 38".encode() in respuesta.content
        assert Attribute.objects.get(slug="producto").valor == 38

    def test_el_post_sin_motivo_devuelve_el_error(self, client):
        respuesta = client.post(
            reverse("core:calibracion"),
            {"slug": "producto", "valor": "38", "nota": ""},
        )

        assert "Sin motivo no se guarda".encode() in respuesta.content
        assert Attribute.objects.get(slug="producto").valor == 28


@pytest.mark.django_db
class TestRetratoDelPersonaje:
    def test_los_cortes_de_estado(self):
        from core.services import estado_de_atributo

        assert estado_de_atributo(72)["clave"] == "subiendo"
        assert estado_de_atributo(60)["clave"] == "subiendo"
        assert estado_de_atributo(59)["clave"] == "estable"
        assert estado_de_atributo(40)["clave"] == "estable"
        assert estado_de_atributo(39)["clave"] == "riesgo"
        assert estado_de_atributo(0)["clave"] == "riesgo"

    def test_trae_el_rango_actual_y_el_siguiente(self):
        from core import services

        hoja = services.hoja_de_personaje()
        assert hoja["rango"].nombre == "Operador"
        assert hoja["siguiente_rango"].nombre == "Especialista"

    def test_cada_atributo_lleva_estado_y_palancas(self):
        from core import services

        filas = [f for g in services.hoja_de_personaje()["grupos"] for f in g["filas"]]
        assert filas
        for fila in filas:
            assert fila["estado"]["acento"] in {"ok", "warn", "bad"}
            for palanca in fila["palancas"]:
                assert palanca["titulo"]

    def test_las_palancas_son_las_misiones_del_atributo(self):
        from core import services
        from core.models import Attribute

        finanzas = Attribute.objects.get(nombre="Finanzas")
        fila = next(
            f
            for g in services.hoja_de_personaje()["grupos"]
            for f in g["filas"]
            if f["atributo"].pk == finanzas.pk
        )
        codigos = [p["codigo"] for p in fila["palancas"]]
        assert "M3" in codigos

    def test_la_vista_pinta_el_retrato_y_los_quince_atributos(self, client):
        from core.models import Attribute

        respuesta = client.get(reverse("core:personaje"))
        contenido = respuesta.content.decode()
        assert respuesta.status_code == 200
        assert "personaje.webp" in contenido
        assert "personaje-mini.webp" in contenido
        assert contenido.count("Siguiente +10") >= 1
        for atributo in Attribute.objects.all():
            assert atributo.nombre in contenido

    def test_las_clases_de_color_van_literales(self, client):
        """Tailwind rastrea texto: una clase construida con {{ }} no se genera."""
        contenido = client.get(reverse("core:personaje")).content.decode()
        assert "bar-fill-{{" not in contenido
        assert "acento-{{" not in contenido
        assert "pill-{{" not in contenido


class TestComentariosDeLasPlantillas:
    """Un {# ... #} solo vale para una línea.

    Si abre en una línea y cierra en otra, Django no lo trata como comentario:
    lo imprime en la página. Ya ha pasado dos veces, así que queda vigilado.
    """

    @staticmethod
    def _plantillas():
        from pathlib import Path

        raiz = Path(__file__).resolve().parent.parent
        for ruta in raiz.rglob("*.html"):
            if not any(p in ruta.parts for p in (".git", "staticfiles", ".venv")):
                yield ruta

    def test_ningun_comentario_abarca_varias_lineas(self):
        import re

        malos = []
        for ruta in self._plantillas():
            texto = ruta.read_text()
            for marca in re.finditer(r"\{#", texto):
                resto = texto[marca.start():]
                cierre = resto.find("#}")
                if cierre == -1 or "\n" in resto[:cierre]:
                    linea = texto[: marca.start()].count("\n") + 1
                    malos.append(f"{ruta.name}:{linea}")

        assert not malos, (
            "Estos comentarios se imprimen en la página; usa {% comment %} "
            f"o una sola línea: {malos}"
        )


@pytest.mark.django_db
class TestCapturaRapida:
    """Cuatro cosas que se anotan de pie, sin cambiar de pantalla."""

    def test_un_contacto_entra_en_el_pipeline_y_cuenta_como_accion(self, client):
        from business.models import Deal
        from missions.models import MissionLog

        antes = Profile.get().xp_total
        respuesta = client.post(
            reverse("core:captura"),
            {"tipo": "contacto", "negocio": "Gimnasio Palma", "canal": "presencial"},
        )

        assert respuesta.status_code == 200
        deal = Deal.objects.get(negocio="Gimnasio Palma")
        assert deal.ultimo_toque == timezone.localdate()
        assert MissionLog.objects.filter(
            completada=True, mission__cuenta_para_racha=True
        ).exists()
        assert Profile.get().xp_total > antes

    def test_un_contacto_sin_nombre_no_se_guarda(self, client):
        from business.models import Deal

        respuesta = client.post(reverse("core:captura"), {"tipo": "contacto", "negocio": " "})
        assert "nombre del negocio".encode() in respuesta.content
        assert Deal.objects.count() == 0

    def test_una_nota_va_al_cuaderno(self, client):
        from notebook.models import Note

        client.post(reverse("core:captura"), {"tipo": "nota", "contenido": "Subir a 1.800 €"})
        assert Note.objects.get().contenido == "Subir a 1.800 €"

    def test_un_entreno_puntua_y_queda_en_el_registro_de_salud(self, client):
        from review.models import HealthLog

        antes = Profile.get().xp_total
        client.post(reverse("core:captura"), {"tipo": "entreno", "tipo_entreno": "Muay Thai"})

        registro = HealthLog.objects.get(fecha=timezone.localdate())
        assert registro.entreno is True
        assert registro.tipo_entreno == "Muay Thai"
        assert Profile.get().xp_total == antes + 20

    def test_un_toque_actualiza_la_oportunidad(self, client):
        from business.models import Deal

        deal = Deal.objects.create(negocio="Gruas Perelló")
        client.post(
            reverse("core:captura"),
            {"tipo": "toque", "deal": deal.pk, "proximo_paso": "Llamar el jueves"},
        )

        deal.refresh_from_db()
        assert deal.ultimo_toque == timezone.localdate()
        assert deal.proximo_paso == "Llamar el jueves"

    def test_recuerda_el_ultimo_tipo_usado(self, client):
        client.post(reverse("core:captura"), {"tipo": "nota", "contenido": "algo"})

        respuesta = client.get(reverse("core:captura"))
        assert respuesta.context["tipo"] == "nota"

    def test_un_fallo_no_cambia_el_tipo_recordado(self, client):
        client.post(reverse("core:captura"), {"tipo": "nota", "contenido": "algo"})
        client.post(reverse("core:captura"), {"tipo": "entreno", "tipo_entreno": " "})

        assert client.get(reverse("core:captura")).context["tipo"] == "nota"

    def test_un_tipo_inventado_cae_en_el_de_por_defecto(self, client):
        respuesta = client.get(reverse("core:captura"), {"tipo": "inventado"})
        assert respuesta.context["tipo"] == "contacto"

    def test_el_boton_flotante_esta_en_todas_las_paginas(self, client):
        for nombre in ("core:index", "core:personaje", "notebook:index", "business:pipeline"):
            contenido = client.get(reverse(nombre)).content.decode()
            assert 'class="fab"' in contenido, nombre
            assert contenido.count('id="modal"') == 1, nombre


@pytest.mark.django_db
class TestEmblemasDeRango:
    """Las insignias de rango, atadas al orden y no al nombre."""

    def test_cada_rango_tiene_su_emblema(self):
        from core.models import Rank

        for rango in Rank.objects.all():
            assert rango.emblema == f"img/rangos/rango-{rango.orden}.webp"

    def test_renombrar_un_rango_no_le_quita_la_insignia(self):
        from core.models import Rank

        rango = Rank.objects.get(orden=2)
        rango.nombre = "Otro nombre"
        rango.save()
        assert rango.emblema == "img/rangos/rango-2.webp"

    def test_un_rango_sin_imagen_no_devuelve_ruta(self):
        from core.services import emblema_de_rango

        assert emblema_de_rango(99) == ""

    def test_el_panel_muestra_el_emblema_del_rango_actual(self, client):
        contenido = client.get(reverse("core:index")).content.decode()
        assert "rango-2" in contenido
        assert "Emblema del rango Operador" in contenido

    def test_el_personaje_muestra_el_actual_y_el_siguiente_apagado(self, client):
        contenido = client.get(reverse("core:personaje")).content.decode()
        assert "rango-2" in contenido
        assert "rango-3" in contenido
        assert "emblema-off" in contenido

    def test_la_escalera_muestra_los_seis(self, client):
        contenido = client.get(reverse("core:niveles")).content.decode()
        for orden in range(1, 7):
            assert f"rango-{orden}.webp" in contenido
        # Los cuatro que aún no se han alcanzado van apagados.
        assert contenido.count("emblema-off") == 4

    def test_las_imagenes_existen_en_disco(self):
        from django.contrib.staticfiles import finders

        for orden in range(1, 7):
            assert finders.find(f"img/rangos/rango-{orden}.webp"), orden
