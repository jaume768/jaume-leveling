import datetime as dt
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from business import services
from business.forms import ProjectForm
from business.models import Client, Deal, Invoice, Project
from core.models import Profile
from missions.models import MissionLog
from progression.models import Penalty, XPEvent

LUNES = dt.date(2026, 9, 7)


@pytest.fixture
def cliente(db):
    return Client.objects.create(nombre="Felycampo", slug="felycampo", mrr=Decimal("249"))


def _deal(**extra):
    datos = {"negocio": "Gruas Perelló", "estado": Deal.Estado.CONVERSANDO}
    datos.update(extra)
    return Deal.objects.create(**datos)


def _factura(cliente, importe="2000", **extra):
    hoy = timezone.localdate()
    datos = {
        "client": cliente,
        "concepto": "Web",
        "importe": Decimal(importe),
        "fecha_emision": hoy - dt.timedelta(days=30),
        "vencimiento": hoy - dt.timedelta(days=1),
    }
    datos.update(extra)
    return Invoice.objects.create(**datos)


@pytest.mark.django_db
class TestResaltado:
    @pytest.mark.parametrize(
        "dias,esperado",
        [(0, ""), (4, ""), (5, "ambar"), (6, "ambar"), (7, "rojo"), (30, "rojo"), (None, "")],
    )
    def test_niveles_de_alerta(self, dias, esperado):
        assert services.nivel_alerta(dias) == esperado

    def test_la_fila_del_pipeline_lleva_su_alerta(self):
        hoy = timezone.localdate()
        _deal(negocio="Frío", ultimo_toque=hoy - dt.timedelta(days=9))
        _deal(negocio="Tibio", ultimo_toque=hoy - dt.timedelta(days=5))
        _deal(negocio="Al día", ultimo_toque=hoy)
        alertas = {f["deal"].negocio: f["alerta"] for f in services.filas_pipeline()}
        assert alertas == {"Frío": "rojo", "Tibio": "ambar", "Al día": ""}


@pytest.mark.django_db
class TestToqueRapido:
    def test_actualiza_ultimo_toque_y_concede_xp(self):
        deal = _deal(ultimo_toque=timezone.localdate() - dt.timedelta(days=10))
        antes = Profile.get().xp_total
        services.toque_rapido(deal)
        deal.refresh_from_db()
        assert deal.ultimo_toque == timezone.localdate()
        assert deal.dias_sin_toque == 0
        assert Profile.get().xp_total == antes + 30

    def test_cuenta_para_la_racha_via_la_mision_diaria(self):
        services.toque_rapido(_deal())
        assert MissionLog.objects.filter(
            completada=True, mission__tipo="DIARIA", mission__orden=1
        ).exists()

    def test_el_segundo_toque_del_dia_no_puntua_dos_veces(self):
        services.toque_rapido(_deal(negocio="Uno"))
        antes = Profile.get().xp_total
        services.toque_rapido(_deal(negocio="Dos"))
        assert Profile.get().xp_total == antes


@pytest.mark.django_db
class TestCobros:
    def test_marcar_cobrada_concede_1_xp_por_cada_10_euros(self, cliente):
        factura = _factura(cliente, "2000")
        antes = Profile.get().xp_total
        services.marcar_cobrada(factura)
        factura.refresh_from_db()
        assert factura.cobrada and factura.fecha_cobro == timezone.localdate()
        assert Profile.get().xp_total == antes + 200

    def test_el_tope_semanal_de_cobro_son_400_xp(self, cliente):
        antes = Profile.get().xp_total
        services.marcar_cobrada(_factura(cliente, "3000"))  # 300 XP
        services.marcar_cobrada(_factura(cliente, "3000"))  # tope: solo 100 mas
        assert Profile.get().xp_total == antes + 400
        assert XPEvent.objects.filter(accion_slug="dinero-cobrado", tope_aplicado=True).exists()

    def test_una_factura_ya_cobrada_no_vuelve_a_puntuar(self, cliente):
        factura = _factura(cliente, "1000")
        services.marcar_cobrada(factura)
        antes = Profile.get().xp_total
        services.marcar_cobrada(factura)
        assert Profile.get().xp_total == antes
        assert XPEvent.objects.filter(accion_slug="dinero-cobrado").count() == 1

    def test_totales_del_mes(self, cliente):
        _factura(cliente, "1000", cobrada=True, fecha_cobro=timezone.localdate())
        _factura(cliente, "500")
        resumen = services.resumen_facturas()
        assert resumen["cobrado_mes"] == Decimal("1000")
        assert resumen["pendiente_total"] == Decimal("500")
        assert resumen["importe_vencido"] == Decimal("500")


