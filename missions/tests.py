import datetime as dt
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from missions import services
from missions.models import Mission, MissionLog
from progression import services as progression
from progression.models import XPEvent, XPRule
from core.models import Profile

# Fechas fijas de 2026 para no depender del dia en que se ejecuten los tests.
LUNES = dt.date(2026, 9, 7)
MIERCOLES = dt.date(2026, 9, 9)
DOMINGO = dt.date(2026, 9, 13)


@pytest.fixture
def d1(db):
    return Mission.objects.get(titulo__startswith="D1 · ")


@pytest.fixture
def d2(db):
    return Mission.objects.get(titulo__startswith="D2 · ")


@pytest.mark.django_db
class TestMisionesDeHoy:
    def test_un_lunes_hay_diarias_y_semanales(self):
        titulos = [m.titulo for m in services.misiones_de_hoy(LUNES)]
        assert any(t.startswith("D1 · ") for t in titulos)
        assert any(t.startswith("S1 · ") for t in titulos)

    def test_el_miercoles_no_hay_ninguna_mision(self):
        assert list(services.misiones_de_hoy(MIERCOLES)) == []

    def test_el_domingo_solo_quedan_las_semanales(self):
        tipos = {m.tipo for m in services.misiones_de_hoy(DOMINGO)}
        assert tipos == {Mission.Tipo.SEMANAL}

    def test_las_minimas_no_aparecen_en_el_dia_completo(self):
        assert not any(m.es_minima for m in services.misiones_de_hoy(LUNES))

    def test_una_semanal_hecha_deja_de_pedirse_esa_semana(self, db):
        semanal = Mission.objects.get(titulo__startswith="S2 · ")
        services.completar_mision(semanal, fecha=LUNES)
        assert semanal not in services.misiones_de_hoy(LUNES + dt.timedelta(days=1))

    def test_modo_dia_minimo_solo_devuelve_minimas(self):
        minimas = services.modo_dia_minimo()
        assert minimas.exists()
        assert all(m.es_minima for m in minimas)


@pytest.mark.django_db
class TestCompletarMision:
    def test_completar_crea_registro_y_concede_xp(self, d1):
        antes = Profile.get().xp_total
        registro = services.completar_mision(d1, evidencia="Email a Felycampo", fecha=LUNES)
        assert registro.completada
        assert registro.xp_otorgado == d1.xp
        assert Profile.get().xp_total == antes + d1.xp
        assert XPEvent.objects.filter(objeto_relacionado=f"mission:{d1.pk}").count() == 1

    def test_es_idempotente_dentro_del_mismo_dia(self, d1):
        services.completar_mision(d1, evidencia="uno", fecha=LUNES)
        antes = Profile.get().xp_total
        services.completar_mision(d1, evidencia="dos", fecha=LUNES)
        assert MissionLog.objects.filter(mission=d1, fecha=LUNES).count() == 1
        assert XPEvent.objects.filter(objeto_relacionado=f"mission:{d1.pk}").count() == 1
        assert Profile.get().xp_total == antes

    def test_se_puede_repetir_al_dia_siguiente(self, d1):
        services.completar_mision(d1, evidencia="uno", fecha=LUNES)
        services.completar_mision(d1, evidencia="dos", fecha=LUNES + dt.timedelta(days=1))
        assert MissionLog.objects.filter(mission=d1, completada=True).count() == 2

    def test_sin_evidencia_no_se_completa_si_la_exige(self, d1):
        assert d1.evidencia_requerida
        with pytest.raises(services.EvidenciaRequerida):
            services.completar_mision(d1, evidencia="   ", fecha=LUNES)
        assert not MissionLog.objects.filter(mission=d1, completada=True).exists()
        assert not XPEvent.objects.exists()

    def test_sin_evidencia_se_completa_si_no_la_exige(self, d2):
        assert not d2.evidencia_requerida
        assert services.completar_mision(d2, fecha=LUNES).completada


@pytest.mark.django_db
class TestRachaYTopes:
    def _dias_seguidos(self, d1, desde, cuantos):
        for i in range(cuantos):
            fecha = desde + dt.timedelta(days=i)
            if progression.es_dia_protegido(fecha):
                continue
            services.completar_mision(d1, evidencia="contacto", fecha=fecha)

    def test_la_racha_cuenta_dias_con_accion_comercial(self, d1):
        self._dias_seguidos(d1, LUNES, 2)
        assert progression.racha_actual(LUNES + dt.timedelta(days=1)) == 2

    def test_el_miercoles_no_rompe_la_racha(self, d1):
        # Lunes y martes hechos, miercoles saltado, jueves hecho.
        self._dias_seguidos(d1, LUNES, 4)
        assert not MissionLog.objects.filter(fecha=MIERCOLES).exists()
        assert progression.racha_actual(dt.date(2026, 9, 10)) == 3

    def test_el_multiplicador_sube_a_los_cinco_dias(self, d1):
        self._dias_seguidos(d1, LUNES, 7)  # 5 dias efectivos: el miercoles no cuenta
        sabado = dt.date(2026, 9, 12)
        assert progression.racha_actual(sabado) == 5
        assert progression.multiplicador_racha(sabado) == Decimal("1.10")

    def test_el_tope_semanal_recorta_la_xp(self, db):
        # La regla viene de la tabla de XP del documento: 60 XP, tope 300/semana.
        regla = XPRule.objects.get(accion_slug="conversacion-comercial")
        assert (regla.xp, regla.tope_semanal) == (60, 300)
        for _ in range(5):
            progression.registrar_xp("conversacion-comercial", fecha=LUNES)
        sexto = progression.registrar_xp("conversacion-comercial", fecha=LUNES)
        assert sexto.xp_bruto == 60
        assert sexto.xp_neto == 0  # 5 x 60 = 300, el tope ya está agotado
        assert sexto.tope_aplicado is True

    def test_una_penalizacion_no_se_multiplica_por_la_racha(self, d1):
        self._dias_seguidos(d1, LUNES, 7)
        evento = progression.registrar_xp(
            "semana-sin-comercial", xp=-150, categoria="PENALIZACION", fecha=dt.date(2026, 9, 12)
        )
        assert evento.xp_neto == -150
        assert evento.multiplicador_racha == 1


@pytest.mark.django_db
class TestPanelHTMX:
    def test_el_panel_carga(self, client):
        respuesta = client.get(reverse("core:index"))
        assert respuesta.status_code == 200
        assert b"Nivel" in respuesta.content

    def test_completar_por_htmx_devuelve_el_fragmento(self, client, d2):
        respuesta = client.post(reverse("missions:completar", args=[d2.pk]))
        assert respuesta.status_code == 200
        assert b'id="bloque-misiones"' in respuesta.content
        assert b"<html" not in respuesta.content
        assert services.esta_completada(d2)

    def test_si_falta_evidencia_el_fragmento_lleva_el_error(self, client, d1):
        respuesta = client.post(reverse("missions:completar", args=[d1.pk]))
        assert respuesta.status_code == 200
        assert "evidencia".encode() in respuesta.content
        assert not services.esta_completada(d1)

    def test_el_modal_de_evidencia_se_abre(self, client, d1):
        respuesta = client.get(reverse("missions:evidencia", args=[d1.pk]))
        assert respuesta.status_code == 200
        assert b"<form" in respuesta.content

    def test_el_dia_minimo_reduce_la_lista(self, client):
        respuesta = client.get(reverse("missions:bloque"), {"minimo": "1"})
        assert b"D&#x27;a m" in respuesta.content or "Día mínimo".encode() in respuesta.content
