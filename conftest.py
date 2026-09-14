"""Configuracion comun de los tests.

La instancia entera esta detras del login (LoginRequiredMiddleware), asi que el
cliente de pruebas entra autenticado por defecto. Los tests que quieran probar
el propio login usan `client_anonimo`.
"""
import pytest


@pytest.fixture
def client(client, django_user_model):
    """Cliente ya autenticado: es como se usa el sistema de verdad."""
    usuario = django_user_model.objects.create_user("tester", password="x")
    client.force_login(usuario)
    return client


@pytest.fixture
def client_anonimo(client):
    """Cliente sin sesion, para comprobar que el login protege de verdad."""
    client.logout()
    return client
