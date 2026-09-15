"""Chequeo diario del sistema. Pensado para cron a las 07:00:

    0 7 * * *  python manage.py chequeo_diario

Detecta las situaciones que el documento penaliza y las registra. Cada
penalización queda PENDIENTE hasta que se marca como resuelta desde el panel,
y ninguna se aplica dos veces por el mismo hecho: cada una lleva una clave de
idempotencia "<regla>--<objeto>".

Los días protegidos (miércoles y domingo) no generan penalizaciones nuevas.

La revisión semanal NO se penaliza: el documento la puntúa con 60 XP pero dice
expresamente que no penaliza si no se hace (docs/sistema-v2.md). El recordatorio
del domingo lo da `recordatorio_revision`, sin descontar XP.
"""
from __future__ import annotations

import datetime as dt

from django.core.management.base import BaseCommand
from django.utils import timezone

from business.models import Deal, Invoice, Project
from progression import services as progression


class Command(BaseCommand):
    help = "Aplica las penalizaciones automáticas del sistema. Cron: 07:00."

    def add_arguments(self, parser):
        parser.add_argument("--fecha", help="Fecha AAAA-MM-DD. Por defecto, hoy.")
        parser.add_argument(
            "--simular",
            action="store_true",
            help="Enseña lo que haría sin escribir nada.",
        )

    def handle(self, *args, **opciones):
        fecha = timezone.localdate()
        if opciones.get("fecha"):
            fecha = dt.datetime.strptime(opciones["fecha"], "%Y-%m-%d").date()
        self.simular = opciones["simular"]

        # Miercoles y domingo estan fuera del sistema: no generan XP, no rompen
        # la racha y no pueden penalizar. Se sale antes de tocar nada, que es
        # lo que la cabecera de este comando promete.
        if progression.es_dia_protegido(fecha):
            dia = "miércoles" if fecha.weekday() == progression.MIERCOLES else "domingo"
            self.stdout.write(
                self.style.SUCCESS(
                    f"{fecha} es {dia}: día protegido. No se penaliza nada."
                )
            )
            return

        aplicadas = []
        for comprobacion in (
            self._facturas_sin_reclamar,
            self._propuestas_sin_seguimiento,
            self._semana_sin_comercial,
            self._exceso_de_wip,
        ):
            aplicadas.extend(comprobacion(fecha))

        if not aplicadas:
            self.stdout.write(self.style.SUCCESS(f"{fecha}: nada que penalizar."))
            return

        total = sum(xp for _, xp in aplicadas)
        for descripcion, xp in aplicadas:
            self.stdout.write(self.style.WARNING(f"  {xp:+} XP · {descripcion}"))
        prefijo = "[simulación] " if self.simular else ""
        self.stdout.write(
            self.style.ERROR(f"{prefijo}{len(aplicadas)} penalizaciones · {total:+} XP")
        )

    # --- Reglas -------------------------------------------------------------

    def _penalizar(self, clave, *, descripcion, correccion, xp=None, fecha=None):
        """Aplica si no estaba aplicada ya. Devuelve [(descripcion, xp)] o []."""
        if progression.penalizacion_ya_aplicada(clave):
            return []
        if self.simular:
            if xp is None:
                regla = progression.XPRule.objects.filter(
                    accion_slug=progression.regla_de(clave)
                ).first()
                xp = regla.xp if regla else 0
            return [(f"{descripcion} (no escrito)", xp)]
        penalizacion = progression.aplicar_penalizacion(
            clave, descripcion=descripcion, correccion=correccion, xp=xp, fecha=fecha
        )
        return [(penalizacion.descripcion, penalizacion.xp)] if penalizacion else []

    def _facturas_sin_reclamar(self, fecha: dt.date):
        """Factura vencida hace más de 15 días sin reclamar: -200 XP."""
        limite = fecha - dt.timedelta(days=Invoice.DIAS_PARA_RECLAMAR)
        aplicadas = []
        for factura in Invoice.objects.filter(
            cobrada=False, vencimiento__lt=limite
        ).select_related("client"):
            aplicadas += self._penalizar(
                progression.clave_penalizacion(
                    "factura-vencida-sin-reclamar", f"invoice-{factura.pk}"
                ),
                descripcion=(
                    f"{factura.client.nombre}: {factura.importe:.0f} € con "
                    f"{factura.dias_vencida} días de retraso"
                ),
                correccion=(
                    "Reclamación enviada antes de cualquier otra tarea. Una vez, clara, "
                    "con fecha y sin adornos."
                ),
                fecha=fecha,
            )
        return aplicadas

    def _propuestas_sin_seguimiento(self, fecha: dt.date):
        """Propuesta sin toque hace más de 7 días: -100 XP, una vez por semana."""
        limite = fecha - dt.timedelta(days=7)
        aplicadas = []
        candidatos = Deal.objects.filter(estado=Deal.Estado.PROPUESTA)
        for deal in candidatos:
            referencia = deal.ultimo_toque or deal.fecha_primer_contacto
            if referencia is None or referencia >= limite:
                continue
            dias = (fecha - referencia).days
            aplicadas += self._penalizar(
                progression.clave_penalizacion(
                    "propuesta-sin-seguimiento",
                    f"deal-{deal.pk}-{progression.clave_semana(fecha)}",
                ),
                descripcion=f"{deal.negocio}: propuesta sin seguimiento, {dias} días",
                correccion="Seguimiento primero, todo lo demás después.",
                fecha=fecha,
            )
        return aplicadas

    def _semana_sin_comercial(self, fecha: dt.date):
        """Semana terminada con 0 acciones comerciales: -150 XP y bloqueo."""
        lunes_actual, _ = progression.rango_de_la_semana(fecha)
        lunes, domingo = progression.rango_de_la_semana(lunes_actual - dt.timedelta(days=1))

        nuevos = Deal.objects.filter(fecha_primer_contacto__range=(lunes, domingo))
        tocados = Deal.objects.filter(ultimo_toque__range=(lunes, domingo))
        if nuevos.union(tocados).exists():
            return []

        return self._penalizar(
            progression.clave_penalizacion(
                "semana-sin-comercial", progression.clave_semana(lunes)
            ),
            descripcion=f"Semana del {lunes} al {domingo}: 0 acciones comerciales",
            correccion=(
                f"El trabajo técnico no facturable queda bloqueado hasta completar "
                f"{progression.CONTACTOS_PARA_DESBLOQUEAR} contactos."
            ),
            fecha=fecha,
        )

    def _exceso_de_wip(self, fecha: dt.date):
        """Más de 2 proyectos activos: -100 XP, una vez por semana."""
        activos = Project.objects.filter(estado=Project.Estado.ACTIVO)
        if activos.count() <= 2:
            return []
        return self._penalizar(
            progression.clave_penalizacion("exceso-wip", progression.clave_semana(fecha)),
            descripcion=f"{activos.count()} proyectos abiertos a la vez (máximo 2)",
            correccion="Cerrar o congelar uno antes de tocar nada más.",
            fecha=fecha,
        )
