from django.urls import path

from . import views

app_name = "progression"

urlpatterns = [
    path("", views.index, name="index"),
    path("accion/", views.registrar_accion, name="registrar_accion"),
    path("reinicio/", views.activar_reinicio, name="activar_reinicio"),
    path("penalizacion/<int:pk>/resolver/", views.resolver, name="resolver"),
]
