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


# --- Presentacion del panel: codigos y grupos --------------------------------


@pytest.mark.parametrize(
    "titulo, esperado",
    [
        ("D1 · Acción comercial", ("D1", "Acción comercial")),
        ("S4 · Revisión semanal (domingo 20:15)", ("S4", "Revisión semanal (domingo 20:15)")),
        # Sin codigo delante: el titulo se queda entero.
        ("Cobro y Cierre", ("", "Cobro y Cierre")),
        # Separador sin nada detras: tampoco hay codigo.
        ("Renta ·", ("", "Renta ·")),
    ],
)
def test_partir_titulo_separa_el_codigo(titulo, esperado):
    assert services.partir_titulo(titulo) == esperado


@pytest.mark.django_db
def test_agrupar_filas_ordena_por_periodicidad_y_cuenta_lo_hecho():
    diaria = Mission.objects.create(
        titulo="D1 · Acción comercial",
        tipo=Mission.Tipo.DIARIA,
        definicion_terminada="Un mensaje enviado.",
        xp=30,
    )
    semanal = Mission.objects.create(
        titulo="S1 · 6 contactos acumulados",
        tipo=Mission.Tipo.SEMANAL,
        definicion_terminada="Seis contactos.",
        xp=100,
    )
    filas = [
        {"mision": semanal, "completada": False},
        {"mision": diaria, "completada": True},
    ]

    grupos = services.agrupar_filas(filas)

    # Las diarias van primero aunque llegaran despues en la lista.
    assert [g["titulo"] for g in grupos] == ["Diarias", "Semanales"]
    assert (grupos[0]["hechas"], grupos[0]["total"]) == (1, 1)
    assert (grupos[1]["hechas"], grupos[1]["total"]) == (0, 1)


def test_agrupar_filas_omite_los_grupos_vacios():
    assert services.agrupar_filas([]) == []


# --- Guia operativa de cada mision -------------------------------------------


@pytest.mark.django_db
def test_guia_de_usa_la_guia_escrita_del_codigo():
    mision = Mission.objects.create(
        titulo="D1 · Acción comercial",
        tipo=Mission.Tipo.DIARIA,
        definicion_terminada="Enviado y anotado en el pipeline",
        xp=30,
    )
    guia = services.guia_de(mision)

    assert guia["generica"] is False
    assert len(guia["pasos"]) >= 3
    # D1 tiene atajo (el dia minimo) y una trampa documentada.
    assert guia["atajo"]
    assert guia["no_cuenta"]


@pytest.mark.django_db
def test_guia_de_encuentra_las_principales_por_titulo():
    mision = Mission.objects.create(
        titulo="Renta",
        tipo=Mission.Tipo.PRINCIPAL,
        definicion_terminada="450 EUR/mes firmados",
        xp=900,
    )
    assert services.guia_de(mision)["generica"] is False


@pytest.mark.django_db
def test_guia_de_cae_en_una_generica_cuando_no_hay_escrita():
    mision = Mission.objects.create(
        titulo="X9 · Misión inventada",
        tipo=Mission.Tipo.SEMANAL,
        descripcion="Hacer algo.",
        definicion_terminada="Hecho",
        motivo="Porque sí.",
        xp=10,
        evidencia_requerida=True,
    )
    guia = services.guia_de(mision)

    assert guia["generica"] is True
    # La generica se construye con los campos de la propia mision.
    assert "Hacer algo." in guia["pasos"]
    assert any("evidencia" in paso.lower() for paso in guia["pasos"])
    assert guia["nota"] == "Porque sí."


@pytest.mark.django_db
def test_detalle_de_mision_trae_codigo_titulo_y_estado():
    mision = Mission.objects.create(
        titulo="S4 · Revisión semanal",
        tipo=Mission.Tipo.SEMANAL,
        definicion_terminada="Panel actualizado",
        xp=60,
    )
    detalle = services.detalle_de_mision(mision)

    assert detalle["codigo"] == "S4"
    assert detalle["titulo"] == "Revisión semanal"
    assert detalle["completada"] is False
    assert detalle["guia"]["pasos"]


