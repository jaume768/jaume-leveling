from django.urls import path

from . import views

app_name = "missions"

urlpatterns = [
    path("", views.index, name="index"),
    path("bloque/", views.bloque, name="bloque"),
    path("<int:pk>/detalle/", views.detalle, name="detalle"),
    path("<int:pk>/completar/", views.completar, name="completar"),
    path("<int:pk>/evidencia/", views.evidencia, name="evidencia"),
    path("<int:pk>/notas/", views.notas, name="notas"),
    path("modal/cerrar/", views.cerrar_modal, name="cerrar_modal"),
]
