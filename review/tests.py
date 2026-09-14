import datetime as dt
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from business.models import Client, Deal, Invoice, Project
from core.models import Profile
from review import services
from review.forms import WeeklyReviewForm
from review.models import HealthLog, WeeklyReview

DOMINGO = dt.date(2026, 9, 13)
LUNES = dt.date(2026, 9, 7)


@pytest.fixture
def cliente(db):
    return Client.objects.create(nombre="Felycampo", slug="felycampo", mrr=Decimal("249"))


@pytest.mark.django_db
class TestSemaforo:
    @pytest.mark.parametrize(
        "clave,valor,esperado",
        [
            ("m1_eur_cobrados", 1200, "verde"),
            ("m1_eur_cobrados", 800, "ambar"),
            ("m1_eur_cobrados", 300, "rojo"),
            ("m2_eur_recurrentes", 450, "verde"),
            ("m4_contactos_nuevos", 6, "verde"),
            ("m4_contactos_nuevos", 4, "ambar"),
            ("m4_contactos_nuevos", 0, "rojo"),
            ("m7_tarifa_efectiva", 65, "verde"),
            ("m7_tarifa_efectiva", 20, "rojo"),
            # En estas, menos es mejor.
            ("m3_eur_vencidos", 0, "verde"),
            ("m8_wip_abierto", 2, "verde"),
            ("m8_wip_abierto", 3, "ambar"),
            ("m8_wip_abierto", 5, "rojo"),
        ],
    )
    def test_colores(self, clave, valor, esperado):
        assert services.semaforo(clave, valor) == esperado


@pytest.mark.django_db
class TestMetricasCalculadas:
    def test_se_calculan_solas(self, cliente):
        Invoice.objects.create(
            client=cliente, concepto="Web", importe=Decimal("1000"),
            fecha_emision=LUNES, vencimiento=LUNES, cobrada=True,
            fecha_cobro=timezone.localdate(),
        )
        Deal.objects.create(
            negocio="Gimnasio", estado=Deal.Estado.PROPUESTA, valor_potencial=Decimal("1800"),
            fecha_primer_contacto=timezone.localdate(), ultimo_toque=timezone.localdate(),
        )
        Project.objects.create(client=cliente, nombre="Web", precio=Decimal("2000"))

        metricas = services.metricas_calculadas()
        assert metricas["m1_eur_cobrados"] == Decimal("1000")
        assert metricas["m2_eur_recurrentes"] == Decimal("249")
        assert metricas["m4_contactos_nuevos"] == 1
        assert metricas["m5_propuestas"] == 1
        assert metricas["m6_precio_medio"] == Decimal("1800.00")
        assert metricas["m8_wip_abierto"] == 1

    def test_el_peso_y_los_entrenos_salen_del_registro_de_salud(self):
        # Dos días de la misma semana ISO: lunes 7 y martes 8 de septiembre de 2026.
        HealthLog.objects.create(fecha=LUNES, peso=Decimal("80.0"), entreno=True)
        HealthLog.objects.create(fecha=LUNES + dt.timedelta(days=1), peso=Decimal("81.0"), entreno=True)
        sugerencias = services.sugerencias_manuales(LUNES)
        assert sugerencias["m9_entrenos"] == 2
        assert sugerencias["m9_peso_medio"] == Decimal("80.50")

    def test_el_formulario_llega_prerelleno(self, client, cliente):
        Deal.objects.create(negocio="Gimnasio", fecha_primer_contacto=timezone.localdate())
        respuesta = client.get(reverse("review:index"))
        assert respuesta.status_code == 200
        form = respuesta.context["form"]
        assert form.initial["m2_eur_recurrentes"] == Decimal("249")
        assert form.initial["m4_contactos_nuevos"] == 1

    def test_las_calculadas_son_de_solo_lectura(self, client):
        form = client.get(reverse("review:index")).context["form"]
        assert form.fields["m1_eur_cobrados"].widget.attrs["readonly"] is True
        assert "readonly" not in form.fields["m9_entrenos"].widget.attrs


