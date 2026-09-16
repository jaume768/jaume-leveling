import datetime as dt
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.urls import reverse

from business.models import Client, Deal, Invoice, Project
from core.models import Profile
from progression import services
from progression.models import Penalty, XPEvent
from review.models import WeeklyReview

# Semana 37 de 2026: lunes 7 a domingo 13. Semana 38: lunes 14.
LUNES_S37 = dt.date(2026, 9, 7)
DOMINGO_S37 = dt.date(2026, 9, 13)
LUNES_S38 = dt.date(2026, 9, 14)
MARTES_S38 = dt.date(2026, 9, 15)


def chequeo(fecha, **extra):
    salida = StringIO()
    call_command("chequeo_diario", fecha=fecha.isoformat(), stdout=salida, **extra)
    return salida.getvalue()


@pytest.fixture
def cliente(db):
    return Client.objects.create(nombre="Felycampo", slug="felycampo")


def _contacto_en(fecha):
    """Un contacto para que no salte la regla de la semana sin comercial."""
    return Deal.objects.create(negocio=f"Contacto {fecha}", fecha_primer_contacto=fecha)


@pytest.mark.django_db
class TestFacturaSinReclamar:
    def _factura(self, cliente, dias_vencida):
        return Invoice.objects.create(
            client=cliente, concepto="Web", importe=Decimal("2000"),
            fecha_emision=MARTES_S38 - dt.timedelta(days=dias_vencida + 30),
            vencimiento=MARTES_S38 - dt.timedelta(days=dias_vencida),
        )

    def test_a_los_16_dias_penaliza_200(self, cliente):
        self._factura(cliente, 16)
        _contacto_en(LUNES_S37)
        antes = Profile.get().xp_total
        chequeo(MARTES_S38)
        penalizacion = Penalty.objects.get(regla_slug__startswith="factura-vencida")
        assert penalizacion.xp == -200
        assert penalizacion.resuelta is False
        assert "Reclamación" in penalizacion.correccion_exigida
        assert Profile.get().xp_total == antes - 200

    def test_a_los_14_dias_todavia_no(self, cliente):
        self._factura(cliente, 14)
        _contacto_en(LUNES_S37)
        chequeo(MARTES_S38)
        assert not Penalty.objects.filter(regla_slug__startswith="factura-vencida").exists()

    def test_una_factura_cobrada_no_penaliza(self, cliente):
        factura = self._factura(cliente, 40)
        factura.cobrada = True
        factura.save()
        _contacto_en(LUNES_S37)
        chequeo(MARTES_S38)
        assert not Penalty.objects.filter(regla_slug__startswith="factura-vencida").exists()

    def test_no_penaliza_dos_veces_la_misma_factura(self, cliente):
        self._factura(cliente, 20)
        _contacto_en(LUNES_S37)
        chequeo(MARTES_S38)
        antes = Profile.get().xp_total
        chequeo(MARTES_S38 + dt.timedelta(days=1))
        assert Penalty.objects.filter(regla_slug__startswith="factura-vencida").count() == 1
        assert Profile.get().xp_total == antes

    def test_dos_facturas_distintas_penalizan_por_separado(self, cliente):
        self._factura(cliente, 20)
        self._factura(cliente, 30)
        _contacto_en(LUNES_S37)
        chequeo(MARTES_S38)
        assert Penalty.objects.filter(regla_slug__startswith="factura-vencida").count() == 2


