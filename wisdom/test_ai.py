"""Tests de la capa de IA. Nunca se llama a la API real: el SDK se simula."""
import datetime as dt
import json
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.urls import reverse
from django.utils import timezone

from business.models import Client, Deal, Invoice
from wisdom import ai, services
from wisdom.models import AdviceSession, SystemPrompt

HOY = dt.date(2026, 9, 14)


class RespuestaFalsa:
    """Imita lo justo de la respuesta del SDK."""

    def __init__(self, texto="Cobra Felycampo hoy. 15 minutos."):
        self.content = [SimpleNamespace(type="text", text=texto)]
        self.model = "claude-sonnet-5"
        self.usage = SimpleNamespace(input_tokens=1500, output_tokens=300)


@pytest.fixture
def ia_simulada(monkeypatch):
    """Sustituye la llamada al SDK y deja ver con qué se ha llamado."""
    llamadas = []

    def falso_preguntar(self, system, mensaje):
        llamadas.append({"system": system, "mensaje": mensaje, "modelo": self.modelo})
        respuesta = RespuestaFalsa()
        return ai.RespuestaIA(
            texto=respuesta.content[0].text,
            modelo=respuesta.model,
            tokens_in=respuesta.usage.input_tokens,
            tokens_out=respuesta.usage.output_tokens,
            coste=ai.coste_estimado(respuesta.model, 1500, 300),
        )

    monkeypatch.setattr(ai.ClienteIA, "preguntar", falso_preguntar)
    return llamadas


class TestCoste:
    def test_sonnet_5(self):
        # 1.500 entrada a 2 $/M + 300 salida a 10 $/M = 0,006 $ -> 0,0055 EUR
        assert ai.coste_estimado("claude-sonnet-5", 1500, 300) == Decimal("0.0055")

    def test_opus_5_cuesta_mas(self):
        assert ai.coste_estimado("claude-opus-5", 1500, 300) > ai.coste_estimado(
            "claude-sonnet-5", 1500, 300
        )

    def test_un_modelo_desconocido_no_revienta(self):
        assert ai.coste_estimado("modelo-inventado", 1000, 100) > 0


class TestCliente:
    def test_sin_clave_no_esta_configurado(self, settings):
        settings.ANTHROPIC_API_KEY = ""
        assert ai.ClienteIA().configurado is False

    def test_sin_clave_lanza_error_claro(self, settings):
        settings.ANTHROPIC_API_KEY = ""
        with pytest.raises(ai.IANoConfigurada) as exc:
            ai.ClienteIA().preguntar("system", "hola")
        assert "ANTHROPIC_API_KEY" in str(exc.value)

    def test_el_modelo_por_defecto_es_sonnet_5(self, settings):
        settings.ANTHROPIC_MODEL = ""
        assert ai.ClienteIA().modelo == "claude-sonnet-5"

    def test_el_modelo_se_lee_del_entorno(self, settings):
        settings.ANTHROPIC_MODEL = "claude-opus-5"
        assert ai.ClienteIA().modelo == "claude-opus-5"


@pytest.mark.django_db
class TestContexto:
    def test_trae_lo_que_tiene_que_traer(self):
        cliente = Client.objects.create(nombre="Felycampo", slug="felycampo", mrr=Decimal("249"))
        Invoice.objects.create(
            client=cliente, concepto="Web", importe=Decimal("2000"),
            fecha_emision=HOY - dt.timedelta(days=40), vencimiento=HOY - dt.timedelta(days=18),
        )
        Deal.objects.create(negocio="Gimnasio", fecha_primer_contacto=HOY)

        contexto = ai.construir_contexto(HOY)
        for clave in (
            "nivel", "rango", "jefe_activo", "xp_semana", "racha_dias",
            "misiones_pendientes_hoy", "pipeline_por_estado", "deals_sin_seguimiento",
            "facturas", "recurrente", "tarifa_efectiva_mes", "ultimas_revisiones", "alertas",
        ):
            assert clave in contexto, clave
        assert contexto["facturas"]["vencido"] == 2000.0
        assert contexto["recurrente"] == {"actual": 249.0, "objetivo": 450.0}
        assert contexto["nivel"] == 45

    def test_es_serializable_y_compacto(self):
        contexto = ai.construir_contexto(HOY)
        texto = json.dumps(contexto, ensure_ascii=False)
        # ~4 caracteres por token: el contexto debe caber de sobra en 2.000.
        assert len(texto) / 4 < 2000, f"{len(texto) // 4} tokens estimados"

    def test_construir_contexto_no_escribe_nada(self):
        from core.models import Profile

        Profile.get()  # el perfil ya existe antes de medir
        antes = (AdviceSession.objects.count(), Deal.objects.count(), Profile.objects.count())
        ai.construir_contexto(HOY)
        assert (AdviceSession.objects.count(), Deal.objects.count(), Profile.objects.count()) == antes


