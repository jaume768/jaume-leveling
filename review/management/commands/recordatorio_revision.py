"""Recordatorio de la revisión semanal.

Pensado para cron los domingos por la tarde:
    0 19 * * 0  python manage.py recordatorio_revision
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from progression import services as progression
from review import services


class Command(BaseCommand):
    help = "Si es domingo y no hay revisión de la semana, deja el aviso en el panel."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fecha",
            help="Fecha en formato AAAA-MM-DD. Por defecto, hoy.",
        )
        parser.add_argument(
            "--forzar",
            action="store_true",
            help="Crea el borrador aunque no sea domingo.",
        )

    def handle(self, *args, **opciones):
        fecha = timezone.localdate()
        if opciones.get("fecha"):
            fecha = timezone.datetime.strptime(opciones["fecha"], "%Y-%m-%d").date()

        if fecha.weekday() != progression.DOMINGO and not opciones["forzar"]:
            self.stdout.write(f"{fecha} no es domingo. Nada que hacer.")
            return

        revision = services.revision_de_la_semana(fecha)
        if revision is not None and revision.m8_revision_hecha:
            self.stdout.write(
                self.style.SUCCESS(f"La revisión de la semana {revision.semana_iso} ya está cerrada.")
            )
            return

        borrador = services.crear_borrador(fecha)
        self.stdout.write(
            self.style.WARNING(
                f"Revisión de la semana {borrador.semana_iso}/{borrador.anio} pendiente. "
                "Borrador creado con las métricas calculadas y aviso activo en el panel."
            )
        )
