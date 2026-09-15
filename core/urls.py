from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.index, name="index"),
    path("captura/", views.captura, name="captura"),
    path("niveles/", views.niveles, name="niveles"),
    path("personaje/", views.personaje, name="personaje"),
    path("calibracion/", views.calibracion, name="calibracion"),
]
