from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

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
    path("", include("core.urls")),
    path("misiones/", include("missions.urls")),
    path("progresion/", include("progression.urls")),
    path("negocio/", include("business.urls")),
    path("revision/", include("review.urls")),
    path("", include("wisdom.urls")),
]
