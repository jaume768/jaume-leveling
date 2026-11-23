import datetime as dt
import random

import pytest
from django.urls import reverse

from cazador import services
from cazador.models import Aviso, Cofre, Escudo, Logro
from missions.models import Mission, MissionLog

# Semana del sistema: lunes 7/9/2026. Miercoles 9 y domingo 13 son protegidos.
LUNES = dt.date(2026, 9, 7)
MARTES = LUNES + dt.timedelta(days=1)
JUEVES = LUNES + dt.timedelta(days=3)
VIERNES = LUNES + dt.timedelta(days=4)
SABADO = LUNES + dt.timedelta(days=5)


def _accion(fecha):
    mision = Mission.objects.get(slug="accion-comercial")
    MissionLog.objects.update_or_create(mission=mision, fecha=fecha, defaults={"completada": True})


@pytest.mark.django_db
class TestRangosDeCazador:
    def test_los_seis_rangos_tienen_letra_y_clase(self):
        from core.models import Rank

        letras = [r.cazador["letra"] for r in Rank.objects.order_by("orden")]
        assert letras == ["E", "D", "C", "B", "A", "S"]
        clases = [r.cazador["clase"] for r in Rank.objects.order_by("orden")]
        assert clases == ["Despertado", "Cazador", "Asesino", "Invocador", "Rompecadenas", "Monarca"]

    def test_un_orden_desconocido_no_tiene_clase(self):
        assert services.rango_cazador(99) == {}


@pytest.mark.django_db
class TestRachaYEscudos:
    def test_un_escudo_usado_salva_el_dia(self):
        from progression import services as progression

        _accion(LUNES)
        _accion(JUEVES)
        # El martes se fallo: sin escudo la racha del jueves es 1.
        assert progression.racha_actual(JUEVES) == 1
        Escudo.objects.create(motivo="prueba", usado_en=MARTES)
        assert progression.racha_actual(JUEVES) == 2

    def test_cerrar_un_dia_fallado_gasta_el_escudo(self):
        _accion(LUNES)
        Escudo.objects.create(motivo="prueba")
        services.cerrar_dia(MARTES)
        assert Escudo.objects.get().usado_en == MARTES
        # Idempotente: cerrar otra vez no gasta nada mas.
        services.cerrar_dia(MARTES)
        assert Escudo.objects.filter(usado_en__isnull=False).count() == 1

    def test_sin_racha_previa_no_se_gasta_escudo(self):
        Escudo.objects.create(motivo="prueba")
        services.cerrar_dia(MARTES)
        assert Escudo.objects.get().usado_en is None

    def test_semana_perfecta_da_un_escudo(self):
        for dia in (LUNES, MARTES, JUEVES, VIERNES, SABADO):
            _accion(dia)
        services.cerrar_dia(SABADO)
        assert services.escudos_disponibles() == 1
        services.cerrar_dia(SABADO)
        assert services.escudos_disponibles() == 1

    def test_nunca_mas_de_dos_escudos(self):
        for n in range(4):
            services.ganar_escudo(f"motivo {n}")
        assert services.escudos_disponibles() == services.MAX_ESCUDOS

    def test_cadena_marca_hechos_fallados_y_protegidos(self):
        from core.models import Profile

        perfil = Profile.get()
        perfil.fecha_inicio = LUNES - dt.timedelta(days=30)
        perfil.save()
        _accion(LUNES)
        cadena = services.cadena_de_dias(VIERNES, semanas=1)
        estados = [d["estado"] for d in cadena[0]]
        assert estados[:5] == ["hecho", "fallado", "protegido", "fallado", "hoy"]
        assert estados[5:] == ["futuro", "futuro"]

    def test_la_cadena_crece_desde_la_semana_del_arranque(self):
        from core.models import Profile

        perfil = Profile.get()
        perfil.fecha_inicio = LUNES - dt.timedelta(days=12)  # dos semanas antes
        perfil.save()
        assert len(services.cadena_de_dias(VIERNES, semanas=6)) == 3
        perfil.fecha_inicio = LUNES
        perfil.save()
        assert len(services.cadena_de_dias(VIERNES, semanas=6)) == 1

    def test_antes_del_arranque_no_hay_dias_fallados(self):
        from core.models import Profile

        perfil = Profile.get()
        perfil.fecha_inicio = JUEVES
        perfil.save()
        cadena = services.cadena_de_dias(VIERNES, semanas=1)
        estados = [d["estado"] for d in cadena[0]]
        assert estados[:3] == ["previo", "previo", "previo"]
        assert estados[3] == "fallado"


