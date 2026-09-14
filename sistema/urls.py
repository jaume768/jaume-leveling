from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("misiones/", include("missions.urls")),
    path("progresion/", include("progression.urls")),
    path("negocio/", include("business.urls")),
    path("revision/", include("review.urls")),
    path("maximas/", include("wisdom.urls")),
    path("consejo/", RedirectView.as_view(pattern_name="wisdom:index", permanent=False)),
]
