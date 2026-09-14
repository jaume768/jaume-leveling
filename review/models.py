from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class WeeklyReview(models.Model):
    """Revision semanal del domingo: las diez metricas del panel.

    Las metricas m1..m10 son las de docs/sistema-v2.md, §12. Se guardan con
    nombre descriptivo para que el admin sea legible.
    """

    anio = models.PositiveSmallIntegerField("anio")
    semana_iso = models.PositiveSmallIntegerField("semana ISO")
    fecha = models.DateField("fecha de la revision")

    m1_eur_cobrados = models.DecimalField(
        "1 · EUR cobrados (mes)", max_digits=10, decimal_places=2, default=0
    )
    m2_eur_recurrentes = models.DecimalField(
        "2 · EUR recurrentes activos/mes", max_digits=10, decimal_places=2, default=0
    )
    m3_eur_vencidos = models.DecimalField(
        "3 · EUR vencidos sin cobrar", max_digits=10, decimal_places=2, default=0
    )
    m4_contactos_nuevos = models.PositiveSmallIntegerField("4 · contactos nuevos", default=0)
    m5_conversaciones = models.PositiveSmallIntegerField("5 · conversaciones", default=0)
    m5_propuestas = models.PositiveSmallIntegerField("5 · propuestas", default=0)
    m6_precio_medio = models.DecimalField(
        "6 · precio medio propuesto", max_digits=10, decimal_places=2, default=0
    )
    m7_tarifa_efectiva = models.DecimalField(
        "7 · tarifa efectiva (EUR/h)",
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text="Metrica maestra: EUR del mes / horas del mes.",
    )
    m8_revision_hecha = models.BooleanField("8 · revision hecha", default=False)
    m8_wip_abierto = models.PositiveSmallIntegerField("8 · WIP abierto", default=0)
    m9_entrenos = models.PositiveSmallIntegerField("9 · entrenos (0-4)", default=0)
    m9_peso_medio = models.DecimalField(
        "9 · peso medio (kg)", max_digits=5, decimal_places=2, null=True, blank=True
    )
    m10_bloques_intactos = models.BooleanField(
        "10 · bloques con Alexandra intactos", default=True
    )

    xp_semana = models.IntegerField("XP de la semana", default=0)
    funciono = models.TextField("funciono", blank=True)
    no_funciono = models.TextField("no funciono", blank=True)
    decision = models.TextField("una decision para la semana que viene", blank=True)
    objetivo_1 = models.CharField("objetivo 1", max_length=255, blank=True)
    objetivo_2 = models.CharField("objetivo 2", max_length=255, blank=True)
    objetivo_3 = models.CharField("objetivo 3", max_length=255, blank=True)

    class Meta:
        verbose_name = "revision semanal"
        verbose_name_plural = "revisiones semanales"
        ordering = ["-anio", "-semana_iso"]
        constraints = [
            models.UniqueConstraint(
                fields=["anio", "semana_iso"], name="weeklyreview_unica_por_semana"
            )
        ]
        indexes = [
            models.Index(fields=["-anio", "-semana_iso"], name="weeklyreview_semana_idx"),
            models.Index(fields=["-fecha"], name="weeklyreview_fecha_idx"),
        ]

    def __str__(self):
        return f"Semana {self.semana_iso}/{self.anio} · {self.xp_semana} XP"


class HealthLog(models.Model):
    """Registro diario de salud. El peso se lee en media de 7 dias, no a diario."""

    fecha = models.DateField("fecha", unique=True)
    peso = models.DecimalField(
        "peso (kg)", max_digits=5, decimal_places=2, null=True, blank=True
    )
    cintura = models.DecimalField(
        "cintura (cm)", max_digits=5, decimal_places=1, null=True, blank=True
    )
    sueno_horas = models.DecimalField(
        "horas de sueno", max_digits=4, decimal_places=1, null=True, blank=True
    )
    energia = models.PositiveSmallIntegerField(
        "energia (1-5)",
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    entreno = models.BooleanField("entreno", default=False)
    tipo_entreno = models.CharField("tipo de entreno", max_length=80, blank=True)

    class Meta:
        verbose_name = "registro de salud"
        verbose_name_plural = "registros de salud"
        ordering = ["-fecha"]
        indexes = [
            models.Index(fields=["-fecha"], name="healthlog_fecha_idx"),
            models.Index(fields=["entreno", "-fecha"], name="healthlog_entreno_idx"),
        ]

    def __str__(self):
        partes = [str(self.fecha)]
        if self.peso:
            partes.append(f"{self.peso} kg")
        if self.entreno:
            partes.append(self.tipo_entreno or "entreno")
        return " · ".join(partes)