@pytest.mark.django_db
def test_el_detalle_se_sirve_por_htmx_y_explica_como_hacerla(client):
    mision = Mission.objects.create(
        titulo="D1 · Acción comercial",
        tipo=Mission.Tipo.DIARIA,
        definicion_terminada="Enviado y anotado en el pipeline",
        xp=30,
    )
    respuesta = client.get(reverse("missions:detalle", args=[mision.pk]))

    assert respuesta.status_code == 200
    assert "Cómo hacerlo".encode() in respuesta.content
    # Sin ?accion=1 no se ofrece completar: no hay bloque de misiones detras.
    assert "Ir al panel para hacerla".encode() in respuesta.content


@pytest.mark.django_db
def test_el_detalle_desde_el_panel_si_deja_completar(client):
    mision = Mission.objects.create(
        titulo="D2 · Cierre del día",
        tipo=Mission.Tipo.DIARIA,
        definicion_terminada="Anotadas",
        xp=15,
    )
    respuesta = client.get(reverse("missions:detalle", args=[mision.pk]), {"accion": "1"})

    assert "Ir al panel para hacerla".encode() not in respuesta.content
    assert "bloque-misiones".encode() in respuesta.content


# --- Escalado por rango y misiones de medio plazo ----------------------------


@pytest.mark.django_db
class TestEscaladoPorRango:
    """Las principales aparecen con su rango y se retiran al superarlo."""

    def _perfil_en(self, orden: int):
        from core.models import Profile, Rank

        rango = Rank.objects.get(orden=orden)
        perfil = Profile.get()
        perfil.nivel = rango.nivel_min
        perfil.rango = rango
        perfil.save()
        return rango

    def _principales_visibles(self, fecha=LUNES):
        return {
            m.titulo
            for m in services.misiones_de_hoy(fecha)
            if m.tipo == Mission.Tipo.PRINCIPAL
        }

    def test_en_operador_solo_se_ven_sus_dos_principales(self):
        self._perfil_en(2)
        assert self._principales_visibles() == {"Cobro y Cierre", "Renta"}

    def test_en_especialista_cambian_las_principales(self):
        self._perfil_en(3)
        visibles = self._principales_visibles()
        assert visibles == {"El Suelo", "Vertical"}
        # Las del rango anterior se retiran: ya no son tu problema.
        assert "Cobro y Cierre" not in visibles

    def test_multiplicador_esta_bloqueada_hasta_constructor(self):
        self._perfil_en(3)
        assert "Multiplicador" not in self._principales_visibles()
        self._perfil_en(4)
        assert "Multiplicador" in self._principales_visibles()

    def test_las_diarias_no_dependen_del_rango(self):
        for orden in (2, 3, 4):
            self._perfil_en(orden)
            diarias = {
                m.titulo
                for m in services.misiones_de_hoy(LUNES)
                if m.tipo == Mission.Tipo.DIARIA
            }
            assert len(diarias) == 2, f"rango {orden}: {diarias}"

    def test_una_principal_cerrada_no_vuelve_nunca(self):
        self._perfil_en(2)
        renta = Mission.objects.get(titulo="Renta")
        MissionLog.objects.create(
            mission=renta, fecha=LUNES - dt.timedelta(days=200), completada=True
        )
        assert "Renta" not in self._principales_visibles()
        assert "Cobro y Cierre" in self._principales_visibles()


@pytest.mark.django_db
class TestMisionesMensuales:
    def _mensuales(self, fecha=LUNES):
        return {
            m.titulo
            for m in services.misiones_de_hoy(fecha)
            if m.tipo == Mission.Tipo.MENSUAL
        }

    def test_las_mensuales_salen_en_el_panel(self):
        assert len(self._mensuales()) == 5

    def test_una_mensual_cerrada_desaparece_ese_mes(self):
        m1 = Mission.objects.get(titulo="M1 · 2 propuestas formales enviadas")
        MissionLog.objects.create(mission=m1, fecha=LUNES, completada=True)
        assert m1.titulo not in self._mensuales()

    def test_pero_vuelve_al_mes_siguiente(self):
        m1 = Mission.objects.get(titulo="M1 · 2 propuestas formales enviadas")
        # Cerrada en agosto: en septiembre vuelve a tocar.
        MissionLog.objects.create(
            mission=m1, fecha=dt.date(2026, 8, 10), completada=True
        )
        assert m1.titulo in self._mensuales(dt.date(2026, 9, 7))


@pytest.mark.django_db
def test_el_marcador_del_panel_solo_cuenta_el_ritmo_del_dia():
    """Mensuales y principales no deben hundir el porcentaje del dia."""
    panel = services.panel_de_misiones(LUNES)

    # 2 diarias + 6 semanales, aunque en pantalla haya cuatro grupos.
    assert panel["total"] == 8
    titulos = [g["titulo"] for g in panel["grupos"]]
    assert titulos == ["Diarias", "Semanales", "Mensuales", "Principales"]


