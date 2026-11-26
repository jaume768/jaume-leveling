"""Avisos de seguimiento y boton de WhatsApp del pipeline."""
import datetime as dt
from decimal import Decimal

import pytest
from django.urls import reverse

from business import services
from business.models import Deal

HOY = dt.date(2026, 9, 10)  # jueves


def _deal(estado=Deal.Estado.CONTACTADO, dias=0, **extra):
    datos = {
        "negocio": "Piscinca",
        "estado": estado,
        "fecha_primer_contacto": HOY - dt.timedelta(days=dias),
        "ultimo_toque": HOY - dt.timedelta(days=dias),
    }
    datos.update(extra)
    return Deal.objects.create(**datos)


@pytest.mark.django_db
class TestCuandoTocaSeguimiento:
    def test_un_contacto_a_los_3_dias_toca(self):
        assert services.motivo_seguimiento(_deal(dias=3), HOY) == "3 días sin respuesta"

    def test_un_contacto_a_los_2_dias_todavia_no(self):
        assert services.motivo_seguimiento(_deal(dias=2), HOY) == ""

    def test_una_propuesta_avisa_antes_de_penalizar(self):
        motivo = services.motivo_seguimiento(_deal(Deal.Estado.PROPUESTA, dias=4), HOY)
        assert "penaliza en 3" in motivo

    def test_un_proximo_paso_vencido_toca_aunque_sea_reciente(self):
        deal = _deal(dias=1, fecha_proximo_paso=HOY - dt.timedelta(days=1))
        assert services.motivo_seguimiento(deal, HOY) == "próximo paso vencido"

    def test_una_cerrada_nunca_toca(self):
        assert services.motivo_seguimiento(_deal(Deal.Estado.GANADO, dias=30), HOY) == ""

    def test_las_propuestas_salen_primero(self):
        _deal(Deal.Estado.CONTACTADO, dias=10, negocio="Frio")
        _deal(Deal.Estado.PROPUESTA, dias=4, negocio="Presupuesto")
        nombres = [p["deal"].negocio for p in services.seguimientos_pendientes(HOY)]
        assert nombres == ["Presupuesto", "Frio"]

    def test_el_panel_avisa_con_su_whatsapp(self):
        _deal(Deal.Estado.PROPUESTA, dias=4, negocio="Paesma", telefono="615 076 100")
        aviso = next(a for a in services.alertas(HOY) if a["clave"] == "seguimiento")
        assert aviso["enlaces"][0]["texto"] == "Paesma"
        assert aviso["enlaces"][0]["url"].startswith("https://wa.me/34615076100?text=")

    def test_lo_que_ya_esta_en_rojo_no_se_repite_en_seguimientos(self):
        _deal(Deal.Estado.PROPUESTA, dias=9, negocio="Olvidada")
        claves = [a["clave"] for a in services.alertas(HOY)]
        assert "pipeline" in claves
        assert "seguimiento" not in claves


class TestTelefono:
    @pytest.mark.parametrize(
        "entrada, salida",
        [
            ("637 72 56 11", "34637725611"),
            ("+34 637 725 611", "34637725611"),
            ("0034637725611", "34637725611"),
            ("971843445", "34971843445"),
            ("", ""),
        ],
    )
    def test_normaliza_con_prefijo(self, entrada, salida):
        assert services.telefono_whatsapp(entrada) == salida


@pytest.mark.django_db
class TestEnlaceWhatsapp:
    def test_con_telefono_va_al_chat_con_el_mensaje_del_estado(self):
        deal = _deal(Deal.Estado.PROPUESTA, telefono="637725611", contacto="Moises Egidos", negocio="Cuines Egidos")
        enlace = services.enlace_whatsapp(deal)
        assert enlace.startswith("https://wa.me/34637725611?text=")
        assert "Moises" in services.mensaje_seguimiento(deal)
        assert "presupuesto" in services.mensaje_seguimiento(deal)

    def test_sin_telefono_deja_elegir_el_chat(self):
        assert services.enlace_whatsapp(_deal()).startswith("https://wa.me/?text=")

    def test_el_pipeline_enseña_el_boton(self, client):
        _deal(telefono="637725611")
        contenido = client.get(reverse("business:pipeline")).content.decode()
        assert "https://wa.me/34637725611" in contenido

    def test_marca_las_propuestas_bajo_la_oferta_minima(self, client):
        _deal(Deal.Estado.PROPUESTA, valor_potencial=Decimal("200"))
        contenido = client.get(reverse("business:pipeline")).content.decode()
        assert "Bajo la oferta mínima" in contenido


@pytest.mark.django_db
class TestAplazadas:
    """El cliente pide retomarlo mas adelante: silencio hasta la fecha."""

    def _aplazada(self, dias=20):
        return _deal(Deal.Estado.CONVERSANDO, dias=dias, fecha_proximo_paso=HOY + dt.timedelta(days=30))

    def test_no_pide_seguimiento_antes_de_la_fecha(self):
        assert services.motivo_seguimiento(self._aplazada(), HOY) == ""

    def test_no_sale_como_oportunidad_fria(self):
        self._aplazada()
        assert list(services.deals_sin_tocar(HOY)) == []

    def test_la_fila_no_se_pone_en_rojo(self):
        self._aplazada()
        assert services.filas_pipeline(fecha=HOY)[0]["alerta"] == ""

    def test_el_dia_de_la_fecha_vuelve_a_avisar(self):
        deal = self._aplazada()
        assert services.motivo_seguimiento(deal, HOY + dt.timedelta(days=30)) == "próximo paso para hoy"
