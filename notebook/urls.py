from django.urls import path

from . import views

app_name = "notebook"

urlpatterns = [
    path("", views.index, name="index"),
    path("crear/", views.crear, name="crear"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/cancelar/", views.cancelar_edicion, name="cancelar"),
    path("<int:pk>/fijar/", views.fijar, name="fijar"),
    path("<int:pk>/borrar/", views.borrar, name="borrar"),
]