@pytest.mark.django_db
class TestPropuestaSinSeguimiento:
    def test_a_los_8_dias_penaliza_100(self):
        Deal.objects.create(
            negocio="Gimnasio", estado=Deal.Estado.PROPUESTA,
            fecha_primer_contacto=LUNES_S37 - dt.timedelta(days=20),
            ultimo_toque=MARTES_S38 - dt.timedelta(days=8),
        )
        chequeo(MARTES_S38)
        penalizacion = Penalty.objects.get(regla_slug__startswith="propuesta-sin-seguimiento")
        assert penalizacion.xp == -100

    def test_a_los_6_dias_no(self):
        Deal.objects.create(
            negocio="Gimnasio", estado=Deal.Estado.PROPUESTA,
            fecha_primer_contacto=LUNES_S37, ultimo_toque=MARTES_S38 - dt.timedelta(days=6),
        )
        chequeo(MARTES_S38)
        assert not Penalty.objects.filter(regla_slug__startswith="propuesta-sin-seguimiento").exists()

    def test_solo_penaliza_las_propuestas(self):
        Deal.objects.create(
            negocio="Charla", estado=Deal.Estado.CONVERSANDO,
            fecha_primer_contacto=LUNES_S37, ultimo_toque=MARTES_S38 - dt.timedelta(days=30),
        )
        chequeo(MARTES_S38)
        assert not Penalty.objects.filter(regla_slug__startswith="propuesta-sin-seguimiento").exists()

    def test_una_vez_por_semana_y_deal(self):
        Deal.objects.create(
            negocio="Gimnasio", estado=Deal.Estado.PROPUESTA,
            fecha_primer_contacto=LUNES_S37, ultimo_toque=LUNES_S37 - dt.timedelta(days=10),
        )
        chequeo(LUNES_S38)
        chequeo(MARTES_S38)
        assert Penalty.objects.filter(regla_slug__startswith="propuesta-sin-seguimiento").count() == 1


@pytest.mark.django_db
class TestSemanaSinComercial:
    def test_sin_contactos_penaliza_150_y_bloquea(self):
        antes = Profile.get().xp_total
        chequeo(MARTES_S38)  # la semana 37 terminó sin contactos
        penalizacion = Penalty.objects.get(regla_slug__startswith="semana-sin-comercial")
        assert penalizacion.xp == -150
        assert "bloqueado" in penalizacion.correccion_exigida
        assert Profile.get().xp_total == antes - 150

        bloqueo = services.bloqueo_tecnico_activo(MARTES_S38)
        assert bloqueo is not None
        assert bloqueo["objetivo"] == 6
        assert bloqueo["cumplido"] is False

    def test_con_un_contacto_no_penaliza(self):
        _contacto_en(DOMINGO_S37)
        chequeo(MARTES_S38)
        assert not Penalty.objects.filter(regla_slug__startswith="semana-sin-comercial").exists()

    def test_el_bloqueo_se_levanta_con_6_contactos(self):
        chequeo(MARTES_S38)
        for i in range(6):
            _contacto_en(LUNES_S38)
        bloqueo = services.bloqueo_tecnico_activo(MARTES_S38)
        assert bloqueo["contactos"] == 6
        assert bloqueo["cumplido"] is True

    def test_el_bloqueo_desaparece_al_resolver(self):
        chequeo(MARTES_S38)
        penalizacion = Penalty.objects.get(regla_slug__startswith="semana-sin-comercial")
        services.resolver_penalizacion(penalizacion.pk)
        assert services.bloqueo_tecnico_activo(MARTES_S38) is None

    def test_no_penaliza_dos_veces_la_misma_semana(self):
        chequeo(LUNES_S38)
        chequeo(MARTES_S38)
        assert Penalty.objects.filter(regla_slug__startswith="semana-sin-comercial").count() == 1


@pytest.mark.django_db
class TestExcesoDeWip:
    def _proyectos(self, cliente, cuantos):
        for i in range(cuantos):
            Project.objects.create(
                client=cliente, nombre=f"Proyecto {i}", precio=Decimal("2000"),
                estado=Project.Estado.ACTIVO,
            )

    def test_tres_activos_penalizan_100(self, cliente):
        self._proyectos(cliente, 3)
        _contacto_en(LUNES_S37)
        chequeo(MARTES_S38)
        assert Penalty.objects.get(regla_slug__startswith="exceso-wip").xp == -100

    def test_dos_activos_no_penalizan(self, cliente):
        self._proyectos(cliente, 2)
        _contacto_en(LUNES_S37)
        chequeo(MARTES_S38)
        assert not Penalty.objects.filter(regla_slug__startswith="exceso-wip").exists()

    def test_los_congelados_no_cuentan(self, cliente):
        self._proyectos(cliente, 2)
        Project.objects.create(
            client=cliente, nombre="Congelado", precio=Decimal("2000"),
            estado=Project.Estado.CONGELADO,
        )
        _contacto_en(LUNES_S37)
        chequeo(MARTES_S38)
        assert not Penalty.objects.filter(regla_slug__startswith="exceso-wip").exists()


