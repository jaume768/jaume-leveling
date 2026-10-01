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
    path("pipeline/<int:pk>/datos/", views.deal_datos, name="deal_datos"),
    path("pipeline/<int:pk>/eliminar/", views.deal_eliminar, name="deal_eliminar"),
    # Facturas
    path("facturas/", views.facturas, name="facturas"),
    path("facturas/nueva/", views.factura_nueva, name="factura_nueva"),
    path("facturas/<int:pk>/confirmar-cobro/", views.confirmar_cobro, name="confirmar_cobro"),
    path("facturas/<int:pk>/cobrar/", views.factura_cobrar, name="factura_cobrar"),
    # Clientes
    path("clientes/", views.clientes, name="clientes"),
    path("clientes/nuevo/", views.cliente_nuevo, name="cliente_nuevo"),
    path("clientes/<int:pk>/editar/", views.cliente_editar, name="cliente_editar"),
    path("clientes/<int:pk>/eliminar/", views.cliente_eliminar, name="cliente_eliminar"),
    # Proyectos
    path("proyectos/", views.proyectos, name="proyectos"),
    path("proyectos/nuevo/", views.proyecto_form, name="proyecto_nuevo"),
    path("proyectos/<int:pk>/editar/", views.proyecto_form, name="proyecto_editar"),
]
