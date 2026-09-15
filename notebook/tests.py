import datetime as dt

import pytest
from django.urls import reverse
from django.utils import timezone

from missions import services as missions_services
from missions.models import Mission
from notebook import services
from notebook.models import Note

HOY = timezone.localdate
AYER = dt.date(2026, 9, 14)


@pytest.fixture
def d2(db):
    return Mission.objects.get(titulo__startswith="D2 · ")


@pytest.mark.django_db
class TestNotas:
    def test_crear_una_nota(self):
        nota = services.crear_nota("Multiidioma para Artà", titulo="Idea")
        assert nota.titulo == "Idea"
        assert nota.contenido == "Multiidioma para Artà"
        assert nota.fecha == HOY()

    def test_una_nota_vacia_no_se_guarda(self):
        assert services.crear_nota("   ") is None
        assert Note.objects.count() == 0

    def test_el_titulo_es_opcional(self):
        nota = services.crear_nota("Sin título, solo el texto")
        assert nota.titulo == ""
        assert nota.encabezado == "Sin título, solo el texto"

    def test_el_encabezado_usa_la_primera_linea(self):
        nota = services.crear_nota("Primera línea\nSegunda línea")
        assert nota.encabezado == "Primera línea"

    def test_actualizar_una_nota(self):
        nota = services.crear_nota("viejo")
        services.actualizar_nota(nota, "nuevo", titulo="Título")
        nota.refresh_from_db()
        assert (nota.titulo, nota.contenido) == ("Título", "nuevo")

    def test_fijar_y_desfijar(self):
        nota = services.crear_nota("importante")
        assert services.alternar_fijada(nota).fijada is True
        assert services.alternar_fijada(nota).fijada is False

    def test_borrar(self):
        services.borrar_nota(services.crear_nota("fuera"))
        assert Note.objects.count() == 0


@pytest.mark.django_db
class TestCuaderno:
    def test_agrupa_por_dia_con_el_mas_reciente_arriba(self):
        Note.objects.create(contenido="lo de ayer", fecha=AYER)
        Note.objects.create(contenido="lo de hoy", fecha=HOY())
        dias = services.cuaderno()["dias"]
        assert [d["fecha"] for d in dias] == [HOY(), AYER]

    def test_las_fijadas_van_aparte(self):
        nota = services.crear_nota("importante")
        services.alternar_fijada(nota)
        services.crear_nota("normal")
        cuaderno = services.cuaderno()
        assert [e["contenido"] for e in cuaderno["fijadas"]] == ["importante"]
        contenidos = [e["contenido"] for d in cuaderno["dias"] for e in d["entradas"]]
        assert contenidos == ["normal"]

    def test_incluye_las_notas_de_las_misiones(self, d2):
        missions_services.guardar_notas(d2, "1. Llamar\n2. Escribir")
        entradas = [e for d in services.cuaderno()["dias"] for e in d["entradas"]]
        de_mision = [e for e in entradas if e["tipo"] == "mision"]
        assert len(de_mision) == 1
        assert de_mision[0]["contenido"] == "1. Llamar\n2. Escribir"
        assert "Cierre del día" in de_mision[0]["titulo"]

    def test_las_misiones_sin_notas_no_aparecen(self, d2):
        missions_services.guardar_notas(d2, "")
        assert services.cuaderno()["dias"] == []

    def test_busca_en_las_notas_sueltas(self):
        services.crear_nota("Multiidioma para Artà")
        services.crear_nota("Llamar a la gestoría")
        entradas = [e for d in services.cuaderno("multiidioma")["dias"] for e in d["entradas"]]
        assert len(entradas) == 1
        assert "Multiidioma" in entradas[0]["contenido"]

    def test_busca_tambien_en_las_de_mision(self, d2):
        missions_services.guardar_notas(d2, "Llamar a Gruas Perelló")
        entradas = [e for d in services.cuaderno("gruas")["dias"] for e in d["entradas"]]
        assert len(entradas) == 1
        assert entradas[0]["tipo"] == "mision"

    def test_busca_por_titulo(self):
        services.crear_nota("cuerpo", titulo="Artà Immobilien")
        assert services.cuaderno("immobilien")["dias"]

    def test_sin_resultados_devuelve_vacio(self):
        services.crear_nota("algo")
        assert services.cuaderno("zzzz")["dias"] == []


@pytest.mark.django_db
class TestVistas:
    def test_el_cuaderno_carga(self, client):
        assert client.get(reverse("notebook:index")).status_code == 200

    def test_esta_en_el_menu(self, client):
        contenido = client.get(reverse("core:index")).content.decode()
        assert reverse("notebook:index") in contenido
        assert "Cuaderno" in contenido

    def test_crear_por_htmx_devuelve_la_lista(self, client):
        respuesta = client.post(
            reverse("notebook:crear"), {"titulo": "Idea", "contenido": "Multiidioma"}
        )
        assert respuesta.status_code == 200
        assert b'id="cuaderno"' in respuesta.content
        assert b"<html" not in respuesta.content
        assert Note.objects.count() == 1

    def test_crear_vacia_avisa_y_no_guarda(self, client):
        respuesta = client.post(reverse("notebook:crear"), {"contenido": "  "})
        assert "Escribe algo antes de guardar".encode() in respuesta.content
        assert Note.objects.count() == 0

    def test_editar_abre_el_formulario(self, client):
        nota = services.crear_nota("texto")
        respuesta = client.get(reverse("notebook:editar", args=[nota.pk]))
        assert b"<textarea" in respuesta.content

    def test_editar_guarda(self, client):
        nota = services.crear_nota("viejo")
        client.post(reverse("notebook:editar", args=[nota.pk]), {"contenido": "nuevo"})
        nota.refresh_from_db()
        assert nota.contenido == "nuevo"

    def test_cancelar_no_guarda(self, client):
        nota = services.crear_nota("intacto")
        respuesta = client.get(reverse("notebook:cancelar", args=[nota.pk]))
        assert b"intacto" in respuesta.content
        nota.refresh_from_db()
        assert nota.contenido == "intacto"

    def test_fijar_por_htmx(self, client):
        nota = services.crear_nota("importante")
        client.post(reverse("notebook:fijar", args=[nota.pk]))
        nota.refresh_from_db()
        assert nota.fijada is True

    def test_borrar_por_htmx(self, client):
        nota = services.crear_nota("fuera")
        client.post(reverse("notebook:borrar", args=[nota.pk]))
        assert Note.objects.count() == 0

    def test_el_buscador_filtra(self, client):
        services.crear_nota("Multiidioma para Artà")
        services.crear_nota("Llamar a la gestoría")
        contenido = client.get(reverse("notebook:index"), {"q": "multiidioma"}).content.decode()
        assert "Multiidioma" in contenido
        assert "gestoría" not in contenido

    def test_las_notas_de_mision_no_se_pueden_borrar_desde_aqui(self, client, d2):
        missions_services.guardar_notas(d2, "1. Llamar")
        contenido = client.get(reverse("notebook:index")).content.decode()
        assert "1. Llamar" in contenido
        # No hay botones de edición ni de borrado para las entradas de misión.
        assert contenido.count("notebook:borrar") == 0
