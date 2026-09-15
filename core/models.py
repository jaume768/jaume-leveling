from django.db import models
from django.utils import timezone

from . import services


class Rank(models.Model):
    """Rango del sistema: el tramo de niveles y la prueba que lo cierra."""

    nombre = models.CharField("nombre", max_length=80, unique=True)
    orden = models.PositiveSmallIntegerField("orden", unique=True)
    nivel_min = models.PositiveSmallIntegerField("nivel minimo")
    nivel_max = models.PositiveSmallIntegerField("nivel maximo")
    objetivo = models.TextField("objetivo", blank=True)
    criterio_ascenso = models.TextField("criterio de ascenso", blank=True)
    jefe = models.CharField("jefe de rango", max_length=120, blank=True)

    class Meta:
        verbose_name = "rango"
        verbose_name_plural = "rangos"
        ordering = ["orden"]
        indexes = [models.Index(fields=["orden"], name="rank_orden_idx")]

    def __str__(self):
        return f"{self.orden}. {self.nombre} (niveles {self.nivel_min}-{self.nivel_max})"

    @property
    def emblema(self) -> str:
        """Ruta estatica del emblema del rango, o cadena vacia si no lo tiene.

        Se ata al orden, no al nombre: renombrar un rango desde el admin no
        deberia dejarlo sin insignia.
        """
        from . import services

        return services.emblema_de_rango(self.orden)


class Profile(models.Model):
    """Perfil del unico usuario del sistema. Singleton: usa Profile.get()."""

    NIVEL_INICIAL = 45

    nivel = models.PositiveSmallIntegerField("nivel", default=NIVEL_INICIAL)
    xp_total = models.IntegerField("XP total", default=0)
    rango = models.ForeignKey(
        Rank,
        verbose_name="rango",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="perfiles",
    )
    fecha_inicio = models.DateField("fecha de inicio", default=timezone.localdate)
    altura_cm = models.PositiveSmallIntegerField("altura (cm)", default=175)
    peso_objetivo = models.DecimalField(
        "peso objetivo (kg)", max_digits=5, decimal_places=2, default=77
    )

    class Meta:
        verbose_name = "perfil"
        verbose_name_plural = "perfil"

    def __str__(self):
        rango = self.rango.nombre if self.rango else "sin rango"
        return f"{rango} · nivel {self.nivel} · {self.xp_total} XP"

    @classmethod
    def get(cls) -> "Profile":
        """Devuelve el perfil unico, creandolo la primera vez."""
        perfil = cls.objects.first()
        if perfil is None:
            perfil = cls.objects.create(
                nivel=cls.NIVEL_INICIAL,
                xp_total=services.xp_acumulada_hasta_nivel(cls.NIVEL_INICIAL),
            )
        return perfil

    def save(self, *args, **kwargs):
        # Blindaje del singleton: nunca hay un segundo perfil. Si alguien crea
        # uno nuevo teniendo ya perfil, se sobrescribe el existente.
        if not self.pk:
            existente = Profile.objects.values_list("pk", flat=True).first()
            if existente is not None:
                self.pk = existente
                kwargs.pop("force_insert", None)
                args = ()
        super().save(*args, **kwargs)

    @property
    def xp_en_nivel(self) -> int:
        """XP acumulada dentro del nivel actual."""
        return services.progreso_en_nivel(self.nivel, self.xp_total)[0]

    @property
    def xp_para_siguiente_nivel(self) -> int:
        """XP que faltan para subir de nivel."""
        return services.progreso_en_nivel(self.nivel, self.xp_total)[1]

    @property
    def progreso_nivel_pct(self) -> int:
        """Porcentaje recorrido del nivel actual (0-100), entero."""
        return services.progreso_en_nivel(self.nivel, self.xp_total)[2]


class Attribute(models.Model):
    """Atributo de la hoja de personaje (0-100)."""

    class Categoria(models.TextChoices):
        NEGOCIO = "NEGOCIO", "Negocio"
        TECNICA = "TECNICA", "Tecnica"
        PERSONAL = "PERSONAL", "Personal"
        SALUD = "SALUD", "Salud"

    nombre = models.CharField("nombre", max_length=80)
    slug = models.SlugField("slug", max_length=80, unique=True)
    valor = models.PositiveSmallIntegerField("valor", default=0)
    categoria = models.CharField(
        "categoria", max_length=20, choices=Categoria.choices, default=Categoria.NEGOCIO
    )
    evidencia = models.TextField(
        "evidencia",
        blank=True,
        help_text="Por que el atributo vale lo que vale, con hechos.",
    )
    siguiente_hito = models.TextField(
        "que mueve el siguiente +10",
        blank=True,
        help_text="Lo concreto que hay que hacer para subirlo diez puntos.",
    )

    class Meta:
        verbose_name = "atributo"
        verbose_name_plural = "atributos"
        ordering = ["categoria", "-valor"]
        indexes = [
            models.Index(fields=["slug"], name="attribute_slug_idx"),
            models.Index(fields=["categoria"], name="attribute_categoria_idx"),
        ]

    def __str__(self):
        return f"{self.nombre}: {self.valor}"


class AttributeLog(models.Model):
    """Cada cambio de valor de un atributo, con su motivo."""

    attribute = models.ForeignKey(
        Attribute, verbose_name="atributo", on_delete=models.CASCADE, related_name="registros"
    )
    fecha = models.DateField("fecha")
    valor = models.PositiveSmallIntegerField("valor")
    nota = models.TextField("nota", blank=True)

    class Meta:
        verbose_name = "registro de atributo"
        verbose_name_plural = "registros de atributos"
        ordering = ["-fecha"]
        indexes = [
            models.Index(fields=["-fecha"], name="attrlog_fecha_idx"),
            models.Index(fields=["attribute", "-fecha"], name="attrlog_attr_fecha_idx"),
        ]

    def __str__(self):
        return f"{self.attribute.nombre} = {self.valor} ({self.fecha})"
