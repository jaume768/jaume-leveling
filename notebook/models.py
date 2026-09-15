from django.db import models
from django.utils import timezone


class Note(models.Model):
    """Una nota suelta del cuaderno.

    No cuelga de ninguna mision: es para lo que se te ocurre y no tiene sitio
    todavia. Las notas de mision viven en MissionLog.notas y el cuaderno las
    muestra junto a estas, pero son cosas distintas.
    """

    titulo = models.CharField("titulo", max_length=160, blank=True)
    contenido = models.TextField("contenido")
    fecha = models.DateField("fecha", default=timezone.localdate)
    fijada = models.BooleanField(
        "fijada",
        default=False,
        help_text="Las fijadas se quedan arriba, fuera del orden por fecha.",
    )
    creada = models.DateTimeField("creada", auto_now_add=True)
    actualizada = models.DateTimeField("actualizada", auto_now=True)

    class Meta:
        verbose_name = "nota"
        verbose_name_plural = "notas"
        ordering = ["-fecha", "-creada"]
        indexes = [
            models.Index(fields=["-fecha"], name="note_fecha_idx"),
            models.Index(fields=["fijada", "-fecha"], name="note_fijada_fecha_idx"),
        ]

    def __str__(self):
        return self.titulo or self.contenido[:60]

    @property
    def encabezado(self) -> str:
        """Lo que se pinta como titulo aunque no lo tenga."""
        if self.titulo:
            return self.titulo
        primera = self.contenido.strip().splitlines()[0] if self.contenido.strip() else ""
        return primera[:80]
