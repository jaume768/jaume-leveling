"""Pulso horario del Sistema. Cron, cada hora en punto:

    0 * * * *  python manage.py pulso_sistema

Cierra el dia anterior (escudos de racha, escudo por semana perfecta, logros)
y manda las notificaciones de las 08:00 y las 21:00, en hora local. Todo es
idempotente: correrlo dos veces no duplica nada.
"""
from django.core.management.base import BaseCommand

from cazador import services


class Command(BaseCommand):
    help = "Cierre del dia y notificaciones del Sistema. Cron: cada hora."

    def handle(self, *args, **opciones):
        hechos = services.pulso()
        if hechos:
            for hecho in hechos:
                self.stdout.write(f"  · {hecho}")
        else:
            self.stdout.write("Sin novedades.")