# --- Cuaderno del cierre del día ---------------------------------------------


@pytest.fixture
def d2(db):
    """El cierre del día: la misión que se hace escribiendo."""
    return Mission.objects.get(titulo__startswith="D2 · ")


@pytest.mark.django_db
class TestCuaderno:
    def test_el_cierre_del_dia_pide_notas(self, d2):
        assert d2.pide_notas is True
        assert d2.etiqueta_notas == "Las dos tareas de mañana"

    def test_la_accion_comercial_no_pide_notas(self, d1):
        assert d1.pide_notas is False

    def test_guardar_notas_no_completa_ni_da_xp(self, d2):
        antes = Profile.get().xp_total
        registro = services.guardar_notas(d2, "1. Llamar\n2. Escribir", fecha=LUNES)
        assert registro.notas == "1. Llamar\n2. Escribir"
        assert registro.completada is False
        assert Profile.get().xp_total == antes
        assert not XPEvent.objects.exists()

    def test_completar_guarda_las_notas_y_da_la_xp(self, d2):
        antes = Profile.get().xp_total
        registro = services.completar_mision(d2, notas="1. Llamar\n2. Escribir", fecha=LUNES)
        assert registro.completada is True
        assert registro.notas == "1. Llamar\n2. Escribir"
        assert Profile.get().xp_total == antes + d2.xp

    def test_se_puede_apuntar_primero_y_completar_despues(self, d2):
        services.guardar_notas(d2, "borrador", fecha=LUNES)
        registro = services.completar_mision(d2, notas="1. Llamar\n2. Escribir", fecha=LUNES)
        assert registro.completada is True
        assert registro.notas == "1. Llamar\n2. Escribir"
        assert MissionLog.objects.filter(mission=d2, fecha=LUNES).count() == 1

    def test_editar_despues_de_completada_no_vuelve_a_puntuar(self, d2):
        services.completar_mision(d2, notas="primera versión", fecha=LUNES)
        antes = Profile.get().xp_total
        services.completar_mision(d2, notas="versión corregida", fecha=LUNES)
        registro = MissionLog.objects.get(mission=d2, fecha=LUNES)
        assert registro.notas == "versión corregida"
        assert Profile.get().xp_total == antes
        assert XPEvent.objects.filter(objeto_relacionado=f"mission:{d2.pk}").count() == 1

    def test_completar_sin_notas_no_borra_lo_ya_escrito(self, d2):
        services.guardar_notas(d2, "lo de antes", fecha=LUNES)
        registro = services.completar_mision(d2, fecha=LUNES)
        assert registro.notas == "lo de antes"

    def test_las_notas_se_recortan(self, d2):
        assert services.guardar_notas(d2, "   con espacios   ", fecha=LUNES).notas == "con espacios"

    def test_ultimas_notas_devuelve_el_dia_anterior_con_algo_escrito(self, d2):
        services.guardar_notas(d2, "lo del lunes", fecha=LUNES)
        anteriores = services.ultimas_notas(d2, fecha=LUNES + dt.timedelta(days=1))
        assert anteriores is not None
        assert anteriores.notas == "lo del lunes"
        assert anteriores.fecha == LUNES

    def test_ultimas_notas_ignora_los_dias_en_blanco(self, d2):
        services.guardar_notas(d2, "lo del lunes", fecha=LUNES)
        services.guardar_notas(d2, "", fecha=LUNES + dt.timedelta(days=1))
        anteriores = services.ultimas_notas(d2, fecha=LUNES + dt.timedelta(days=2))
        assert anteriores.fecha == LUNES

    def test_ultimas_notas_no_mira_el_futuro(self, d2):
        services.guardar_notas(d2, "lo de hoy", fecha=LUNES)
        assert services.ultimas_notas(d2, fecha=LUNES) is None

    def test_el_panel_trae_lo_apuntado_hoy_y_lo_de_ayer(self, d2):
        services.guardar_notas(d2, "lo del lunes", fecha=LUNES)
        martes = LUNES + dt.timedelta(days=1)
        services.guardar_notas(d2, "lo del martes", fecha=martes)

        fila = next(
            f for f in services.panel_de_misiones(martes)["filas"] if f["mision"].pk == d2.pk
        )
        assert fila["notas"] == "lo del martes"
        assert fila["anteriores"].notas == "lo del lunes"

    def test_las_misiones_normales_no_arrastran_notas_anteriores(self, d1):
        fila = next(
            f for f in services.panel_de_misiones(LUNES)["filas"] if f["mision"].pk == d1.pk
        )
        assert fila["anteriores"] is None


