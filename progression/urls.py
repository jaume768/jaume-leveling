from django.urls import path

from . import views

app_name = "progression"

urlpatterns = [
    path("", views.index, name="index"),
    path("penalizacion/<int:pk>/resolver/", views.resolver, name="resolver"),
]