@pytest.mark.django_db
class TestClientesYProyectos:
    def test_recurrente_frente_al_objetivo(self, cliente):
        Client.objects.create(nombre="Artà", slug="arta", mrr=Decimal("139"))
        resumen = services.resumen_clientes()
        assert resumen["total_mrr"] == Decimal("388")
        assert resumen["objetivo"] == Decimal("450")
        assert resumen["falta"] == Decimal("62")

    def test_tarifa_efectiva_de_un_proyecto(self, cliente):
        proyecto = Project.objects.create(
            client=cliente, nombre="Web", precio=Decimal("2000"), horas_reales=Decimal("25")
        )
        assert proyecto.tarifa_efectiva == Decimal("80.00")

    def test_tarifa_efectiva_sin_horas_es_none(self, cliente):
        proyecto = Project.objects.create(client=cliente, nombre="Web", precio=Decimal("2000"))
        assert proyecto.tarifa_efectiva is None

    def test_tarifa_efectiva_del_mes(self, cliente):
        Project.objects.create(
            client=cliente, nombre="Web", precio=Decimal("2000"),
            horas_reales=Decimal("20"), estado=Project.Estado.ACTIVO,
        )
        _factura(cliente, "1000", cobrada=True, fecha_cobro=timezone.localdate())
        assert services.tarifa_efectiva_mes() == Decimal("50.00")


@pytest.mark.django_db
class TestSueloDePrecio:
    def _datos(self, cliente, precio, **extra):
        datos = {
            "client": cliente.pk,
            "nombre": "Web barata",
            "precio": precio,
            "horas_estimadas": "20",
            "horas_reales": "0",
            "estado": "ACTIVO",
            "fecha_inicio": "2026-09-07",
        }
        datos.update(extra)
        return datos

    def test_por_encima_del_suelo_se_guarda_sin_friccion(self, cliente):
        form = ProjectForm(self._datos(cliente, "2000"))
        assert form.is_valid(), form.errors
        assert form.hay_excepcion is False

    def test_por_debajo_del_suelo_exige_marcar_la_excepcion(self, cliente):
        form = ProjectForm(self._datos(cliente, "800"))
        assert not form.is_valid()
        assert "excepcion_justificada" in form.errors

    def test_la_excepcion_sin_motivo_no_vale(self, cliente):
        form = ProjectForm(self._datos(cliente, "800", excepcion_justificada="on"))
        assert not form.is_valid()
        assert "motivo_excepcion" in form.errors

    def test_con_excepcion_y_motivo_se_guarda(self, cliente):
        form = ProjectForm(
            self._datos(
                cliente, "800", excepcion_justificada="on",
                motivo_excepcion="Cliente que trae tres referidos firmados",
            )
        )
        assert form.is_valid(), form.errors
        assert form.hay_excepcion is True

    def test_la_excepcion_cuesta_250_xp_y_queda_documentada(self, cliente):
        proyecto = Project.objects.create(client=cliente, nombre="Web barata", precio=Decimal("800"))
        antes = Profile.get().xp_total
        services.registrar_excepcion_de_suelo(proyecto, "Trae tres referidos")
        assert Profile.get().xp_total == antes - 250
        penalizacion = Penalty.objects.get(regla_slug="proyecto-por-debajo-del-suelo")
        assert penalizacion.correccion_exigida == "Trae tres referidos"

    def test_la_penalizacion_no_la_multiplica_la_racha(self, cliente):
        # Con racha alta, -250 sigue siendo -250.
        for i in range(6):
            services.toque_rapido(_deal(negocio=f"Contacto {i}"), fecha=LUNES + dt.timedelta(days=i))
        proyecto = Project.objects.create(client=cliente, nombre="Barata", precio=Decimal("800"))
        antes = Profile.get().xp_total
        services.registrar_excepcion_de_suelo(proyecto, "motivo")
        assert Profile.get().xp_total == antes - 250