@pytest.mark.django_db
class TestRevisionNoHecha:
    """La revisión no penaliza. El documento la puntúa, pero no castiga su falta."""

    def test_el_lunes_sin_revision_no_penaliza(self):
        _contacto_en(LUNES_S37)
        chequeo(LUNES_S38)
        assert not Penalty.objects.filter(regla_slug__startswith="revision-no-hecha").exists()

    def test_un_borrador_sin_cerrar_tampoco_penaliza(self):
        WeeklyReview.objects.create(
            anio=2026, semana_iso=37, fecha=DOMINGO_S37, m8_revision_hecha=False
        )
        _contacto_en(LUNES_S37)
        chequeo(LUNES_S38)
        assert not Penalty.objects.filter(regla_slug__startswith="revision-no-hecha").exists()


@pytest.mark.django_db
class TestComando:
    def test_simular_no_escribe_nada(self, cliente):
        Invoice.objects.create(
            client=cliente, concepto="Web", importe=Decimal("2000"),
            fecha_emision=LUNES_S37, vencimiento=LUNES_S37 - dt.timedelta(days=20),
        )
        antes = Profile.get().xp_total
        salida = chequeo(MARTES_S38, simular=True)
        assert Penalty.objects.count() == 0
        assert XPEvent.objects.count() == 0
        assert Profile.get().xp_total == antes
        assert "simulación" in salida

    def test_sin_nada_que_penalizar_lo_dice(self):
        _contacto_en(LUNES_S37)
        assert "nada que penalizar" in chequeo(MARTES_S38)

    def test_la_penalizacion_no_la_multiplica_la_racha(self, cliente):
        Invoice.objects.create(
            client=cliente, concepto="Web", importe=Decimal("2000"),
            fecha_emision=LUNES_S37, vencimiento=LUNES_S37 - dt.timedelta(days=20),
        )
        _contacto_en(LUNES_S37)
        chequeo(MARTES_S38)
        evento = XPEvent.objects.get(accion_slug="factura-vencida-sin-reclamar")
        assert evento.xp_neto == -200
        assert evento.multiplicador_racha == 1


@pytest.mark.django_db
class TestResolverDesdeElPanel:
    def test_el_boton_marca_la_penalizacion_como_resuelta(self, client):
        chequeo(MARTES_S38)
        penalizacion = Penalty.objects.get(regla_slug__startswith="semana-sin-comercial")
        respuesta = client.post(reverse("progression:resolver", args=[penalizacion.pk]))
        assert respuesta.status_code == 200
        assert b'id="alertas"' in respuesta.content
        penalizacion.refresh_from_db()
        assert penalizacion.resuelta is True

    def test_resolver_no_devuelve_la_xp(self, client):
        chequeo(MARTES_S38)
        penalizacion = Penalty.objects.get(regla_slug__startswith="semana-sin-comercial")
        antes = Profile.get().xp_total
        client.post(reverse("progression:resolver", args=[penalizacion.pk]))
        assert Profile.get().xp_total == antes



# --- Acciones sueltas de la tabla de XP --------------------------------------


