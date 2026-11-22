from django.urls import path

from . import views

app_name = "cazador"

urlpatterns = [
    path("avisos/", views.avisos, name="avisos"),
    path("cofre/abrir/", views.abrir_cofre, name="abrir_cofre"),
    path("titulo/", views.equipar_titulo, name="equipar_titulo"),
    path("marco/", views.equipar_marco, name="equipar_marco"),
    path("alias/", views.alias, name="alias"),
    path("push/suscribir/", views.suscribir, name="suscribir"),
    path("push/probar/", views.probar_push, name="probar_push"),
]
