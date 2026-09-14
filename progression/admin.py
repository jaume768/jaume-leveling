from django.contrib import admin

from .models import ResetWeek, Penalty, Reward, XPEvent, XPRule


@admin.register(XPRule)
class XPRuleAdmin(admin.ModelAdmin):
    list_display = ("nombre", "accion_slug", "categoria", "xp", "tope_semanal", "activa")
    list_display_links = ("nombre",)
    list_editable = ("xp", "tope_semanal", "activa")
    list_filter = ("categoria", "activa")
    search_fields = ("nombre", "accion_slug")
    prepopulated_fields = {"accion_slug": ("nombre",)}
    ordering = ("categoria", "-xp")


@admin.register(XPEvent)
class XPEventAdmin(admin.ModelAdmin):
    list_display = (
        "fecha",
        "accion_slug",
        "categoria",
        "xp_bruto",
        "multiplicador_racha",
        "xp_neto",
        "tope_aplicado",
        "fuente",
    )
    list_filter = ("categoria", "fuente", "tope_aplicado")
    search_fields = ("accion_slug", "descripcion", "objeto_relacionado")
    date_hierarchy = "fecha"
    ordering = ("-fecha", "-id")


@admin.register(Penalty)
class PenaltyAdmin(admin.ModelAdmin):
    list_display = ("fecha", "descripcion", "regla_slug", "xp", "resuelta")
    list_editable = ("resuelta",)
    list_filter = ("resuelta", "regla_slug")
    search_fields = ("descripcion", "regla_slug", "correccion_exigida")
    date_hierarchy = "fecha"
    ordering = ("-fecha",)
    actions = ("marcar_resueltas",)

    @admin.action(description="Marcar como resueltas")
    def marcar_resueltas(self, request, queryset):
        actualizadas = queryset.update(resuelta=True)
        self.message_user(request, f"{actualizadas} penalizaciones marcadas como resueltas.")


@admin.register(Reward)
class RewardAdmin(admin.ModelAdmin):
    list_display = ("titulo", "nivel_requerido", "rango", "desbloqueada", "fecha")
    list_editable = ("desbloqueada",)
    list_filter = ("desbloqueada", "rango")
    search_fields = ("titulo", "descripcion")
    date_hierarchy = "fecha"
    autocomplete_fields = ("rango",)
    ordering = ("nivel_requerido",)


@admin.register(ResetWeek)
class ResetWeekAdmin(admin.ModelAdmin):
    list_display = ("semana_iso", "anio", "fecha_activacion", "motivo")
    list_filter = ("anio",)
    date_hierarchy = "fecha_activacion"
