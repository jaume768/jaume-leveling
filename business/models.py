from decimal import Decimal

from django.db import models
from django.utils import timezone


class Client(models.Model):
    """Cliente. El MRR es el ingreso recurrente que aporta cada mes."""

    class Estado(models.TextChoices):
        ACTIVO = "ACTIVO", "Activo"
        INACTIVO = "INACTIVO", "Inactivo"
        POTENCIAL = "POTENCIAL", "Potencial"
        PERDIDO = "PERDIDO", "Perdido"

    nombre = models.CharField("nombre", max_length=160)
    slug = models.SlugField("slug", max_length=160, unique=True)
    sector = models.CharField("sector", max_length=120, blank=True)
    url = models.URLField("web", blank=True)
    estado = models.CharField(
        "estado", max_length=10, choices=Estado.choices, default=Estado.ACTIVO
    )
    mrr = models.DecimalField(
        "recurrente (EUR/mes)", max_digits=10, decimal_places=2, default=0
    )
    fecha_alta = models.DateField("fecha de alta", default=timezone.localdate)
    notas = models.TextField("notas", blank=True)

    class Meta:
        verbose_name = "cliente"
        verbose_name_plural = "clientes"
        ordering = ["nombre"]
        indexes = [
            models.Index(fields=["slug"], name="client_slug_idx"),
            models.Index(fields=["estado"], name="client_estado_idx"),
            models.Index(fields=["sector"], name="client_sector_idx"),
            models.Index(fields=["-fecha_alta"], name="client_alta_idx"),
        ]

    def __str__(self):
        if self.mrr:
            return f"{self.nombre} ({self.mrr} EUR/mes)"
        return self.nombre


class Deal(models.Model):
    """Fila del pipeline. Un contacto o una oportunidad viva."""

    class Estado(models.TextChoices):
        CONTACTADO = "CONTACTADO", "Contactado"
        CONVERSANDO = "CONVERSANDO", "Conversando"
        PROPUESTA = "PROPUESTA", "Propuesta enviada"
        GANADO = "GANADO", "Ganado"
        PERDIDO = "PERDIDO", "Perdido"

    ESTADOS_ABIERTOS = (Estado.CONTACTADO, Estado.CONVERSANDO, Estado.PROPUESTA)

    negocio = models.CharField("negocio", max_length=160)
    contacto = models.CharField("contacto", max_length=160, blank=True)
    canal = models.CharField(
        "canal", max_length=120, blank=True, help_text="Referido, gimnasio, frio, entrante..."
    )
    sector = models.CharField("sector", max_length=120, blank=True)
    estado = models.CharField(
        "estado", max_length=12, choices=Estado.choices, default=Estado.CONTACTADO
    )
    valor_potencial = models.DecimalField(
        "valor potencial (EUR)", max_digits=10, decimal_places=2, default=0
    )
    fecha_primer_contacto = models.DateField("primer contacto", default=timezone.localdate)
    ultimo_toque = models.DateField("ultimo toque", null=True, blank=True)
    proximo_paso = models.CharField("proximo paso", max_length=255, blank=True)
    fecha_proximo_paso = models.DateField("fecha del proximo paso", null=True, blank=True)
    motivo_perdida = models.TextField(
        "motivo de perdida",
        blank=True,
        help_text="Un 'no' explicado vale mas que diez conversaciones agradables.",
    )
    client = models.ForeignKey(
        Client,
        verbose_name="cliente",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="oportunidades",
    )

    class Meta:
        verbose_name = "oportunidad"
        verbose_name_plural = "pipeline"
        ordering = ["-fecha_primer_contacto"]
        indexes = [
            models.Index(fields=["estado"], name="deal_estado_idx"),
            models.Index(fields=["-fecha_primer_contacto"], name="deal_primer_contacto_idx"),
            models.Index(fields=["ultimo_toque"], name="deal_ultimo_toque_idx"),
            models.Index(fields=["fecha_proximo_paso"], name="deal_prox_paso_idx"),
            models.Index(fields=["estado", "ultimo_toque"], name="deal_estado_toque_idx"),
        ]

    def __str__(self):
        return f"{self.negocio} · {self.get_estado_display()}"

    @property
    def esta_abierto(self) -> bool:
        return self.estado in self.ESTADOS_ABIERTOS

    @property
    def dias_sin_toque(self) -> int | None:
        """Dias desde el ultimo contacto. None si la oportunidad esta cerrada."""
        if not self.esta_abierto:
            return None
        referencia = self.ultimo_toque or self.fecha_primer_contacto
        if referencia is None:
            return None
        return max(0, (timezone.localdate() - referencia).days)