@pytest.mark.django_db
class TestRegistrarAccion:
    def test_registra_la_xp_de_la_regla(self):
        evento = services.registrar_accion("peticion-referido", "Referido pedido a Ana")

        assert evento.xp_bruto == 50
        assert evento.xp_neto == 50
        assert evento.descripcion == "Referido pedido a Ana"

    def test_respeta_el_tope_semanal(self):
        for i in range(3):
            services.registrar_accion("peticion-referido", f"referido {i}")
        # El tope de peticion-referido son 150/semana: la cuarta no suma.
        cuarta = services.registrar_accion("peticion-referido", "una mas")

        assert cuarta.xp_neto == 0
        assert cuarta.tope_aplicado is True

    def test_exige_evidencia(self):
        with pytest.raises(ValueError):
            services.registrar_accion("peticion-referido", "   ")

    def test_no_deja_registrar_lo_que_ya_llega_solo(self):
        """Dinero cobrado viene de las facturas: a mano seria puntuar dos veces."""
        with pytest.raises(ValueError):
            services.registrar_accion("dinero-cobrado", "2.000 EUR")

    def test_el_modal_lista_las_acciones_registrables(self, client):
        respuesta = client.get(reverse("progression:registrar_accion"))

        assert respuesta.status_code == 200
        assert b"peticion-referido" in respuesta.content
        # Las automaticas no salen en la lista.
        assert b"contrato-recurrente-firmado" not in respuesta.content

    def test_el_post_registra_y_devuelve_el_resultado(self, client):
        respuesta = client.post(
            reverse("progression:registrar_accion"),
            {"accion": "publicacion-contenido-real", "evidencia": "Caso de Felycampo"},
        )

        assert respuesta.status_code == 200
        assert "+40 XP".encode() in respuesta.content
        assert XPEvent.objects.filter(accion_slug="publicacion-contenido-real").exists()


# --- Detalle de un evento de XP ----------------------------------------------


@pytest.mark.django_db
class TestDetalleDeEvento:
    def _mision(self, titulo):
        from missions.models import Mission

        return Mission.objects.get(titulo__startswith=titulo)

    def test_una_mision_muestra_la_evidencia_que_anotaste(self):
        from missions import services as misiones

        mision = self._mision("D1 · ")
        misiones.completar_mision(mision, evidencia="Email a Gruas Perelló", fecha=LUNES_S37)
        evento = XPEvent.objects.get(objeto_relacionado=f"mission:{mision.pk}")

        detalle = services.detalle_de_evento(evento)
        assert detalle["origen"]["tipo"] == "Misión"
        assert detalle["origen"]["evidencia"] == "Email a Gruas Perelló"

    def test_una_mision_de_cuaderno_muestra_lo_apuntado(self):
        from missions import services as misiones

        mision = self._mision("D2 · ")
        misiones.completar_mision(mision, notas="1. Llamar\n2. Escribir", fecha=LUNES_S37)
        evento = XPEvent.objects.get(objeto_relacionado=f"mission:{mision.pk}")

        assert services.detalle_de_evento(evento)["origen"]["notas"] == "1. Llamar\n2. Escribir"

    def test_una_accion_manual_guarda_la_evidencia_en_la_descripcion(self):
        evento = services.registrar_accion("peticion-referido", "Pedido a Felycampo")
        detalle = services.detalle_de_evento(evento)
        assert detalle["manual"] is True
        assert detalle["origen"] is None
        assert detalle["evento"].descripcion == "Pedido a Felycampo"

    def test_una_factura_muestra_su_concepto_y_sus_notas(self, cliente):
        from business import services as negocio

        factura = Invoice.objects.create(
            client=cliente, concepto="Tienda online", importe=Decimal("2000"),
            fecha_emision=LUNES_S37, vencimiento=LUNES_S37, notas="Por transferencia",
        )
        negocio.marcar_cobrada(factura, fecha=LUNES_S37)
        evento = XPEvent.objects.get(objeto_relacionado=f"invoice:{factura.pk}")

        origen = services.detalle_de_evento(evento)["origen"]
        assert origen["tipo"] == "Factura"
        assert origen["subtitulo"] == "Tienda online"
        assert origen["evidencia"] == "Por transferencia"

    def test_una_penalizacion_muestra_la_correccion_exigida(self):
        chequeo(MARTES_S38)
        penalizacion = Penalty.objects.get(regla_slug__startswith="semana-sin-comercial")
        evento = XPEvent.objects.get(objeto_relacionado=f"penalty:{penalizacion.pk}")

        origen = services.detalle_de_evento(evento)["origen"]
        assert origen["tipo"] == "Penalización"
        assert "bloqueado" in origen["evidencia"]

    def test_una_referencia_a_un_objeto_borrado_no_revienta(self):
        evento = XPEvent.objects.create(
            fecha=LUNES_S37, categoria="RESULTADO", accion_slug="prueba",
            descripcion="huérfano", xp_bruto=10, xp_neto=10,
            objeto_relacionado="mission:999999",
        )
        assert services.detalle_de_evento(evento)["origen"] is None

    def test_una_referencia_con_formato_raro_no_revienta(self):
        evento = XPEvent.objects.create(
            fecha=LUNES_S37, categoria="RESULTADO", accion_slug="prueba",
            xp_bruto=10, xp_neto=10, objeto_relacionado="esto-no-es-una-referencia",
        )
        assert services.detalle_de_evento(evento)["origen"] is None


