from django.urls import path

from . import views

app_name = "wisdom"

urlpatterns = [
    path("", views.index, name="index"),
]
