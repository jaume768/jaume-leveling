from django.contrib import admin

from .models import Attribute, AttributeLog, Profile, Rank

admin.site.site_header = "Sistema · Jaume"
admin.site.site_title = "Sistema"
admin.site.index_title = "Interfaz de emergencia"


@admin.register(Rank)
class RankAdmin(admin.ModelAdmin):
    list_display = ("orden", "nombre", "nivel_min", "nivel_max", "jefe")
    list_display_links = ("nombre",)
    list_filter = ("orden",)
    search_fields = ("nombre", "jefe", "objetivo", "criterio_ascenso")
    ordering = ("orden",)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        "__str__",
        "nivel",
        "xp_total",
        "xp_en_nivel",
        "xp_para_siguiente_nivel",
        "progreso_nivel_pct",
        "rango",
    )
    list_filter = ("rango",)
    readonly_fields = (
        "fecha_inicio",
        "xp_en_nivel",
        "xp_para_siguiente_nivel",
        "progreso_nivel_pct",
    )
    fieldsets = (
        ("Progresion", {"fields": ("nivel", "xp_total", "rango")}),
        (
            "Calculado",
            {"fields": ("xp_en_nivel", "xp_para_siguiente_nivel", "progreso_nivel_pct")},
        ),
        ("Fisico", {"fields": ("altura_cm", "peso_objetivo")}),
        ("Meta", {"fields": ("fecha_inicio",)}),
    )

    def has_add_permission(self, request):
        # Singleton: el perfil se crea solo con Profile.get().
        return not Profile.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


class AttributeLogInline(admin.TabularInline):
    model = AttributeLog
    extra = 0
    fields = ("fecha", "valor", "nota")
    ordering = ("-fecha",)


@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    list_display = ("nombre", "slug", "valor", "categoria")
    list_editable = ("valor",)
    list_filter = ("categoria",)
    search_fields = ("nombre", "slug")
    prepopulated_fields = {"slug": ("nombre",)}
    ordering = ("categoria", "-valor")
    inlines = [AttributeLogInline]


@admin.register(AttributeLog)
class AttributeLogAdmin(admin.ModelAdmin):
    list_display = ("fecha", "attribute", "valor", "nota")
    list_filter = ("attribute__categoria", "attribute")
    search_fields = ("attribute__nombre", "nota")
    date_hierarchy = "fecha"
    autocomplete_fields = ("attribute",)
