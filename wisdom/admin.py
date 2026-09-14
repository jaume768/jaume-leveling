from django.contrib import admin

from .models import AdviceSession, Maxim, SystemPrompt


@admin.register(Maxim)
class MaximAdmin(admin.ModelAdmin):
    list_display = ("numero", "titulo", "libro", "tags")
    list_display_links = ("titulo",)
    list_filter = ("libro",)
    search_fields = ("titulo", "texto", "principio", "aplicacion", "tags")
    ordering = ("numero",)


@admin.register(SystemPrompt)
class SystemPromptAdmin(admin.ModelAdmin):
    list_display = ("nombre", "slug", "version", "activo")
    list_display_links = ("nombre",)
    list_editable = ("activo",)
    list_filter = ("activo", "slug")
    search_fields = ("nombre", "slug", "contenido")
    prepopulated_fields = {"slug": ("nombre",)}
    ordering = ("slug", "-version")


@admin.register(AdviceSession)
class AdviceSessionAdmin(admin.ModelAdmin):
    list_display = ("fecha", "pregunta_corta", "modelo", "tokens_in", "tokens_out", "coste_estimado")
    list_filter = ("modelo", "system_prompt")
    search_fields = ("pregunta", "respuesta")
    date_hierarchy = "fecha"
    ordering = ("-fecha",)
    readonly_fields = ("fecha", "tokens_in", "tokens_out", "coste_estimado")
    autocomplete_fields = ("system_prompt",)

    @admin.display(description="pregunta")
    def pregunta_corta(self, obj):
        return obj.pregunta[:80]