@pytest.mark.django_db
class TestCuadernoHTMX:
    def test_el_modal_se_abre_con_lo_ya_escrito(self, client, d2):
        services.guardar_notas(d2, "1. Llamar")
        respuesta = client.get(reverse("missions:notas", args=[d2.pk]))
        assert respuesta.status_code == 200
        assert b"1. Llamar" in respuesta.content
        assert "Las dos tareas de mañana".encode() in respuesta.content

    def test_guardar_por_htmx_devuelve_el_bloque(self, client, d2):
        respuesta = client.post(
            reverse("missions:notas", args=[d2.pk]), {"notas": "1. Llamar\n2. Escribir"}
        )
        assert respuesta.status_code == 200
        assert b'id="bloque-misiones"' in respuesta.content
        assert b"<html" not in respuesta.content
        assert services.notas_de(d2) == "1. Llamar\n2. Escribir"
        assert not services.esta_completada(d2)

    def test_guardar_y_completar_en_la_misma_accion(self, client, d2):
        respuesta = client.post(
            reverse("missions:notas", args=[d2.pk]),
            {"notas": "1. Llamar\n2. Escribir", "completar": "1"},
        )
        assert respuesta.status_code == 200
        assert services.esta_completada(d2)
        assert services.notas_de(d2) == "1. Llamar\n2. Escribir"

    def test_el_panel_pinta_lo_apuntado(self, client, d2):
        services.guardar_notas(d2, "1. Llamar a Gruas")
        contenido = client.get(reverse("core:index")).content.decode()
        assert "Apuntado hoy" in contenido
        assert "1. Llamar a Gruas" in contenido

    def test_la_casilla_del_cierre_abre_el_cuaderno(self, client, d2):
        contenido = client.get(reverse("core:index")).content.decode()
        assert reverse("missions:notas", args=[d2.pk]) in contenido


# --- Identidad de las misiones y variantes -----------------------------------


@pytest.mark.django_db
class TestIdentidadDeMision:
    """El título y el orden son presentación; el slug es identidad."""

    def test_la_accion_comercial_esta_marcada_para_la_racha(self):
        marcadas = set(
            Mission.objects.filter(cuenta_para_racha=True).values_list("slug", flat=True)
        )
        assert marcadas == {"accion-comercial", "accion-comercial-minima"}

    def test_reordenar_desde_el_admin_no_cambia_la_racha(self, d1):
        """Antes la racha se deducía de (tipo, orden) y esto la rompía."""
        services.completar_mision(d1, evidencia="contacto", fecha=LUNES)
        assert progression.racha_actual(LUNES) == 1

        # Se reordena y se reescribe el enunciado, como en el admin.
        d1.orden = 9
        d1.titulo = "D9 · Otro nombre para lo mismo"
        d1.save()

        assert progression.racha_actual(LUNES) == 1

    def test_otra_diaria_de_orden_1_no_cuenta_para_la_racha(self, db):
        """Antes, cualquier diaria con orden 1 mantenía la racha."""
        impostora = Mission.objects.create(
            titulo="Leer el correo", tipo=Mission.Tipo.DIARIA, orden=1,
            definicion_terminada="Leído", xp=5,
        )
        services.completar_mision(impostora, fecha=LUNES)

        assert impostora.cuenta_para_racha is False
        assert progression.racha_actual(LUNES) == 0

    def test_el_slug_se_deriva_del_titulo_si_no_se_da(self, db):
        mision = Mission.objects.create(
            titulo="Z9 · Misión de prueba", tipo=Mission.Tipo.DIARIA,
            definicion_terminada="Hecha", xp=5,
        )
        assert mision.slug == "z9-mision-de-prueba"

    def test_dos_misiones_con_el_mismo_titulo_no_chocan(self, db):
        datos = dict(tipo=Mission.Tipo.DIARIA, definicion_terminada="Hecha", xp=5)
        a = Mission.objects.create(titulo="Repetida", **datos)
        b = Mission.objects.create(titulo="Repetida", **datos)
        assert (a.slug, b.slug) == ("repetida", "repetida-2")

    def test_la_semana_de_reinicio_se_identifica_por_slug(self, db):
        from missions.services import MISIONES_DE_REINICIO

        assert set(MISIONES_DE_REINICIO) <= set(
            Mission.objects.values_list("slug", flat=True)
        )


