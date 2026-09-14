from django.contrib import admin

from .models import Mission, MissionLog


@admin.register(Mission)
class MissionAdmin(admin.ModelAdmin):
    list_display = (
        "titulo",
        "tipo",
        "xp",
        "tiempo_estimado_min",
        "attribute",
        "activa",
        "es_minima",
        "orden",
    )
    list_display_links = ("titulo",)
    list_editable = ("activa", "orden")
    list_filter = ("tipo", "activa", "es_minima", "evidencia_requerida", "attribute")
    search_fields = ("titulo", "descripcion", "definicion_terminada", "motivo")
    autocomplete_fields = ("attribute",)
    ordering = ("tipo", "orden")
    fieldsets = (
        ("Identidad", {"fields": ("titulo", "tipo", "orden", "activa", "es_minima")}),
        (
            "Definicion",
            {"fields": ("descripcion", "definicion_terminada", "tiempo_estimado_min")},
        ),
        ("Puntuacion", {"fields": ("xp", "attribute", "evidencia_requerida")}),
        ("Por que", {"fields": ("motivo",)}),
    )


@admin.register(MissionLog)
class MissionLogAdmin(admin.ModelAdmin):
    list_display = ("fecha", "mission", "completada", "xp_otorgado", "evidencia_texto")
    list_editable = ("completada", "xp_otorgado")
    list_filter = ("completada", "mission__tipo", "mission")
    search_fields = ("mission__titulo", "evidencia_texto", "notas")
    date_hierarchy = "fecha"
    autocomplete_fields = ("mission",)
    ordering = ("-fecha",)