@pytest.mark.django_db
class TestVistaDelEvento:
    def test_el_modal_se_abre_con_la_anotacion(self, client):
        from missions import services as misiones
        from missions.models import Mission

        mision = Mission.objects.get(titulo__startswith="D1 · ")
        misiones.completar_mision(mision, evidencia="Email a Gruas Perelló", fecha=LUNES_S37)
        evento = XPEvent.objects.get(objeto_relacionado=f"mission:{mision.pk}")

        respuesta = client.get(reverse("progression:evento", args=[evento.pk]))
        assert respuesta.status_code == 200
        assert "Email a Gruas Perelló".encode() in respuesta.content
        assert b"<html" not in respuesta.content

    def test_un_evento_sin_anotacion_lo_dice(self, client):
        evento = XPEvent.objects.create(
            fecha=LUNES_S37, categoria="RESULTADO", accion_slug="prueba",
            xp_bruto=10, xp_neto=10,
        )
        respuesta = client.get(reverse("progression:evento", args=[evento.pk]))
        assert "No se anotó nada".encode() in respuesta.content

    def test_un_evento_inexistente_da_404(self, client):
        assert client.get(reverse("progression:evento", args=[999999])).status_code == 404

    def test_las_filas_de_la_tabla_enlazan_al_detalle(self, client):
        evento = services.registrar_accion("peticion-referido", "Pedido a Felycampo")
        contenido = client.get(reverse("progression:index")).content.decode()
        assert reverse("progression:evento", args=[evento.pk]) in contenido
        assert 'id="modal"' in contenido


@pytest.mark.django_db
class TestEtiquetasDeLasAcciones:
    """El modal debe enseñar el nombre de la regla, no su slug.

    Un slug va sin tildes ni ñ por definición: "sueno-7h". Si la plantilla
    pide un campo que no existe, Django devuelve vacío y cae al slug sin
    avisar, que es justo lo que pasaba.
    """

    def test_el_modal_usa_los_nombres_con_tildes(self, client):
        contenido = client.get(reverse("progression:registrar_accion")).content.decode()

        assert "Sueño de 7 h o más" in contenido
        assert "Conversación comercial real" in contenido
        assert "Petición de referido hecha" in contenido

    def test_el_modal_no_ensena_ningun_slug(self, client):
        from progression.services import acciones_registrables

        contenido = client.get(reverse("progression:registrar_accion")).content.decode()
        for regla in acciones_registrables():
            # El slug sigue en el value del radio, pero no como texto visible.
            assert f">{regla.accion_slug}<" not in contenido
            assert regla.nombre in contenido

    def test_la_calibracion_tambien(self, client):
        contenido = client.get(reverse("core:calibracion")).content.decode()
        assert "sueno-7h" not in contenido or "Sueño de 7 h o más" in contenido