@pytest.mark.django_db
class TestConsultar:
    def test_guarda_la_sesion_con_tokens_y_coste(self, ia_simulada, settings):
        settings.ANTHROPIC_API_KEY = "test"
        sesion, error = services.consultar("¿Qué hago ahora mismo?")
        assert error == ""
        assert sesion.tokens_in == 1500 and sesion.tokens_out == 300
        assert sesion.coste_estimado == Decimal("0.0055")
        assert sesion.modelo == "claude-sonnet-5"
        assert sesion.system_prompt.slug == "consejo"
        assert sesion.contexto_json["nivel"] == 45

    def test_usa_el_prompt_versionado_de_la_base_de_datos(self, ia_simulada, settings):
        settings.ANTHROPIC_API_KEY = "test"
        SystemPrompt.objects.create(
            slug="consejo", version=2, nombre="v2", contenido="PROMPT NUEVO", activo=True
        )
        services.consultar("hola")
        assert ia_simulada[-1]["system"] == "PROMPT NUEVO"

    def test_inyecta_el_contexto_en_el_mensaje(self, ia_simulada, settings):
        settings.ANTHROPIC_API_KEY = "test"
        services.consultar("¿Subo el precio?")
        mensaje = ia_simulada[-1]["mensaje"]
        assert "CONTEXTO DEL SISTEMA" in mensaje
        assert "¿Subo el precio?" in mensaje
        assert '"nivel": 45' in mensaje

    def test_sin_prompt_activo_devuelve_aviso(self, ia_simulada, settings):
        settings.ANTHROPIC_API_KEY = "test"
        SystemPrompt.objects.update(activo=False)
        sesion, error = services.consultar("hola")
        assert sesion is None and "prompt de sistema" in error

    def test_una_pregunta_vacia_no_llama_a_la_api(self, ia_simulada, settings):
        settings.ANTHROPIC_API_KEY = "test"
        sesion, error = services.consultar("   ")
        assert sesion is None and error
        assert ia_simulada == []

    def test_si_la_api_falla_no_se_guarda_nada(self, monkeypatch, settings):
        settings.ANTHROPIC_API_KEY = "test"

        def revienta(self, system, mensaje):
            raise ai.IAError("La API ha respondido con un error 529.")

        monkeypatch.setattr(ai.ClienteIA, "preguntar", revienta)
        sesion, error = services.consultar("hola")
        assert sesion is None
        assert "529" in error
        assert AdviceSession.objects.count() == 0

    def test_sin_clave_la_app_sigue_funcionando(self, settings):
        settings.ANTHROPIC_API_KEY = ""
        sesion, error = services.consultar("hola")
        assert sesion is None
        assert "ANTHROPIC_API_KEY" in error


@pytest.mark.django_db
class TestGasto:
    def test_suma_el_mes_en_curso(self, ia_simulada, settings):
        settings.ANTHROPIC_API_KEY = "test"
        services.consultar("una")
        services.consultar("dos")
        gasto = services.gasto_del_mes()
        assert gasto["consultas"] == 2
        assert gasto["total"] == Decimal("0.0110")
        assert gasto["tokens_in"] == 3000

    def test_no_cuenta_meses_anteriores(self, ia_simulada, settings):
        settings.ANTHROPIC_API_KEY = "test"
        sesion, _ = services.consultar("una")
        AdviceSession.objects.filter(pk=sesion.pk).update(
            fecha=timezone.now() - dt.timedelta(days=70)
        )
        assert services.gasto_del_mes()["consultas"] == 0


