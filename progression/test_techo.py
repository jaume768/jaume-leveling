"""Techo semanal de 1.000 XP: frena misiones y soporte, no los hechos comerciales."""
import datetime as dt

import pytest

from missions import services as missions
from missions.models import Mission
from progression import services
from progression.models import Categoria, XPEvent, XPRule

LUNES = dt.date(2026, 9, 7)


def _mision(xp: int, slug: str = "mision-prueba") -> XPEvent:
    return services.registrar_xp(
        slug, xp=xp, categoria=Categoria.RESULTADO, fuente=XPEvent.Fuente.MISION, fecha=LUNES
    )


def _hecho(xp: int, slug: str = "dinero-cobrado-prueba") -> XPEvent:
    return services.registrar_xp(
        slug, xp=xp, categoria=Categoria.RESULTADO, fuente=XPEvent.Fuente.AUTO, fecha=LUNES
    )


@pytest.mark.django_db
class TestTechoSemanal:
    def test_las_misiones_siguen_frenadas_por_el_techo(self):
        _mision(900, "m-a")
        evento = _mision(300, "m-b")
        assert evento.xp_neto == 100
        assert evento.tope_aplicado is True
        assert evento.fuera_de_techo is False

    def test_un_hecho_comercial_no_lo_recorta_el_techo(self):
        _mision(1000)
        evento = _hecho(200)
        assert evento.xp_neto == 200
        assert evento.fuera_de_techo is True
        assert evento.tope_aplicado is False

    def test_un_hecho_comercial_no_le_quita_hueco_a_las_misiones(self):
        _hecho(900)
        evento = _mision(300)
        assert evento.xp_neto == 300

    def test_el_tope_por_accion_sigue_valiendo_fuera_del_techo(self):
        XPRule.objects.update_or_create(
            accion_slug="propuesta-prueba",
            defaults={"nombre": "Propuesta", "xp": 80, "tope_semanal": 160, "categoria": Categoria.RESULTADO},
        )
        _mision(1000)
        netos = [
            services.registrar_xp("propuesta-prueba", fuente=XPEvent.Fuente.AUTO, fecha=LUNES).xp_neto
            for _ in range(3)
        ]
        assert netos == [80, 80, 0]

    def test_una_penalizacion_no_va_fuera_de_techo(self):
        evento = services.registrar_xp(
            "penalizacion-prueba", xp=-100, categoria=Categoria.PENALIZACION,
            fuente=XPEvent.Fuente.AUTO, fecha=LUNES,
        )
        assert evento.fuera_de_techo is False
        assert evento.xp_neto == -100

    def test_una_mision_principal_no_llena_el_techo(self):
        principal = Mission.objects.create(
            titulo="Cobro y Cierre", tipo=Mission.Tipo.PRINCIPAL,
            definicion_terminada="2.000 EUR cobrados", xp=600,
        )
        registro = missions.completar_mision(principal, evidencia="Cobrado", fecha=LUNES)
        assert registro.xp_otorgado == 600
        evento = XPEvent.objects.get(objeto_relacionado=f"mission:{principal.pk}")
        assert evento.fuera_de_techo is True
        # La semana sigue teniendo los 1.000 XP del techo para lo demas.
        assert services.xp_dentro_del_techo(LUNES) == 0
        assert _mision(1000).xp_neto == 1000

    def test_una_mision_diaria_ocupa_el_techo(self):
        diaria = Mission.objects.create(
            titulo="Diaria de prueba", tipo=Mission.Tipo.DIARIA,
            definicion_terminada="Hecha", xp=30,
        )
        missions.completar_mision(diaria, fecha=LUNES)
        assert services.xp_dentro_del_techo(LUNES) == 30
