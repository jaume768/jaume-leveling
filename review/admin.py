from django.contrib import admin

from .models import HealthLog, WeeklyReview


@admin.register(WeeklyReview)
class WeeklyReviewAdmin(admin.ModelAdmin):
    list_display = (
        "__str__",
        "fecha",
        "m1_eur_cobrados",
        "m2_eur_recurrentes",
        "m3_eur_vencidos",
        "m4_contactos_nuevos",
        "m7_tarifa_efectiva",
        "m8_wip_abierto",
        "m9_entrenos",
        "m10_bloques_intactos",
        "xp_semana",
    )
    list_display_links = ("__str__",)
    list_filter = ("anio", "m8_revision_hecha", "m10_bloques_intactos")
    search_fields = ("funciono", "no_funciono", "decision", "objetivo_1", "objetivo_2", "objetivo_3")
    date_hierarchy = "fecha"
    ordering = ("-anio", "-semana_iso")
    fieldsets = (
        ("Semana", {"fields": ("anio", "semana_iso", "fecha", "xp_semana")}),
        (
            "Dinero",
            {
                "fields": (
                    "m1_eur_cobrados",
                    "m2_eur_recurrentes",
                    "m3_eur_vencidos",
                    "m6_precio_medio",
                    "m7_tarifa_efectiva",
                )
            },
        ),
        (
            "Comercial",
            {"fields": ("m4_contactos_nuevos", "m5_conversaciones", "m5_propuestas")},
        ),
        ("Sistema", {"fields": ("m8_revision_hecha", "m8_wip_abierto")}),
        ("Personal", {"fields": ("m9_entrenos", "m9_peso_medio", "m10_bloques_intactos")}),
        (
            "Balance",
            {
                "fields": (
                    "funciono",
                    "no_funciono",
                    "decision",
                    "objetivo_1",
                    "objetivo_2",
                    "objetivo_3",
                )
            },
        ),
    )


@admin.register(HealthLog)
class HealthLogAdmin(admin.ModelAdmin):
    list_display = ("fecha", "peso", "cintura", "sueno_horas", "energia", "entreno", "tipo_entreno")
    list_editable = ("peso", "sueno_horas", "energia", "entreno")
    list_filter = ("entreno", "tipo_entreno", "energia")
    search_fields = ("tipo_entreno",)
    date_hierarchy = "fecha"
    ordering = ("-fecha",)
