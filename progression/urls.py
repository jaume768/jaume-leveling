from django.urls import path

from . import views

app_name = "progression"

urlpatterns = [
    path("", views.index, name="index"),
    path("accion/", views.registrar_accion, name="registrar_accion"),
    path("reinicio/", views.activar_reinicio, name="activar_reinicio"),
    path("evento/<int:pk>/", views.evento, name="evento"),
    path("recompensas/", views.recompensas, name="recompensas"),
    path("recompensas/<int:pk>/desbloquear/", views.desbloquear_recompensa,
         name="desbloquear_recompensa"),
    path("recompensas/<int:pk>/disfrutar/", views.disfrutar_recompensa,
         name="disfrutar_recompensa"),
    path("penalizacion/<int:pk>/resolver/", views.resolver, name="resolver"),
]