@pytest.mark.django_db
class TestGuardarRevision:
    def _datos(self, **extra):
        datos = {
            "anio": 2026, "semana_iso": 37, "fecha": "2026-09-13",
            "m1_eur_cobrados": "1200", "m2_eur_recurrentes": "450", "m3_eur_vencidos": "0",
            "m4_contactos_nuevos": 6, "m5_conversaciones": 2, "m5_propuestas": 1,
            "m6_precio_medio": "1800", "m7_tarifa_efectiva": "55", "m8_wip_abierto": 2,
            "m9_entrenos": 4, "xp_semana": 620,
            "m8_revision_hecha": "on", "m10_bloques_intactos": "on",
            "funciono": "El recurrente", "no_funciono": "El pipeline al entregar",
            "decision": "No aceptar nada por debajo de 1.500 €",
            "objetivo_1": "Cobrar Felycampo", "objetivo_2": "6 contactos", "objetivo_3": "Caso nº1",
        }
        datos.update(extra)
        return datos

    def test_cerrar_la_revision_concede_60_xp(self):
        antes = Profile.get().xp_total
        form = WeeklyReviewForm(self._datos())
        assert form.is_valid(), form.errors
        services.guardar_revision(form)
        assert Profile.get().xp_total == antes + services.XP_REVISION

    def test_guardarla_dos_veces_no_puntua_dos_veces(self):
        form = WeeklyReviewForm(self._datos())
        assert form.is_valid(), form.errors
        revision = services.guardar_revision(form)
        antes = Profile.get().xp_total
        form2 = WeeklyReviewForm(self._datos(), instance=revision)
        assert form2.is_valid(), form2.errors
        services.guardar_revision(form2)
        assert Profile.get().xp_total == antes

    def test_un_borrador_sin_cerrar_no_puntua(self):
        antes = Profile.get().xp_total
        datos = self._datos()
        del datos["m8_revision_hecha"]
        form = WeeklyReviewForm(datos)
        assert form.is_valid(), form.errors
        services.guardar_revision(form)
        assert Profile.get().xp_total == antes

    def test_no_se_cierra_sin_decision(self):
        form = WeeklyReviewForm(self._datos(decision="  "))
        assert not form.is_valid()
        assert "decision" in form.errors


@pytest.mark.django_db
class TestHistorico:
    def _revision(self, semana, **extra):
        datos = {
            "anio": 2026, "semana_iso": semana, "fecha": LUNES,
            "m1_eur_cobrados": Decimal("1000"), "m8_wip_abierto": 2,
            "m8_revision_hecha": True,
        }
        datos.update(extra)
        return WeeklyReview.objects.create(**datos)

    def test_flechas_de_tendencia(self):
        self._revision(36, m1_eur_cobrados=Decimal("1000"), m8_wip_abierto=2)
        self._revision(37, m1_eur_cobrados=Decimal("1500"), m8_wip_abierto=3)
        filas = services.historico()["filas"]
        ultima = filas[0]  # la 37, la más reciente
        cobrados = ultima["celdas"][0]
        wip = ultima["celdas"][6]
        assert cobrados["tendencia"] == "mejor"   # 1.000 -> 1.500, más es mejor
        assert wip["tendencia"] == "peor"         # 2 -> 3, menos es mejor

    def test_la_primera_revision_no_tiene_con_que_comparar(self):
        self._revision(37)
        assert services.historico()["filas"][0]["celdas"][0]["tendencia"] == ""


@pytest.mark.django_db
class TestRecordatorio:
    def test_el_domingo_sin_revision_deja_aviso(self):
        aviso = services.aviso_revision_pendiente(DOMINGO)
        assert aviso is not None and aviso["semana"] == 37

    def test_entre_semana_no_hay_aviso(self):
        assert services.aviso_revision_pendiente(LUNES) is None

    def test_con_la_revision_cerrada_no_hay_aviso(self):
        WeeklyReview.objects.create(
            anio=2026, semana_iso=37, fecha=DOMINGO, m8_revision_hecha=True
        )
        assert services.aviso_revision_pendiente(DOMINGO) is None

    def test_el_comando_crea_el_borrador_con_las_metricas(self, cliente):
        salida = StringIO()
        call_command("recordatorio_revision", fecha="2026-09-13", stdout=salida)
        borrador = services.revision_de_la_semana(DOMINGO)
        assert borrador is not None
        assert borrador.m8_revision_hecha is False
        assert borrador.m2_eur_recurrentes == Decimal("249")
        assert "pendiente" in salida.getvalue()

    def test_el_comando_no_hace_nada_entre_semana(self):
        salida = StringIO()
        call_command("recordatorio_revision", fecha="2026-09-07", stdout=salida)
        assert WeeklyReview.objects.count() == 0
        assert "no es domingo" in salida.getvalue()

    def test_el_comando_es_idempotente(self):
        call_command("recordatorio_revision", fecha="2026-09-13", stdout=StringIO())
        call_command("recordatorio_revision", fecha="2026-09-13", stdout=StringIO())
        assert WeeklyReview.objects.count() == 1