class Invoice(models.Model):
    """Factura emitida. La regla dura: reclamar al dia 15 de vencimiento."""

    DIAS_PARA_RECLAMAR = 15

    client = models.ForeignKey(
        Client, verbose_name="cliente", on_delete=models.PROTECT, related_name="facturas"
    )
    concepto = models.CharField("concepto", max_length=255)
    importe = models.DecimalField("importe (EUR)", max_digits=10, decimal_places=2)
    fecha_emision = models.DateField("fecha de emision", default=timezone.localdate)
    vencimiento = models.DateField("vencimiento")
    cobrada = models.BooleanField("cobrada", default=False)
    fecha_cobro = models.DateField("fecha de cobro", null=True, blank=True)
    notas = models.TextField("notas", blank=True)

    class Meta:
        verbose_name = "factura"
        verbose_name_plural = "facturas"
        ordering = ["-fecha_emision"]
        indexes = [
            models.Index(fields=["cobrada"], name="invoice_cobrada_idx"),
            models.Index(fields=["vencimiento"], name="invoice_vencimiento_idx"),
            models.Index(fields=["-fecha_emision"], name="invoice_emision_idx"),
            models.Index(fields=["cobrada", "vencimiento"], name="invoice_cobrada_venc_idx"),
        ]

    def __str__(self):
        estado = "cobrada" if self.cobrada else "pendiente"
        return f"{self.client.nombre} · {self.importe} EUR · {estado}"

    @property
    def dias_vencida(self) -> int:
        """Dias de retraso sobre el vencimiento. 0 si esta cobrada o en plazo."""
        if self.cobrada or not self.vencimiento:
            return 0
        return max(0, (timezone.localdate() - self.vencimiento).days)

    @property
    def hay_que_reclamar(self) -> bool:
        return self.dias_vencida >= self.DIAS_PARA_RECLAMAR


class Project(models.Model):
    """Proyecto entregable. El WIP maximo del sistema es 2 proyectos activos."""

    class Estado(models.TextChoices):
        ACTIVO = "ACTIVO", "Activo"
        ENTREGADO = "ENTREGADO", "Entregado"
        CONGELADO = "CONGELADO", "Congelado"

    client = models.ForeignKey(
        Client, verbose_name="cliente", on_delete=models.PROTECT, related_name="proyectos"
    )
    nombre = models.CharField("nombre", max_length=160)
    precio = models.DecimalField("precio (EUR)", max_digits=10, decimal_places=2, default=0)
    horas_estimadas = models.DecimalField(
        "horas estimadas", max_digits=6, decimal_places=1, default=0
    )
    horas_reales = models.DecimalField(
        "horas reales", max_digits=6, decimal_places=1, default=0
    )
    estado = models.CharField(
        "estado", max_length=10, choices=Estado.choices, default=Estado.ACTIVO
    )
    fecha_inicio = models.DateField("fecha de inicio", default=timezone.localdate)
    fecha_entrega = models.DateField("fecha de entrega", null=True, blank=True)

    class Meta:
        verbose_name = "proyecto"
        verbose_name_plural = "proyectos"
        ordering = ["-fecha_inicio"]
        indexes = [
            models.Index(fields=["estado"], name="project_estado_idx"),
            models.Index(fields=["-fecha_inicio"], name="project_inicio_idx"),
            models.Index(fields=["fecha_entrega"], name="project_entrega_idx"),
        ]

    def __str__(self):
        return f"{self.nombre} · {self.client.nombre} ({self.precio} EUR)"

    @property
    def tarifa_efectiva(self) -> Decimal | None:
        """EUR por hora realmente conseguidos. El juez incorruptible."""
        if not self.horas_reales:
            return None
        return (self.precio / self.horas_reales).quantize(Decimal("0.01"))
