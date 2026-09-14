from django.contrib import admin
from django.utils import timezone

from .models import Client, Deal, Invoice, Project


class InvoiceInline(admin.TabularInline):
    model = Invoice
    extra = 0
    fields = ("concepto", "importe", "fecha_emision", "vencimiento", "cobrada", "fecha_cobro")
    ordering = ("-fecha_emision",)


class ProjectInline(admin.TabularInline):
    model = Project
    extra = 0
    fields = ("nombre", "precio", "estado", "horas_estimadas", "horas_reales", "fecha_entrega")
    ordering = ("-fecha_inicio",)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("nombre", "sector", "estado", "mrr", "fecha_alta", "url")
    list_display_links = ("nombre",)
    list_editable = ("estado", "mrr")
    list_filter = ("estado", "sector")
    search_fields = ("nombre", "slug", "sector", "notas")
    prepopulated_fields = {"slug": ("nombre",)}
    date_hierarchy = "fecha_alta"
    ordering = ("nombre",)
    inlines = [ProjectInline, InvoiceInline]


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = (
        "negocio",
        "contacto",
        "estado",
        "valor_potencial",
        "canal",
        "sector",
        "ultimo_toque",
        "dias_sin_toque_col",
        "proximo_paso",
        "fecha_proximo_paso",
    )
    list_display_links = ("negocio",)
    list_editable = ("estado", "ultimo_toque")
    list_filter = ("estado", "canal", "sector")
    search_fields = ("negocio", "contacto", "proximo_paso", "motivo_perdida")
    date_hierarchy = "fecha_primer_contacto"
    autocomplete_fields = ("client",)
    ordering = ("-fecha_primer_contacto",)
    actions = ("marcar_toque_hoy",)
    fieldsets = (
        ("Quien", {"fields": ("negocio", "contacto", "canal", "sector", "client")}),
        ("Estado", {"fields": ("estado", "valor_potencial", "motivo_perdida")}),
        (
            "Seguimiento",
            {
                "fields": (
                    "fecha_primer_contacto",
                    "ultimo_toque",
                    "proximo_paso",
                    "fecha_proximo_paso",
                )
            },
        ),
    )

    @admin.display(description="dias sin toque", ordering="ultimo_toque")
    def dias_sin_toque_col(self, obj):
        dias = obj.dias_sin_toque
        if dias is None:
            return "—"
        # 7 dias sin seguimiento en una propuesta son -100 XP.
        return f"{dias} ⚠" if dias > 7 else str(dias)

    @admin.action(description="Marcar ultimo toque = hoy")
    def marcar_toque_hoy(self, request, queryset):
        actualizados = queryset.update(ultimo_toque=timezone.localdate())
        self.message_user(request, f"{actualizados} oportunidades actualizadas.")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "client",
        "concepto",
        "importe",
        "fecha_emision",
        "vencimiento",
        "cobrada",
        "fecha_cobro",
        "dias_vencida_col",
    )
    list_display_links = ("concepto",)
    list_editable = ("cobrada", "fecha_cobro")
    list_filter = ("cobrada", "client", "vencimiento")
    search_fields = ("concepto", "client__nombre", "notas")
    date_hierarchy = "fecha_emision"
    autocomplete_fields = ("client",)
    ordering = ("-fecha_emision",)
    actions = ("marcar_cobradas",)

    @admin.display(description="dias vencida", ordering="vencimiento")
    def dias_vencida_col(self, obj):
        dias = obj.dias_vencida
        if not dias:
            return "—"
        return f"{dias} ⚠ RECLAMAR" if obj.hay_que_reclamar else str(dias)

    @admin.action(description="Marcar como cobradas hoy")
    def marcar_cobradas(self, request, queryset):
        actualizadas = queryset.update(cobrada=True, fecha_cobro=timezone.localdate())
        self.message_user(request, f"{actualizadas} facturas marcadas como cobradas.")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        "nombre",
        "client",
        "estado",
        "precio",
        "horas_estimadas",
        "horas_reales",
        "tarifa_efectiva_col",
        "fecha_inicio",
        "fecha_entrega",
    )
    list_display_links = ("nombre",)
    list_editable = ("estado", "horas_reales")
    list_filter = ("estado", "client")
    search_fields = ("nombre", "client__nombre")
    date_hierarchy = "fecha_inicio"
    autocomplete_fields = ("client",)
    ordering = ("-fecha_inicio",)

    @admin.display(description="tarifa efectiva (EUR/h)")
    def tarifa_efectiva_col(self, obj):
        tarifa = obj.tarifa_efectiva
        return "—" if tarifa is None else f"{tarifa}"