@pytest.mark.django_db
class TestVistas:
    @pytest.mark.parametrize(
        "nombre", ["business:pipeline", "business:facturas", "business:clientes", "business:proyectos"]
    )
    def test_las_vistas_cargan(self, client, nombre):
        assert client.get(reverse(nombre)).status_code == 200

    def test_el_filtro_por_estado_reduce_la_tabla(self, client):
        # Nombres que no coincidan con las etiquetas de los filtros.
        _deal(negocio="Empresa Uno", estado=Deal.Estado.GANADO)
        _deal(negocio="Empresa Dos", estado=Deal.Estado.CONTACTADO)
        respuesta = client.get(reverse("business:pipeline"), {"estado": "GANADO"})
        assert b"Empresa Uno" in respuesta.content
        assert b"Empresa Dos" not in respuesta.content

    def test_el_pipeline_se_ordena_por_fecha_del_proximo_paso(self, client):
        hoy = timezone.localdate()
        _deal(negocio="Tarde", fecha_proximo_paso=hoy + dt.timedelta(days=10))
        _deal(negocio="Pronto", fecha_proximo_paso=hoy + dt.timedelta(days=1))
        _deal(negocio="Sin fecha")
        orden = [f["deal"].negocio for f in services.filas_pipeline()]
        assert orden == ["Pronto", "Tarde", "Sin fecha"]

    def test_toque_por_htmx_devuelve_solo_la_fila(self, client):
        deal = _deal()
        respuesta = client.post(reverse("business:deal_toque", args=[deal.pk]))
        assert respuesta.status_code == 200
        assert f'id="deal-{deal.pk}"'.encode() in respuesta.content
        assert b"<html" not in respuesta.content

    def test_edicion_en_linea_guarda_el_proximo_paso(self, client):
        deal = _deal()
        respuesta = client.post(
            reverse("business:deal_guardar", args=[deal.pk]),
            {"estado": Deal.Estado.PROPUESTA, "proximo_paso": "Llamar el jueves", "fecha_proximo_paso": ""},
        )
        assert respuesta.status_code == 200
        deal.refresh_from_db()
        assert deal.estado == Deal.Estado.PROPUESTA
        assert deal.proximo_paso == "Llamar el jueves"

    def test_no_se_marca_como_perdido_sin_motivo(self, client):
        deal = _deal()
        client.post(
            reverse("business:deal_guardar", args=[deal.pk]),
            {"estado": Deal.Estado.PERDIDO, "proximo_paso": "", "fecha_proximo_paso": ""},
        )
        deal.refresh_from_db()
        assert deal.estado != Deal.Estado.PERDIDO

    def test_cobrar_por_htmx_devuelve_el_bloque_con_totales(self, client, cliente):
        factura = _factura(cliente, "1000")
        respuesta = client.post(reverse("business:factura_cobrar", args=[factura.pk]))
        assert respuesta.status_code == 200
        assert b'id="facturas"' in respuesta.content
        factura.refresh_from_db()
        assert factura.cobrada

    def test_el_formulario_avisa_del_suelo_al_cambiar_el_precio(self, client, cliente):
        respuesta = client.post(
            reverse("business:proyecto_nuevo"),
            {"client": cliente.pk, "nombre": "Web", "precio": "800"},
            headers={"HX-Request": "true"},
        )
        assert respuesta.status_code == 200
        assert "por debajo del suelo".encode() in respuesta.content
        # Es un aviso, no un rechazo: no se han marcado errores de campos vacíos.
        assert "Este campo es obligatorio".encode() not in respuesta.content

    def test_el_dashboard_muestra_la_tarifa_efectiva(self, client):
        respuesta = client.get(reverse("core:index"))
        assert "métrica maestra".encode() in respuesta.content