@pytest.mark.django_db
class TestCofre:
    def test_abrir_sin_cofre_no_hace_nada(self):
        assert services.abrir_cofre(LUNES) is None

    def test_el_cofre_se_abre_una_vez(self):
        Cofre.objects.create(fecha=LUNES)
        cofre = services.abrir_cofre(LUNES, rng=random.Random(1))
        assert cofre.abierto and cofre.titulo
        assert services.abrir_cofre(LUNES) is None

    def test_cinco_fragmentos_forjan_un_escudo(self):
        from cazador.models import Cazador

        ficha = Cazador.get()
        ficha.fragmentos = 4
        ficha.save()
        Cofre.objects.create(fecha=LUNES)

        class SoloFragmentos(random.Random):
            def choices(self, poblacion, weights=None, k=1):
                return ["fragmento"]

        services.abrir_cofre(LUNES, rng=SoloFragmentos())
        assert services.escudos_disponibles() == 1
        assert Cazador.get().fragmentos == 0


@pytest.mark.django_db
class TestLogrosYAvisos:
    def test_el_primer_titulo_se_gana_solo(self):
        services.revisar_logros()
        assert Logro.objects.filter(tipo=Logro.Tipo.TITULO, clave="el-que-despierta").exists()
        assert Aviso.objects.filter(tipo=Aviso.Tipo.TITULO).exists()

    def test_los_logros_no_se_duplican(self):
        services.revisar_logros()
        total = Logro.objects.count()
        services.revisar_logros()
        assert Logro.objects.count() == total

    def test_las_claves_de_titulo_son_unicas_y_hay_muchos(self):
        claves = [t["clave"] for t in services.TITULOS]
        assert len(claves) == len(set(claves))
        assert len(claves) >= 30

    def test_todas_las_condiciones_se_evaluan_sin_error(self):
        for logro in services.TITULOS + services.HABILIDADES:
            assert logro["cond"]() in (True, False), logro["clave"]

    def test_un_escudo_salvador_da_segunda_oportunidad(self):
        Escudo.objects.create(motivo="prueba", usado_en=MARTES)
        services.revisar_logros()
        assert Logro.objects.filter(clave="segunda-oportunidad").exists()

    def test_equipar_un_titulo_bloqueado_falla(self):
        with pytest.raises(ValueError):
            services.equipar_titulo("inquebrantable")

    def test_ganar_xp_crea_un_aviso(self):
        from progression import services as progression

        progression.registrar_xp("accion-comercial", xp=30, fecha=LUNES)
        assert Aviso.objects.filter(tipo=Aviso.Tipo.XP, valor=30).exists()

    def test_subir_de_nivel_avisa(self):
        from core.models import Profile
        from progression import services as progression

        perfil = Profile.get()
        progression.registrar_xp("dinero-cobrado", xp=2500, fecha=LUNES, aplicar_racha=False)
        if Profile.get().nivel > perfil.nivel:
            assert Aviso.objects.filter(tipo=Aviso.Tipo.NIVEL).exists()

    def test_los_avisos_se_pintan_una_vez(self, client):
        services.avisar(Aviso.Tipo.SISTEMA, "Hola", "prueba")
        primera = client.get(reverse("cazador:avisos")).content.decode()
        assert "Hola" in primera
        segunda = client.get(reverse("cazador:avisos")).content.decode()
        assert "Hola" not in segunda

    def test_el_middleware_avisa_por_htmx(self, client):
        services.avisar(Aviso.Tipo.SISTEMA, "Algo", "")
        respuesta = client.get(reverse("missions:bloque"), HTTP_HX_REQUEST="true")
        assert "avisos" in respuesta.headers.get("HX-Trigger", "")


@pytest.mark.django_db
class TestPantallas:
    def test_hoy_estado_y_gremio_responden(self, client):
        for nombre in ("core:index", "core:personaje", "business:index", "core:niveles"):
            assert client.get(reverse(nombre)).status_code == 200, nombre

    def test_estado_muestra_titulos_y_habilidades(self, client):
        contenido = client.get(reverse("core:personaje")).content.decode()
        assert "Títulos" in contenido and "Habilidades" in contenido
        assert "Ejército de sombras" in contenido

    def test_sin_claves_vapid_no_se_envia_nada(self, settings):
        settings.VAPID_PUBLIC_KEY = ""
        settings.VAPID_PRIVATE_KEY = ""
        assert services.enviar_push("t", "c") == 0