@pytest.mark.django_db
class TestDiasProtegidos:
    """Miércoles y domingo no penalizan, pase lo que pase.

    Se monta el peor escenario posible —factura vencida, propuesta fría y tres
    proyectos abiertos— y aun así el comando no debe escribir nada.
    """

    MIERCOLES = dt.date(2026, 9, 16)
    DOMINGO = dt.date(2026, 9, 20)

    @pytest.fixture
    def todo_mal(self, cliente):
        """Una factura vencida, una propuesta fría y WIP por encima del tope."""
        Invoice.objects.create(
            client=cliente, concepto="Web", importe=Decimal("2000"),
            fecha_emision=LUNES_S37 - dt.timedelta(days=40),
            vencimiento=LUNES_S37 - dt.timedelta(days=20),
        )
        Deal.objects.create(
            negocio="Gimnasio", estado=Deal.Estado.PROPUESTA,
            fecha_primer_contacto=LUNES_S37 - dt.timedelta(days=30),
            ultimo_toque=LUNES_S37 - dt.timedelta(days=20),
        )
        for i in range(3):
            Project.objects.create(
                client=cliente, nombre=f"Proyecto {i}", precio=Decimal("2000"),
                estado=Project.Estado.ACTIVO,
            )

    def test_el_miercoles_no_penaliza_nada(self, todo_mal):
        antes = Profile.get().xp_total
        salida = chequeo(self.MIERCOLES)

        assert Penalty.objects.count() == 0
        assert XPEvent.objects.count() == 0
        assert Profile.get().xp_total == antes
        assert "protegido" in salida

    def test_el_domingo_no_penaliza_nada(self, todo_mal):
        antes = Profile.get().xp_total
        salida = chequeo(self.DOMINGO)

        assert Penalty.objects.count() == 0
        assert XPEvent.objects.count() == 0
        assert Profile.get().xp_total == antes
        assert "protegido" in salida

    def test_el_mismo_escenario_en_martes_si_penaliza(self, todo_mal):
        """Prueba de control: sin ella, los dos tests de arriba no valen nada."""
        chequeo(MARTES_S38)

        reglas = {p.regla_slug.split("--")[0] for p in Penalty.objects.all()}
        assert "factura-vencida-sin-reclamar" in reglas
        assert "propuesta-sin-seguimiento" in reglas
        assert "exceso-wip" in reglas

    def test_un_dia_protegido_no_bloquea_el_dia_siguiente(self, todo_mal):
        """Saltarse el miércoles no puede perdonar la deuda: el jueves cobra."""
        chequeo(self.MIERCOLES)
        assert Penalty.objects.count() == 0

        chequeo(self.MIERCOLES + dt.timedelta(days=1))
        assert Penalty.objects.count() > 0


# --- Recompensas -------------------------------------------------------------


