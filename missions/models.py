from django.db import models


class Mission(models.Model):
    """Mision del sistema. La definicion de 'terminada' es obligatoria."""

    class Tipo(models.TextChoices):
        DIARIA = "DIARIA", "Diaria"
        SEMANAL = "SEMANAL", "Semanal"
        MENSUAL = "MENSUAL", "Mensual"
        ANUAL = "ANUAL", "Anual"
        PRINCIPAL = "PRINCIPAL", "Principal"

    titulo = models.CharField("titulo", max_length=160)
    tipo = models.CharField("tipo", max_length=12, choices=Tipo.choices, db_index=True)
    descripcion = models.TextField("descripcion", blank=True)
    definicion_terminada = models.CharField(
        "definicion de terminada",
        max_length=255,
        help_text="Que tiene que ser cierto para darla por hecha.",
    )
    tiempo_estimado_min = models.PositiveSmallIntegerField("tiempo estimado (min)", default=0)
    xp = models.IntegerField("XP", default=0)
    attribute = models.ForeignKey(
        "core.Attribute",
        verbose_name="atributo que mueve",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="misiones",
    )
    # Escalado por rango. Ambos opcionales: una mision sin rangos esta siempre
    # disponible, que es el caso de las diarias, semanales y mensuales. Las
    # principales si se atan a su rango, porque cada una cierra el suyo
    # (docs/sistema-v2.md, SS4 y SS5).
    rango_min = models.ForeignKey(
        "core.Rank",
        verbose_name="disponible desde el rango",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="misiones_desde",
        help_text="Vacio = disponible desde el principio.",
    )
    rango_max = models.ForeignKey(
        "core.Rank",
        verbose_name="disponible hasta el rango",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="misiones_hasta",
        help_text="Vacio = no se retira nunca.",
    )
    motivo = models.TextField("por que", blank=True)
    evidencia_requerida = models.BooleanField("requiere evidencia", default=False)
    pide_notas = models.BooleanField(
        "abre el cuaderno",
        default=False,
        help_text=(
            "Al completarla se abre un cuaderno para apuntar. Es el caso del "
            "cierre del dia: lo anotado ES la mision."
        ),
    )
    etiqueta_notas = models.CharField(
        "que se apunta",
        max_length=120,
        blank=True,
        help_text="Rotulo del cuaderno, p. ej. 'Las dos tareas de manana'.",
    )
    activa = models.BooleanField("activa", default=True)
    orden = models.PositiveSmallIntegerField("orden", default=0)
    es_minima = models.BooleanField(
        "es version minima",
        default=False,
        help_text="Version reducida que mantiene la racha en un dia malo.",
    )

    class Meta:
        verbose_name = "mision"
        verbose_name_plural = "misiones"
        ordering = ["tipo", "orden", "titulo"]
        indexes = [
            models.Index(fields=["tipo", "activa"], name="mission_tipo_activa_idx"),
            models.Index(fields=["activa", "orden"], name="mission_activa_orden_idx"),
        ]

    def __str__(self):
        return f"[{self.get_tipo_display()}] {self.titulo} ({self.xp} XP)"


class MissionLog(models.Model):
    """Cumplimiento de una mision en una fecha concreta."""

    mission = models.ForeignKey(
        Mission, verbose_name="mision", on_delete=models.CASCADE, related_name="registros"
    )
    fecha = models.DateField("fecha")
    completada = models.BooleanField("completada", default=False)
    evidencia_texto = models.TextField("evidencia", blank=True)
    evidencia_url = models.URLField("enlace de evidencia", blank=True)
    xp_otorgado = models.IntegerField("XP otorgada", default=0)
    notas = models.TextField("notas", blank=True)

    class Meta:
        verbose_name = "registro de mision"
        verbose_name_plural = "registros de misiones"
        ordering = ["-fecha", "mission__orden"]
        constraints = [
            models.UniqueConstraint(
                fields=["mission", "fecha"], name="missionlog_unica_por_dia"
            )
        ]
        indexes = [
            models.Index(fields=["-fecha"], name="missionlog_fecha_idx"),
            models.Index(fields=["fecha", "completada"], name="missionlog_fecha_comp_idx"),
            models.Index(fields=["mission", "-fecha"], name="missionlog_mis_fecha_idx"),
        ]

    def __str__(self):
        estado = "hecha" if self.completada else "pendiente"
        return f"{self.mission.titulo} · {self.fecha} · {estado}"
