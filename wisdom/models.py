from django.db import models


class Maxim(models.Model):
    """Maxima del decalogo operativo (docs/sistema-v3-maquiavelo.md)."""

    numero = models.PositiveSmallIntegerField("numero", unique=True)
    libro = models.CharField("libro", max_length=80, blank=True)
    titulo = models.CharField("titulo", max_length=200)
    principio = models.TextField("principio", blank=True)
    texto = models.TextField("texto")
    aplicacion = models.TextField("aplicacion concreta", blank=True)
    tags = models.CharField(
        "etiquetas", max_length=200, blank=True, help_text="Separadas por comas."
    )

    class Meta:
        verbose_name = "maxima"
        verbose_name_plural = "maximas"
        ordering = ["numero"]
        indexes = [
            models.Index(fields=["numero"], name="maxim_numero_idx"),
            models.Index(fields=["libro"], name="maxim_libro_idx"),
        ]

    def __str__(self):
        return f"{self.numero}. {self.titulo}"


class SystemPrompt(models.Model):
    """Prompt de sistema con el que se consulta al modelo."""

    # El slug NO es único: identifica al prompt, y cada fila es una versión suya.
    # La unicidad real es (slug, version), abajo en Meta.
    slug = models.SlugField("slug", max_length=60)
    nombre = models.CharField("nombre", max_length=160)
    contenido = models.TextField("contenido")
    activo = models.BooleanField("activo", default=True)
    version = models.PositiveSmallIntegerField("version", default=1)

    class Meta:
        verbose_name = "prompt de sistema"
        verbose_name_plural = "prompts de sistema"
        ordering = ["slug", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["slug", "version"], name="systemprompt_slug_version_unicos"
            )
        ]
        indexes = [
            models.Index(fields=["slug"], name="systemprompt_slug_idx"),
            models.Index(fields=["activo"], name="systemprompt_activo_idx"),
        ]

    def __str__(self):
        return f"{self.nombre} v{self.version}{'' if self.activo else ' (inactivo)'}"


class AdviceSession(models.Model):
    """Consulta al modelo, con su coste. Lo que no se mide, se dispara."""

    fecha = models.DateTimeField("fecha")
    pregunta = models.TextField("pregunta")
    contexto_json = models.JSONField("contexto", default=dict, blank=True)
    respuesta = models.TextField("respuesta", blank=True)
    modelo = models.CharField("modelo", max_length=80, blank=True)
    tokens_in = models.PositiveIntegerField("tokens de entrada", default=0)
    tokens_out = models.PositiveIntegerField("tokens de salida", default=0)
    coste_estimado = models.DecimalField(
        "coste estimado (EUR)", max_digits=8, decimal_places=4, default=0
    )
    system_prompt = models.ForeignKey(
        SystemPrompt,
        verbose_name="prompt usado",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sesiones",
    )

    class Meta:
        verbose_name = "consulta al consejo"
        verbose_name_plural = "consultas al consejo"
        ordering = ["-fecha"]
        indexes = [
            models.Index(fields=["-fecha"], name="advice_fecha_idx"),
            models.Index(fields=["modelo", "-fecha"], name="advice_modelo_idx"),
        ]

    def __str__(self):
        return f"{self.fecha:%Y-%m-%d %H:%M} · {self.pregunta[:60]}"
