from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from core import views as core_views

urlpatterns = [
    path("admin/", admin.site.urls),
    # Auth minima: un solo usuario, sin registro ni recuperacion por correo.
    path(
        "entrar/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html", redirect_authenticated_user=True
        ),
        name="login",
    ),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
    # App instalable: manifiesto, service worker y verificacion del APK.
    path("manifest.webmanifest", core_views.manifiesto, name="manifiesto"),
    path("sw.js", core_views.service_worker, name="service_worker"),
    path("sin-conexion/", core_views.sin_conexion, name="sin_conexion"),
    path(".well-known/assetlinks.json", core_views.assetlinks, name="assetlinks"),
    path("", include("core.urls")),
    path("misiones/", include("missions.urls")),
    path("progresion/", include("progression.urls")),
    path("negocio/", include("business.urls")),
    path("revision/", include("review.urls")),
    path("cuaderno/", include("notebook.urls")),
    path("", include("wisdom.urls")),
]
