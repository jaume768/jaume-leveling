import datetime as dt
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from business.models import Client, Deal, Invoice, Project
from wisdom import services
from wisdom.models import Maxim

HOY = timezone.localdate


@pytest.fixture
def cliente(db):
    return Client.objects.create(nombre="Felycampo", slug="felycampo")


def _cobrada(cliente, importe, dias=5):
    hoy = HOY()
    return Invoice.objects.create(
        client=cliente, concepto="Trabajo", importe=Decimal(importe),
        fecha_emision=hoy - dt.timedelta(days=dias + 30),
        vencimiento=hoy - dt.timedelta(days=dias),
        cobrada=True, fecha_cobro=hoy - dt.timedelta(days=dias),
    )


@pytest.mark.django_db
class TestMaximaDelDia:
    def test_el_mismo_dia_da_siempre_la_misma(self):
        fecha = dt.date(2026, 9, 14)
        assert services.maxima_del_dia(fecha) == services.maxima_del_dia(fecha)

    def test_no_repite_hasta_agotar_el_ciclo(self):
        total = Maxim.objects.count()
        inicio = dt.date(2026, 1, 1)
        vistas = [
            services.maxima_del_dia(inicio + dt.timedelta(days=i)).numero for i in range(total)
        ]
        assert len(set(vistas)) == total

    def test_el_ciclo_vuelve_a_empezar_despues(self):
        total = Maxim.objects.count()
        inicio = dt.date(2026, 1, 1)
        assert services.maxima_del_dia(inicio) == services.maxima_del_dia(
            inicio + dt.timedelta(days=total)
        )


@pytest.mark.django_db
class TestMaximaContextual:
    def test_sin_nada_roto_devuelve_la_del_dia(self, cliente):
        # Un pipeline vacío ya es algo roto, así que hace falta un contacto.
        Deal.objects.create(negocio="Gimnasio", fecha_primer_contacto=HOY())
        consejo = services.maxima_contextual()
        assert consejo["contextual"] is False
        assert consejo["maxima"] == services.maxima_del_dia()

    def test_una_factura_vencida_trae_el_libro_viii(self, cliente):
        Invoice.objects.create(
            client=cliente, concepto="Web", importe=Decimal("2000"),
            fecha_emision=HOY() - dt.timedelta(days=40),
            vencimiento=HOY() - dt.timedelta(days=18),
        )
        consejo = services.maxima_contextual()
        assert consejo["maxima"].libro == "Libro VIII"
        assert "18 días" in consejo["motivo"]

    def test_un_proyecto_por_debajo_del_suelo_trae_el_libro_iii(self, cliente):
        Project.objects.create(
            client=cliente, nombre="Web barata", precio=Decimal("800"), estado="ACTIVO"
        )
        consejo = services.maxima_contextual()
        assert consejo["maxima"].libro == "Libro III"
        assert "800" in consejo["motivo"]

    def test_un_cliente_por_encima_del_35_trae_el_libro_ii(self, cliente):
        otro = Client.objects.create(nombre="Artà", slug="arta")
        _cobrada(cliente, "8000")
        _cobrada(otro, "1000")
        # Un contacto de esta semana para que no salte la regla del pipeline.
        Deal.objects.create(negocio="Gimnasio", fecha_primer_contacto=HOY())
        consejo = services.maxima_contextual()
        assert consejo["maxima"].libro == "Libro II"
        assert "Felycampo" in consejo["motivo"]

    def test_un_reparto_sano_no_dispara_el_libro_ii(self, cliente):
        # Con dos clientes al 50% la regla salta igual: por debajo del 35% hacen
        # falta tres o más.
        segundo = Client.objects.create(nombre="Artà", slug="arta")
        tercero = Client.objects.create(nombre="Gruas", slug="gruas")
        _cobrada(cliente, "2000")
        _cobrada(segundo, "2000")
        _cobrada(tercero, "2000")
        Deal.objects.create(negocio="Gimnasio", fecha_primer_contacto=HOY())
        assert services.maxima_contextual()["contextual"] is False

    def test_una_semana_sin_contactos_trae_el_libro_i(self):
        consejo = services.maxima_contextual()
        assert consejo["maxima"].libro == "Libro I"
        assert "0 contactos" in consejo["motivo"]

    def test_con_contactos_la_semana_no_salta_el_libro_i(self):
        Deal.objects.create(negocio="Gimnasio", fecha_primer_contacto=HOY())
        assert services.maxima_contextual()["contextual"] is False

    def test_el_dinero_parado_manda_sobre_todo_lo_demas(self, cliente):
        # Con factura vencida y proyecto barato a la vez, gana el Libro VIII.
        Invoice.objects.create(
            client=cliente, concepto="Web", importe=Decimal("2000"),
            fecha_emision=HOY() - dt.timedelta(days=40),
            vencimiento=HOY() - dt.timedelta(days=18),
        )
        Project.objects.create(
            client=cliente, nombre="Barata", precio=Decimal("800"), estado="ACTIVO"
        )
        assert services.maxima_contextual()["maxima"].libro == "Libro VIII"


@pytest.mark.django_db
class TestVistaMaximas:
    def test_la_vista_carga_las_22(self, client):
        respuesta = client.get(reverse("wisdom:index"))
        assert respuesta.status_code == 200
        assert len(respuesta.context["maximas"]) == 22

    def test_el_filtro_por_tag_reduce_la_lista(self, client):
        respuesta = client.get(reverse("wisdom:index"), {"tag": "cobro"})
        maximas = list(respuesta.context["maximas"])
        assert maximas
        assert all("cobro" in m.tags for m in maximas)

    def test_los_diez_libros_estan_cargados(self):
        libros = Maxim.objects.filter(numero__lte=10)
        assert libros.count() == 10
        assert all(m.principio and m.texto and m.aplicacion for m in libros)

    def test_el_decalogo_tiene_sus_doce_reglas(self):
        assert Maxim.objects.filter(numero__gt=10).count() == 12

    def test_todas_tienen_al_menos_un_tag_conocido(self):
        for maxima in Maxim.objects.all():
            tags = [t.strip() for t in maxima.tags.split(",")]
            assert any(t in services.TAGS for t in tags), maxima.titulo