@pytest.mark.django_db
class TestVariantesDelMismoGrupo:
    """La versión mínima mantiene la racha, pero no es una segunda fuente de XP."""

    @pytest.fixture
    def d1_minima(self, db):
        return Mission.objects.get(slug="accion-comercial-minima")

    @pytest.fixture
    def d2_minima(self, db):
        return Mission.objects.get(slug="cierre-del-dia-minima")

    def test_comparten_grupo(self, d1, d1_minima):
        assert d1.grupo == d1_minima.grupo == "accion-comercial"

    def test_la_minima_mantiene_la_racha(self, d1_minima):
        services.completar_mision(d1_minima, evidencia="tres líneas", fecha=LUNES)
        assert progression.racha_actual(LUNES) == 1

    def test_no_se_puede_completar_la_normal_despues_de_la_minima(self, d1, d1_minima):
        services.completar_mision(d1_minima, evidencia="tres líneas", fecha=LUNES)
        antes = Profile.get().xp_total

        with pytest.raises(services.VarianteYaCompletada):
            services.completar_mision(d1, evidencia="contacto", fecha=LUNES)

        assert Profile.get().xp_total == antes
        assert XPEvent.objects.filter(fecha=LUNES).count() == 1

    def test_ni_al_reves(self, d1, d1_minima):
        services.completar_mision(d1, evidencia="contacto", fecha=LUNES)
        antes = Profile.get().xp_total

        with pytest.raises(services.VarianteYaCompletada):
            services.completar_mision(d1_minima, evidencia="tres líneas", fecha=LUNES)

        assert Profile.get().xp_total == antes

    def test_lo_mismo_con_el_cierre_del_dia(self, d2, d2_minima):
        services.completar_mision(d2, notas="1. y 2.", fecha=LUNES)
        with pytest.raises(services.VarianteYaCompletada):
            services.completar_mision(d2_minima, fecha=LUNES)

    def test_al_dia_siguiente_se_puede_elegir_la_otra(self, d1, d1_minima):
        services.completar_mision(d1, evidencia="contacto", fecha=LUNES)
        martes = LUNES + dt.timedelta(days=1)
        registro = services.completar_mision(d1_minima, evidencia="tres líneas", fecha=martes)
        assert registro.completada

    def test_el_panel_deja_de_ofrecer_la_hermana(self, d1, d1_minima):
        services.completar_mision(d1_minima, evidencia="tres líneas", fecha=LUNES)
        panel = services.panel_de_misiones(LUNES, minimo=True)
        ofrecidas = {f["mision"].slug for f in panel["filas"]}
        assert "accion-comercial-minima" in ofrecidas
        assert "accion-comercial" not in ofrecidas

    def test_la_vista_avisa_en_vez_de_reventar(self, client, d1, d1_minima):
        services.completar_mision(d1_minima, evidencia="tres líneas")
        respuesta = client.post(
            reverse("missions:completar", args=[d1.pk]), {"evidencia": "contacto"}
        )
        assert respuesta.status_code == 200
        assert "solo cuenta una vez".encode() in respuesta.content

    def test_el_toque_rapido_no_revienta_si_ya_se_hizo_la_minima(self, d1_minima):
        from business import services as negocio
        from business.models import Deal

        services.completar_mision(d1_minima, evidencia="tres líneas")
        deal = Deal.objects.create(negocio="Gimnasio")
        antes = Profile.get().xp_total

        negocio.toque_rapido(deal)

        deal.refresh_from_db()
        assert deal.ultimo_toque == timezone.localdate()
        assert Profile.get().xp_total == antes


# --- Catálogo de misiones ----------------------------------------------------