@pytest.mark.django_db
class TestHitosDeAtributo:
    def test_el_primer_escalon_es_el_siguiente_10_de_siempre(self):
        from core.models import Attribute

        from cazador import hitos

        for atributo in Attribute.objects.all():
            escalera = hitos.ESCALERAS[atributo.slug]
            assert escalera[0][0] == atributo.siguiente_hito, atributo.slug

    def test_un_hito_con_evidencia_sube_10_y_pasa_al_siguiente(self):
        from core.models import Attribute

        from cazador import hitos

        antes = Attribute.objects.get(slug="red-profesional")
        hitos.reclamar_hito("red-profesional", "Lista de 15 dueños en el cuaderno, 20/11.")
        despues = Attribute.objects.get(slug="red-profesional")
        assert despues.valor == antes.valor + 10
        assert despues.siguiente_hito == hitos.ESCALERAS["red-profesional"][1][0]
        assert despues.registros.count() >= 1

    def test_sin_evidencia_no_se_reclama(self):
        from cazador import hitos

        with pytest.raises(ValueError):
            hitos.reclamar_hito("red-profesional", "")

    def test_un_hito_medible_sin_cumplir_no_se_reclama(self):
        from cazador import hitos

        with pytest.raises(ValueError):
            hitos.reclamar_hito("organizacion")

    def test_un_hito_medible_cumplido_avisa_y_se_reclama(self):
        from core.models import Attribute

        from cazador import hitos

        mision = Mission.objects.get(slug="revision-semanal")
        domingo = dt.date(2026, 9, 13)
        for semana in range(8):
            MissionLog.objects.create(mission=mision, fecha=domingo - dt.timedelta(weeks=semana), completada=True)
        assert "Organización" in " ".join(hitos.revisar_hitos()) or Aviso.objects.filter(
            clave__startswith="hito-listo:organizacion").exists()
        antes = Attribute.objects.get(slug="organizacion").valor
        hitos.reclamar_hito("organizacion")
        assert Attribute.objects.get(slug="organizacion").valor == antes + 10

    def test_estado_pinta_el_hito(self, client):
        contenido = client.get(reverse("core:personaje")).content.decode()
        assert "Hito 1 de" in contenido


@pytest.mark.django_db
class TestPortales:
    def test_se_ofrecen_tres_una_vez_por_semana(self):
        from cazador import portales

        primera = portales.abrir_portales(LUNES)
        segunda = portales.abrir_portales(JUEVES)
        assert len(primera) == 3
        assert {p.pk for p in primera} == {p.pk for p in segunda}
        assert sorted(p.dificultad for p in primera) == ["A", "C", "E"]

    def test_entrar_descarta_los_otros_y_solo_una_vez(self):
        from cazador import portales
        from cazador.models import Portal

        ofrecidos = portales.abrir_portales(LUNES)
        portales.entrar(ofrecidos[0].pk, LUNES)
        estados = sorted(Portal.objects.values_list("estado", flat=True))
        assert estados.count("DESCARTADO") == 2
        with pytest.raises(ValueError):
            portales.entrar(ofrecidos[1].pk, LUNES)

    def test_se_supera_con_datos_reales_y_da_botin(self):
        from cazador import portales
        from cazador.models import Cazador, Portal

        portal = Portal.objects.create(lunes=LUNES, dificultad="E", tipo="racha", titulo="t",
                                       descripcion="d", objetivo=2, estado=Portal.Estado.ABIERTO)
        _accion(LUNES)
        _accion(MARTES)
        portales.revisar(MARTES)
        portal.refresh_from_db()
        assert portal.estado == Portal.Estado.SUPERADO
        assert Cazador.get().fragmentos == 1

    def test_sin_cumplir_se_desborda_al_acabar_la_semana(self):
        from cazador import portales
        from cazador.models import Portal

        portal = Portal.objects.create(lunes=LUNES, dificultad="A", tipo="racha", titulo="t",
                                       descripcion="d", objetivo=5, estado=Portal.Estado.ABIERTO)
        portales.revisar(LUNES + dt.timedelta(days=8))
        portal.refresh_from_db()
        assert portal.estado == Portal.Estado.DESBORDADO

    def test_hoy_muestra_los_portales(self, client):
        contenido = client.get(reverse("core:index")).content.decode()
        assert "Portales de la semana" in contenido


@pytest.mark.django_db
class TestCodiceYRetratos:
    def test_el_codice_tiene_las_frases_nuevas(self):
        from wisdom.models import Maxim

        assert Maxim.objects.count() >= 75

    def test_las_frases_de_hoy_rotan_pero_no_cambian_al_recargar(self):
        assert services.frases_del_codice(LUNES) == services.frases_del_codice(LUNES)
        assert len(services.frases_del_codice(LUNES)) == 14

    def test_los_retratos_por_rango_existen(self):
        for orden in (3, 4, 5, 6):
            assert services.retrato_de_rango(orden) == f"img/retratos/rango-{orden}.webp"
            assert services.retrato_mini_de_rango(orden) == f"img/retratos/rango-{orden}-mini.webp"
        assert services.retrato_de_rango(2) == "img/personaje.webp"

    def test_la_galeria_bloquea_los_rangos_no_alcanzados(self):
        galeria = services.galeria_de_retratos(2)
        assert [g["letra"] for g in galeria] == ["D", "C", "B", "A", "S"]
        assert [g["desbloqueado"] for g in galeria] == [True, False, False, False, False]
