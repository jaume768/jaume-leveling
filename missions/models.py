from django.db import models
from django.utils.text import slugify


class Mission(models.Model):
    """Mision del sistema. La definicion de 'terminada' es obligatoria."""

    class Tipo(models.TextChoices):
        DIARIA = "DIARIA", "Diaria"
        SEMANAL = "SEMANAL", "Semanal"
        MENSUAL = "MENSUAL", "Mensual"
        ANUAL = "ANUAL", "Anual"
        PRINCIPAL = "PRINCIPAL", "Principal"

    # Identidad estable. El titulo y el orden son presentacion: se reescriben y
    # se reordenan desde el admin sin que nada del codigo deba enterarse. Lo que
    # el codigo referencia es el slug.
    slug = models.SlugField(
        "slug",
        max_length=60,
        unique=True,
        help_text="Identidad de la mision. No se cambia una vez creada.",
    )
    # Variantes de la misma mision: la version normal y la minima comparten
    # grupo, y solo una de las dos puede completarse cada dia.
    grupo = models.SlugField(
        "grupo de variantes",
        max_length=60,
        blank=True,
        help_text="Vacio = la mision es su propio grupo.",
    )
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
        help_text="Rótulo del cuaderno, p. ej. 'Las dos tareas de mañana'.",
    )
    activa = models.BooleanField("activa", default=True)
    orden = models.PositiveSmallIntegerField("orden", default=0)
    es_minima = models.BooleanField(
        "es version minima",
        default=False,
        help_text="Version reducida que mantiene la racha en un dia malo.",
    )
    cuenta_para_racha = models.BooleanField(
        "cuenta para la racha",
        default=False,
        help_text=(
            "Completarla mantiene viva la racha comercial. Antes esto se "
            "deducia del orden, y reordenar en el admin lo rompia en silencio."
        ),
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

    def save(self, *args, **kwargs):
        """Un slug vacio se deriva del titulo. Asi crear desde el admin sigue
        siendo tan facil como antes, pero la identidad existe desde el minuto
        uno y ya no depende del orden."""
        if not self.slug:
            base = slugify(self.titulo)[:56] or "mision"
            slug = base
            sufijo = 2
            hermanas = Mission.objects.exclude(pk=self.pk)
            while hermanas.filter(slug=slug).exists():
                slug = f"{base}-{sufijo}"
                sufijo += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def clave_de_grupo(self) -> str:
        """Grupo al que pertenece. Sin grupo declarado, la mision es su grupo."""
        return self.grupo or self.slug


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
