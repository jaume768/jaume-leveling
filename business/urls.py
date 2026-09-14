from django.urls import path

from . import views

app_name = "business"

urlpatterns = [
    path("", views.index, name="index"),
    # Pipeline
    path("pipeline/", views.pipeline, name="pipeline"),
    path("pipeline/nueva/", views.deal_nuevo, name="deal_nuevo"),
    path("pipeline/<int:pk>/fila/", views.deal_fila, name="deal_fila"),
    path("pipeline/<int:pk>/editar/", views.deal_editar, name="deal_editar"),
    path("pipeline/<int:pk>/guardar/", views.deal_guardar, name="deal_guardar"),
    path("pipeline/<int:pk>/toque/", views.deal_toque, name="deal_toque"),
    # Facturas
    path("facturas/", views.facturas, name="facturas"),
    path("facturas/nueva/", views.factura_nueva, name="factura_nueva"),
    path("facturas/<int:pk>/cobrar/", views.factura_cobrar, name="factura_cobrar"),
    # Clientes
    path("clientes/", views.clientes, name="clientes"),
    path("clientes/nuevo/", views.cliente_nuevo, name="cliente_nuevo"),
    # Proyectos
    path("proyectos/", views.proyectos, name="proyectos"),
    path("proyectos/nuevo/", views.proyecto_form, name="proyecto_nuevo"),
    path("proyectos/<int:pk>/editar/", views.proyecto_form, name="proyecto_editar"),
]
