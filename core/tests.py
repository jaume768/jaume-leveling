from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from business.models import Client, Deal, Invoice
from core.models import Profile


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