@pytest.mark.django_db
class TestCatalogoDeMisiones:
    """La pantalla de misiones: orden por periodicidad, no por alfabeto."""

    def test_los_grupos_van_en_orden_de_periodicidad(self):
        catalogo = services.catalogo_de_misiones(LUNES)
        assert [g["titulo"] for g in catalogo["grupos"]] == [
            "Diarias", "Semanales", "Mensuales", "Principales",
        ]

    def test_ordenar_por_el_valor_del_tipo_daba_otro_orden(self):
        """El fallo original: 'MENSUAL' va antes que 'SEMANAL' alfabéticamente."""
        alfabetico = list(
            Mission.objects.filter(activa=True)
            .order_by("tipo")
            .values_list("tipo", flat=True)
            .distinct()
        )
        assert alfabetico.index("MENSUAL") < alfabetico.index("SEMANAL")

        real = [g["tipo"] for g in services.catalogo_de_misiones(LUNES)["grupos"]]
        assert real.index("SEMANAL") < real.index("MENSUAL")

    def test_la_variante_minima_va_detras_de_su_version_normal(self):
        diarias = services.catalogo_de_misiones(LUNES)["grupos"][0]["filas"]
        slugs = [f["mision"].slug for f in diarias]
        assert slugs.index("accion-comercial") < slugs.index("accion-comercial-minima")

    def test_cada_grupo_lleva_su_recuento(self):
        for grupo in services.catalogo_de_misiones(LUNES)["grupos"]:
            assert grupo["total"] == len(grupo["filas"])
            assert 0 <= grupo["hechas"] <= grupo["total"]

    def test_una_diaria_cuenta_como_hecha_solo_el_dia_que_se_hizo(self, d1):
        services.completar_mision(d1, evidencia="contacto", fecha=LUNES)

        hoy = {f["mision"].pk: f["completada"] for g in services.catalogo_de_misiones(LUNES)["grupos"] for f in g["filas"]}
        assert hoy[d1.pk] is True

        martes = LUNES + dt.timedelta(days=1)
        manana = {f["mision"].pk: f["completada"] for g in services.catalogo_de_misiones(martes)["grupos"] for f in g["filas"]}
        assert manana[d1.pk] is False

    def test_una_semanal_cuenta_hecha_toda_la_semana(self, db):
        semanal = Mission.objects.get(slug="entregable-visible")
        services.completar_mision(semanal, fecha=LUNES)

        viernes = LUNES + dt.timedelta(days=4)
        filas = {f["mision"].pk: f["completada"] for g in services.catalogo_de_misiones(viernes)["grupos"] for f in g["filas"]}
        assert filas[semanal.pk] is True

    def test_las_bloqueadas_por_rango_se_marcan_pero_se_ven(self):
        catalogo = services.catalogo_de_misiones(LUNES)
        filas = [f for g in catalogo["grupos"] for f in g["filas"]]
        bloqueadas = [f for f in filas if not f["disponible"]]

        assert bloqueadas, "Con rango Operador debería haber misiones de rangos superiores"
        for fila in bloqueadas:
            assert fila["motivo"]

    def test_el_filtro_deja_un_solo_grupo(self):
        catalogo = services.catalogo_de_misiones(LUNES, tipo="SEMANAL")
        assert [g["tipo"] for g in catalogo["grupos"]] == ["SEMANAL"]

    def test_el_filtro_no_falsea_los_recuentos_de_las_pestanas(self):
        completo = services.catalogo_de_misiones(LUNES)
        filtrado = services.catalogo_de_misiones(LUNES, tipo="SEMANAL")
        assert filtrado["pestanas"] == completo["pestanas"]
        assert filtrado["total"] == completo["total"]


@pytest.mark.django_db
class TestPantallaDeMisiones:
    def test_la_pantalla_carga_con_los_grupos_en_orden(self, client):
        """Se buscan los subtítulos: son únicos de cada cabecera de grupo."""
        contenido = client.get(reverse("missions:index")).content.decode()
        posiciones = [
            contenido.index("Haz lo esencial"),
            contenido.index("Construye resultados"),
            contenido.index("El mes se gana"),
            contenido.index("Cierran tu rango"),
        ]
        assert posiciones == sorted(posiciones)

    def test_el_filtro_por_htmx_devuelve_solo_el_catalogo(self, client):
        respuesta = client.get(
            reverse("missions:index"), {"tipo": "SEMANAL"}, headers={"HX-Request": "true"}
        )
        assert respuesta.status_code == 200
        assert b'id="catalogo"' in respuesta.content
        assert b"<html" not in respuesta.content
        assert respuesta.content.count(b"<section") == 1

    def test_un_tipo_inventado_no_rompe_la_pantalla(self, client):
        respuesta = client.get(reverse("missions:index"), {"tipo": "INVENTADO"})
        assert respuesta.status_code == 200
        assert respuesta.context["tipo_activo"] == ""
