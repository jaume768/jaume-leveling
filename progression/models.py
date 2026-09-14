from django.db import models


class Categoria(models.TextChoices):
    """Categorias de la tabla de XP (docs/sistema-v2.md, §6)."""

    RESULTADO = "RESULTADO", "Resultado"
    SOPORTE = "SOPORTE", "Soporte"
    CONSUMO = "CONSUMO", "Consumo"
    PENALIZACION = "PENALIZACION", "Penalizacion"


class XPRule(models.Model):
    """Regla de puntuacion: cuanta XP da una accion y cual es su tope semanal."""

    accion_slug = models.SlugField("slug de la accion", max_length=60, unique=True)
    nombre = models.CharField("nombre", max_length=160)
    xp = models.IntegerField("XP")
    tope_semanal = models.IntegerField(
        "tope semanal", null=True, blank=True, help_text="Vacio = sin tope."
    )
    categoria = models.CharField(
        "categoria", max_length=14, choices=Categoria.choices, default=Categoria.RESULTADO
    )
    activa = models.BooleanField("activa", default=True)

    class Meta:
        verbose_name = "regla de XP"
        verbose_name_plural = "reglas de XP"
        ordering = ["categoria", "-xp"]
        indexes = [
            models.Index(fields=["accion_slug"], name="xprule_slug_idx"),
            models.Index(fields=["categoria", "activa"], name="xprule_cat_activa_idx"),
        ]

    def __str__(self):
        tope = f" (tope {self.tope_semanal}/sem)" if self.tope_semanal else ""
        return f"{self.nombre}: {self.xp} XP{tope}"


class XPEvent(models.Model):
    """Cada XP concedida o restada, con el tope y la racha ya aplicados."""

    class Fuente(models.TextChoices):
        MISION = "MISION", "Mision"
        MANUAL = "MANUAL", "Manual"
        AUTO = "AUTO", "Automatica"

    fecha = models.DateField("fecha")
    categoria = models.CharField("categoria", max_length=14, choices=Categoria.choices)
    accion_slug = models.SlugField("slug de la accion", max_length=60)
    descripcion = models.CharField("descripcion", max_length=255, blank=True)
    xp_bruto = models.IntegerField("XP bruta")
    xp_neto = models.IntegerField("XP neta")
    tope_aplicado = models.BooleanField("tope aplicado", default=False)
    multiplicador_racha = models.DecimalField(
        "multiplicador de racha", max_digits=4, decimal_places=2, default=1
    )
    fuente = models.CharField(
        "fuente", max_length=8, choices=Fuente.choices, default=Fuente.MANUAL
    )
    objeto_relacionado = models.CharField(
        "objeto relacionado",
        max_length=120,
        blank=True,
        help_text="Referencia libre, p. ej. 'invoice:12' o 'deal:4'.",
    )

    class Meta:
        verbose_name = "evento de XP"
        verbose_name_plural = "eventos de XP"
        ordering = ["-fecha", "-id"]
        indexes = [
            models.Index(fields=["-fecha"], name="xpevent_fecha_idx"),
            models.Index(fields=["accion_slug", "-fecha"], name="xpevent_slug_fecha_idx"),
            models.Index(fields=["categoria", "-fecha"], name="xpevent_cat_fecha_idx"),
        ]

    def __str__(self):
        return f"{self.fecha} · {self.accion_slug} · {self.xp_neto:+} XP"


class Penalty(models.Model):
    """Penalizacion aplicada. Siempre lleva correccion exigida."""

    fecha = models.DateField("fecha")
    regla_slug = models.SlugField("slug de la regla", max_length=60)
    descripcion = models.CharField("descripcion", max_length=255)
    xp = models.IntegerField("XP", help_text="Negativa.")
    correccion_exigida = models.TextField("correccion exigida")
    resuelta = models.BooleanField("resuelta", default=False)

    class Meta:
        verbose_name = "penalizacion"
        verbose_name_plural = "penalizaciones"
        ordering = ["-fecha"]
        indexes = [
            models.Index(fields=["-fecha"], name="penalty_fecha_idx"),
            models.Index(fields=["resuelta", "-fecha"], name="penalty_resuelta_idx"),
            models.Index(fields=["regla_slug"], name="penalty_regla_idx"),
        ]

    def __str__(self):
        estado = "resuelta" if self.resuelta else "PENDIENTE"
        return f"{self.fecha} · {self.descripcion} ({self.xp} XP, {estado})"


class Reward(models.Model):
    """Recompensa que se desbloquea por nivel o por rango."""

    titulo = models.CharField("titulo", max_length=160)
    descripcion = models.TextField("descripcion", blank=True)
    nivel_requerido = models.PositiveSmallIntegerField(
        "nivel requerido", null=True, blank=True
    )
    rango = models.ForeignKey(
        "core.Rank",
        verbose_name="rango requerido",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recompensas",
    )
    desbloqueada = models.BooleanField("desbloqueada", default=False)
    fecha = models.DateField("fecha de desbloqueo", null=True, blank=True)

    class Meta:
        verbose_name = "recompensa"
        verbose_name_plural = "recompensas"
        ordering = ["nivel_requerido", "titulo"]
        indexes = [
            models.Index(fields=["desbloqueada"], name="reward_desbloqueada_idx"),
            models.Index(fields=["nivel_requerido"], name="reward_nivel_idx"),
        ]

    def __str__(self):
        if self.nivel_requerido:
            requisito = f"nivel {self.nivel_requerido}"
        elif self.rango_id:
            requisito = self.rango.nombre
        else:
            requisito = "sin requisito"
        return f"{self.titulo} ({requisito})"
