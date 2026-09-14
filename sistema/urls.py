from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("misiones/", include("missions.urls")),
    path("progresion/", include("progression.urls")),
    path("negocio/", include("business.urls")),
    path("revision/", include("review.urls")),
    path("", include("wisdom.urls")),
]
