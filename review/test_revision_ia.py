"""Revision del domingo: boton de cierre y borrador preparado por IA."""
import datetime as dt
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from core.models import Profile
from review import services
from review.models import WeeklyReview
from wisdom import ai
from wisdom.models import AdviceSession


def _datos(accion=None, **extra):
    hoy = timezone.localdate()
    anio, semana = hoy.isocalendar()[:2]
    datos = {
        "anio": anio, "semana_iso": semana, "fecha": hoy.isoformat(),
        "m1_eur_cobrados": "0", "m2_eur_recurrentes": "0", "m3_eur_vencidos": "0",
        "m4_contactos_nuevos": 0, "m5_conversaciones": 0, "m5_propuestas": 0,
        "m6_precio_medio": "0", "m7_tarifa_efectiva": "0", "m8_wip_abierto": 0,
        "m9_entrenos": 3, "xp_semana": 0, "m10_bloques_intactos": "on",
        "decision": "Seguimiento a las tres propuestas el lunes",
        "objetivo_1": "6 contactos", "objetivo_2": "1 cierre", "objetivo_3": "Caso nº1",
    }
    if accion:
        datos["accion"] = accion
    datos.update(extra)
    return datos


@pytest.mark.django_db
class TestBotonDeCierre:
    def test_cerrar_marca_hecha_y_da_60_xp(self, client):
        antes = Profile.get().xp_total
        client.post(reverse("review:index"), _datos("cerrar"))
        assert WeeklyReview.objects.get().m8_revision_hecha is True
        assert Profile.get().xp_total == antes + services.XP_REVISION

    def test_borrador_no_la_cierra(self, client):
        antes = Profile.get().xp_total
        client.post(reverse("review:index"), _datos("borrador"))
        assert WeeklyReview.objects.get().m8_revision_hecha is False
        assert Profile.get().xp_total == antes

    def test_guardar_cambios_no_reabre_una_cerrada(self, client):
        client.post(reverse("review:index"), _datos("cerrar"))
        client.post(reverse("review:index"), _datos("borrador", decision="Otra decisión"))
        revision = WeeklyReview.objects.get()
        assert revision.m8_revision_hecha is True
        assert revision.decision == "Otra decisión"

    def test_cerrar_sin_decision_no_vale(self, client):
        respuesta = client.post(reverse("review:index"), _datos("cerrar", decision=""))
        assert respuesta.status_code == 200
        assert not WeeklyReview.objects.exists()

    def test_la_pagina_enseña_los_dos_botones(self, client):
        contenido = client.get(reverse("review:index")).content.decode()
        assert "Cerrar la revisión (+60 XP)" in contenido
        assert "Preparar con IA" in contenido


class TestExtraerJson:
    def test_lee_el_json_aunque_venga_con_texto(self):
        texto = 'Aquí va:\n{"resumen": "R", "funciono": "F", "no_funciono": "N", "decision": "D", "objetivos": ["a"]}\nFin'
        datos = services._extraer_json(texto)
        assert datos["decision"] == "D"
        assert datos["objetivos"] == ["a", "", ""]

    def test_sin_json_falla(self):
        with pytest.raises(ValueError):
            services._extraer_json("nada")


@pytest.mark.django_db
class TestPrepararConIA:
    def test_devuelve_el_borrador_y_anota_el_coste(self, monkeypatch):
        respuesta = ai.RespuestaIA(
            texto='{"resumen": "Semana floja", "funciono": "x", "no_funciono": "y", '
                  '"decision": "Seguir las propuestas", "objetivos": ["1", "2", "3"]}',
            modelo="claude-sonnet-5", tokens_in=1000, tokens_out=200, coste=Decimal("0.004"),
        )
        monkeypatch.setattr(ai.ClienteIA, "preguntar", lambda self, system, mensaje: respuesta)
        propuesta, error = services.preparar_con_ia(dt.date(2026, 9, 13))
        assert error == ""
        assert propuesta["decision"] == "Seguir las propuestas"
        assert AdviceSession.objects.count() == 1

    def test_si_la_ia_falla_lo_dice_sin_romper(self, monkeypatch):
        def falla(self, system, mensaje):
            raise ai.IANoConfigurada("Falta ANTHROPIC_API_KEY.")

        monkeypatch.setattr(ai.ClienteIA, "preguntar", falla)
        propuesta, error = services.preparar_con_ia(dt.date(2026, 9, 13))
        assert propuesta is None
        assert "ANTHROPIC_API_KEY" in error

    def test_la_vista_responde_json(self, client, monkeypatch):
        monkeypatch.setattr(
            services, "preparar_con_ia",
            lambda fecha=None: ({"resumen": "R", "funciono": "", "no_funciono": "", "decision": "D", "objetivos": ["", "", ""]}, ""),
        )
        datos = client.post(reverse("review:preparar")).json()
        assert datos["ok"] is True
        assert datos["decision"] == "D"