@pytest.mark.django_db
class TestRecompensas:
    """Tres estados: bloqueada, ganada y cobrada."""

    def _perfil_en_nivel(self, nivel):
        from core import services as core_services

        perfil = Profile.get()
        perfil.nivel = nivel
        perfil.xp_total = core_services.xp_acumulada_hasta_nivel(nivel)
        perfil.rango = core_services.rango_para_nivel(nivel)
        perfil.save()
        return perfil

    def test_estan_sembradas_y_todas_bloqueadas(self):
        from progression.models import Reward

        assert Reward.objects.count() >= 5
        assert not Reward.objects.filter(desbloqueada=True).exists()

    def test_subir_de_nivel_desbloquea_la_suya(self):
        from progression.models import Reward

        premio = Reward.objects.get(nivel_requerido=50)
        assert premio.desbloqueada is False

        self._perfil_en_nivel(50)
        nuevas = services.revisar_recompensas()

        premio.refresh_from_db()
        assert premio.desbloqueada is True
        assert premio.fecha is not None
        assert premio in nuevas

    def test_no_se_desbloquea_antes_de_tiempo(self):
        from progression.models import Reward

        self._perfil_en_nivel(49)
        services.revisar_recompensas()
        assert Reward.objects.get(nivel_requerido=50).desbloqueada is False

    def test_ascender_de_rango_desbloquea_la_del_rango(self):
        from core.models import Rank
        from progression.models import Reward

        especialista = Rank.objects.get(orden=3)
        premio = Reward.objects.get(rango=especialista)

        self._perfil_en_nivel(especialista.nivel_min)
        services.revisar_recompensas()

        premio.refresh_from_db()
        assert premio.desbloqueada is True

    def test_revisar_dos_veces_no_la_desbloquea_dos_veces(self):
        self._perfil_en_nivel(50)
        primera = services.revisar_recompensas()
        segunda = services.revisar_recompensas()
        assert primera and not segunda

    def test_las_manuales_no_se_desbloquean_solas(self):
        from progression.models import Reward

        self._perfil_en_nivel(60)
        services.revisar_recompensas()
        manuales = [r for r in Reward.objects.all() if r.es_manual]
        assert manuales
        assert all(not r.desbloqueada for r in manuales)

    def test_una_manual_se_desbloquea_a_mano(self):
        from progression.models import Reward

        manual = next(r for r in Reward.objects.all() if r.es_manual)
        services.desbloquear_recompensa(manual.pk)
        manual.refresh_from_db()
        assert manual.desbloqueada is True

    def test_solo_se_disfruta_lo_desbloqueado(self):
        from progression.models import Reward

        premio = Reward.objects.get(nivel_requerido=50)
        assert services.disfrutar_recompensa(premio.pk) is None

        self._perfil_en_nivel(50)
        services.revisar_recompensas()
        assert services.disfrutar_recompensa(premio.pk) is not None

        premio.refresh_from_db()
        assert premio.disfrutada is True
        assert premio.fecha_disfrute is not None

    def test_el_panel_separa_los_tres_estados(self):
        self._perfil_en_nivel(50)
        panel = services.panel_de_recompensas()

        assert len(panel["pendientes"]) == 1
        assert panel["disfrutadas"] == []
        assert panel["bloqueadas"]

        services.disfrutar_recompensa(panel["pendientes"][0].pk)
        panel = services.panel_de_recompensas()
        assert panel["pendientes"] == []
        assert len(panel["disfrutadas"]) == 1

    def test_dice_cual_es_la_siguiente_y_cuanto_falta(self):
        panel = services.panel_de_recompensas()
        assert panel["siguiente"].nivel_requerido == 50
        assert panel["faltan_niveles"] == 5


@pytest.mark.django_db
class TestPantallaDeRecompensas:
    def test_la_pantalla_carga(self, client):
        respuesta = client.get(reverse("progression:recompensas"))
        assert respuesta.status_code == 200
        assert "Un juego de Switch sin culpa".encode() in respuesta.content

    def test_esta_en_el_menu(self, client):
        contenido = client.get(reverse("core:index")).content.decode()
        assert reverse("progression:recompensas") in contenido

    def test_desbloquear_a_mano_por_htmx(self, client):
        from progression.models import Reward

        manual = next(r for r in Reward.objects.all() if r.es_manual)
        respuesta = client.post(
            reverse("progression:desbloquear_recompensa", args=[manual.pk])
        )
        assert respuesta.status_code == 200
        assert b'id="recompensas"' in respuesta.content
        assert b"<html" not in respuesta.content
        manual.refresh_from_db()
        assert manual.desbloqueada is True

    def test_disfrutar_por_htmx(self, client):
        from progression.models import Reward

        manual = next(r for r in Reward.objects.all() if r.es_manual)
        services.desbloquear_recompensa(manual.pk)
        client.post(reverse("progression:disfrutar_recompensa", args=[manual.pk]))
        manual.refresh_from_db()
        assert manual.disfrutada is True
