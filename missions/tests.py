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