@pytest.mark.django_db
class TestVistas:
    def test_el_consejo_carga_sin_clave_configurada(self, client, settings):
        settings.ANTHROPIC_API_KEY = ""
        respuesta = client.get(reverse("wisdom:index"))
        assert respuesta.status_code == 200
        assert respuesta.context["ia_configurada"] is False
        assert "Falta la clave".encode() in respuesta.content

    def test_preguntar_sin_clave_avisa_pero_no_rompe(self, client, settings):
        settings.ANTHROPIC_API_KEY = ""
        respuesta = client.post(reverse("wisdom:index"), {"pregunta": "hola"})
        assert respuesta.status_code == 200
        assert "no está disponible".encode() in respuesta.content

    def test_las_consultas_predefinidas_funcionan(self, client, ia_simulada, settings):
        settings.ANTHROPIC_API_KEY = "test"
        client.post(reverse("wisdom:index"), {"consulta": "ahora"})
        assert "tres acciones" in ia_simulada[-1]["mensaje"]

    def test_criticar_propuesta_exige_el_texto(self, client, ia_simulada, settings):
        settings.ANTHROPIC_API_KEY = "test"
        respuesta = client.post(reverse("wisdom:index"), {"consulta": "propuesta", "texto": "  "})
        assert "Pega la propuesta".encode() in respuesta.content
        assert ia_simulada == []

    def test_criticar_propuesta_adjunta_el_texto(self, client, ia_simulada, settings):
        settings.ANTHROPIC_API_KEY = "test"
        client.post(
            reverse("wisdom:index"),
            {"consulta": "propuesta", "texto": "Web por 900 € en dos semanas"},
        )
        assert "900 €" in ia_simulada[-1]["mensaje"]

    def test_htmx_devuelve_solo_el_fragmento(self, client, ia_simulada, settings):
        settings.ANTHROPIC_API_KEY = "test"
        respuesta = client.post(
            reverse("wisdom:index"), {"consulta": "ahora"}, headers={"HX-Request": "true"}
        )
        assert b'id="conversacion"' in respuesta.content
        assert b"<html" not in respuesta.content

    def test_la_vista_de_gasto_carga(self, client):
        assert client.get(reverse("wisdom:gasto")).status_code == 200


@pytest.mark.django_db
class TestLaClaveNoSeFiltra:
    """La clave de la API no puede salir por pantalla, por el error ni por el log."""

    CLAVE = "sk-ant-clave-de-prueba-que-no-debe-aparecer"

    def test_no_llega_a_la_pagina(self, client, settings):
        settings.ANTHROPIC_API_KEY = self.CLAVE
        contenido = client.get(reverse("wisdom:index")).content.decode()
        assert self.CLAVE not in contenido
        assert "sk-ant" not in contenido

    def test_la_vista_solo_recibe_un_booleano(self, client, settings):
        settings.ANTHROPIC_API_KEY = self.CLAVE
        contexto = client.get(reverse("wisdom:index")).context
        assert contexto["ia_configurada"] is True
        assert self.CLAVE not in str(contexto)

    def test_no_aparece_en_el_mensaje_de_error(self, monkeypatch, settings):
        settings.ANTHROPIC_API_KEY = self.CLAVE

        def revienta(self, system, mensaje):
            raise ai.IAError("La API ha respondido con un error 401.")

        monkeypatch.setattr(ai.ClienteIA, "preguntar", revienta)
        _, error = services.consultar("hola")
        assert self.CLAVE not in error

    def test_no_entra_en_el_contexto_que_se_manda_al_modelo(self, settings):
        settings.ANTHROPIC_API_KEY = self.CLAVE
        assert self.CLAVE not in json.dumps(ai.construir_contexto(HOY))

    def test_no_se_guarda_en_la_sesion(self, ia_simulada, settings):
        settings.ANTHROPIC_API_KEY = self.CLAVE
        sesion, _ = services.consultar("hola")
        assert self.CLAVE not in json.dumps(sesion.contexto_json)
        assert self.CLAVE not in sesion.pregunta + sesion.respuesta

    def test_django_la_oculta_en_los_informes_de_error(self, settings):
        from django.views.debug import SafeExceptionReporterFilter

        settings.ANTHROPIC_API_KEY = self.CLAVE
        ajustes = SafeExceptionReporterFilter().get_safe_settings()
        assert ajustes["ANTHROPIC_API_KEY"] != self.CLAVE
        assert ajustes["SECRET_KEY"] != settings.SECRET_KEY


class TestHigieneDelRepositorio:
    """Comprobaciones que no dependen de la base de datos."""

    @staticmethod
    def _raiz():
        from pathlib import Path

        return Path(__file__).resolve().parent.parent

    def test_el_env_esta_ignorado_por_git(self):
        contenido = (self._raiz() / ".gitignore").read_text()
        assert "\n.env\n" in f"\n{contenido}"

    def test_el_env_esta_excluido_de_la_imagen(self):
        contenido = (self._raiz() / ".dockerignore").read_text()
        assert ".env" in contenido

    def test_no_hay_ninguna_clave_en_el_codigo(self):
        import re

        patron = re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}")
        sospechosos = []
        for ruta in self._raiz().rglob("*"):
            if not ruta.is_file() or ruta.suffix not in {".py", ".html", ".yml", ".sh", ".md", ".txt"}:
                continue
            if ".git" in ruta.parts or ruta.name == "test_ai.py":
                continue
            if patron.search(ruta.read_text(errors="ignore")):
                sospechosos.append(str(ruta))
        assert not sospechosos, f"Posibles claves en: {sospechosos}"

    def test_el_dockerfile_no_hornea_la_clave(self):
        contenido = (self._raiz() / "Dockerfile").read_text()
        assert "ANTHROPIC_API_KEY" not in contenido
        assert "ARG SECRET" not in contenido
