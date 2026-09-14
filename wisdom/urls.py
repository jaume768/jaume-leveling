from django.urls import path

from . import views

app_name = "wisdom"

# Se monta en la raíz para que las rutas queden en /consejo/ y /maximas/.
urlpatterns = [
    path("consejo/", views.consejo, name="index"),
    path("consejo/gasto/", views.gasto, name="gasto"),
    path("maximas/", views.maximas, name="maximas"),
]
