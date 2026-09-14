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
    def test_el_lunes_sin_revision_penaliza_80(self):
        _contacto_en(LUNES_S37)
        chequeo(LUNES_S38)
        assert Penalty.objects.get(regla_slug__startswith="revision-no-hecha").xp == -80

    def test_con_la_revision_cerrada_no_penaliza(self):
        WeeklyReview.objects.create(
            anio=2026, semana_iso=37, fecha=DOMINGO_S37, m8_revision_hecha=True
        )
        _contacto_en(LUNES_S37)
        chequeo(LUNES_S38)
        assert not Penalty.objects.filter(regla_slug__startswith="revision-no-hecha").exists()

    def test_un_borrador_sin_cerrar_si_penaliza(self):
        WeeklyReview.objects.create(
            anio=2026, semana_iso=37, fecha=DOMINGO_S37, m8_revision_hecha=False
        )
        _contacto_en(LUNES_S37)
        chequeo(LUNES_S38)
        assert Penalty.objects.filter(regla_slug__startswith="revision-no-hecha").exists()

    def test_solo_se_comprueba_los_lunes(self):
        _contacto_en(LUNES_S37)
        chequeo(MARTES_S38)
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
