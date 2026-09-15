from django.contrib import admin

from .models import Note


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("encabezado", "fecha", "fijada", "actualizada")
    list_display_links = ("encabezado",)
    list_editable = ("fijada",)
    list_filter = ("fijada", "fecha")
    search_fields = ("titulo", "contenido")
    date_hierarchy = "fecha"
    ordering = ("-fecha", "-creada")
