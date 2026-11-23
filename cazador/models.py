"""Capa de juego del Sistema: avisos, logros, cofre, escudos y notificaciones.

Nada de esto concede XP. La XP sigue saliendo de hechos registrados en las
demas apps; aqui solo vive lo que hace visible y apetecible ese progreso.
"""
from django.db import models
from django.utils import timezone


class Cazador(models.Model):
    """Ficha cosmetica del jugador. Singleton: usa Cazador.get()."""

    alias = models.CharField("alias de cazador", max_length=40, blank=True)
    titulo_equipado = models.CharField("titulo equipado", max_length=60, blank=True)
    marco = models.CharField("marco equipado", max_length=30, default="sistema")
    fragmentos = models.PositiveSmallIntegerField("fragmentos de runa", default=0)

    class Meta:
        verbose_name = "cazador"
        verbose_name_plural = "cazador"

    def __str__(self):
        return self.alias or "Cazador"

    @classmethod
    def get(cls) -> "Cazador":
        ficha = cls.objects.first()
        if ficha is None:
            ficha = cls.objects.create()
        return ficha


class Aviso(models.Model):
    """Mensaje del Sistema. Se pinta una vez (toast o ventana) y queda visto."""

    class Tipo(models.TextChoices):
        XP = "XP", "XP ganada"
        NIVEL = "NIVEL", "Subida de nivel"
        RANGO = "RANGO", "Ascenso de rango"
        TITULO = "TITULO", "Titulo desbloqueado"
        HABILIDAD = "HABILIDAD", "Habilidad desbloqueada"
        COFRE = "COFRE", "Cofre disponible"
        ESCUDO = "ESCUDO", "Escudo de racha"
        PENALIZACION = "PENALIZACION", "Penalizacion"
        MISION_DIARIA = "MISION_DIARIA", "La mision diaria ha llegado"
        SISTEMA = "SISTEMA", "Sistema"

    # Los que merecen ventana a pantalla completa; el resto va en toast.
    TIPOS_VENTANA = (Tipo.NIVEL, Tipo.RANGO, Tipo.TITULO, Tipo.HABILIDAD, Tipo.MISION_DIARIA)

    creado = models.DateTimeField("creado", default=timezone.now)
    tipo = models.CharField("tipo", max_length=20, choices=Tipo.choices)
    titulo = models.CharField("titulo", max_length=120)
    texto = models.CharField("texto", max_length=255, blank=True)
    valor = models.IntegerField("valor", default=0)
    # Clave de idempotencia: el mismo hecho no avisa dos veces.
    clave = models.CharField("clave", max_length=80, null=True, blank=True, unique=True)
    visto = models.BooleanField("visto", default=False)

    class Meta:
        verbose_name = "aviso del Sistema"
        verbose_name_plural = "avisos del Sistema"
        ordering = ["creado", "pk"]

    def __str__(self):
        return f"[{self.tipo}] {self.titulo}"

    @property
    def es_ventana(self) -> bool:
        return self.tipo in self.TIPOS_VENTANA


class Logro(models.Model):
    """Titulo o habilidad desbloqueados. La definicion vive en services."""

    class Tipo(models.TextChoices):
        TITULO = "TITULO", "Titulo"
        HABILIDAD = "HABILIDAD", "Habilidad"
        MARCO = "MARCO", "Marco"

    tipo = models.CharField("tipo", max_length=12, choices=Tipo.choices)
    clave = models.SlugField("clave", max_length=60)
    fecha = models.DateField("fecha", default=timezone.localdate)

    class Meta:
        verbose_name = "logro"
        verbose_name_plural = "logros"
        constraints = [
            models.UniqueConstraint(fields=["tipo", "clave"], name="logro_unico")
        ]

    def __str__(self):
        return f"{self.get_tipo_display()}: {self.clave}"


class Cofre(models.Model):
    """Cofre del dia: se gana cerrando todas las diarias y se abre una vez."""

    fecha = models.DateField("fecha", unique=True)
    abierto = models.BooleanField("abierto", default=False)
    tipo = models.CharField("tipo de botin", max_length=20, blank=True)
    titulo = models.CharField("botin", max_length=160, blank=True)
    texto = models.TextField("texto", blank=True)

    class Meta:
        verbose_name = "cofre diario"
        verbose_name_plural = "cofres diarios"
        ordering = ["-fecha"]

    def __str__(self):
        return f"Cofre {self.fecha}"


class Escudo(models.Model):
    """Escudo de racha: salva un dia fallado sin romper la cadena."""

    ganado = models.DateField("ganado", default=timezone.localdate)
    motivo = models.CharField("motivo", max_length=160)
    usado_en = models.DateField("usado en", null=True, blank=True, unique=True)

    class Meta:
        verbose_name = "escudo de racha"
        verbose_name_plural = "escudos de racha"
        ordering = ["ganado", "pk"]

    def __str__(self):
        return f"Escudo ({self.motivo})"


class SuscripcionPush(models.Model):
    """Un navegador o movil que acepto las notificaciones del Sistema."""

    endpoint = models.URLField("endpoint", max_length=600, unique=True)
    p256dh = models.CharField("clave p256dh", max_length=200)
    auth = models.CharField("clave auth", max_length=100)
    agente = models.CharField("navegador", max_length=200, blank=True)
    creada = models.DateTimeField("creada", default=timezone.now)

    class Meta:
        verbose_name = "suscripcion push"
        verbose_name_plural = "suscripciones push"

    def __str__(self):
        return self.agente or self.endpoint[:60]


class EnvioPush(models.Model):
    """Registro de notificaciones enviadas: cada aviso programado sale una vez."""

    clave = models.CharField("clave", max_length=80, unique=True)
    enviado = models.DateTimeField("enviado", default=timezone.now)
    destinos = models.PositiveSmallIntegerField("destinos", default=0)

    class Meta:
        verbose_name = "envio push"
        verbose_name_plural = "envios push"

    def __str__(self):
        return self.clave


class HitoAtributo(models.Model):
    """Un +10 reclamado. El indice dice por que escalon de la escalera va."""

    slug = models.SlugField("atributo", max_length=80)
    indice = models.PositiveSmallIntegerField("escalon")
    texto = models.CharField("hito", max_length=255)
    evidencia = models.TextField("evidencia", blank=True)
    automatico = models.BooleanField("detectado por el Sistema", default=False)
    fecha = models.DateField("fecha", default=timezone.localdate)

    class Meta:
        verbose_name = "hito de atributo"
        verbose_name_plural = "hitos de atributo"
        ordering = ["-fecha", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["slug", "indice"], name="hito_unico_por_escalon")
        ]

    def __str__(self):
        return f"{self.slug} #{self.indice}: {self.texto}"


class Portal(models.Model):
    """Portal semanal: un reto de 7 dias con botin. Cada lunes se abren tres."""

    class Estado(models.TextChoices):
        OFRECIDO = "OFRECIDO", "Ofrecido"
        ABIERTO = "ABIERTO", "Abierto"
        SUPERADO = "SUPERADO", "Superado"
        DESBORDADO = "DESBORDADO", "Desbordado"
        DESCARTADO = "DESCARTADO", "Descartado"

    lunes = models.DateField("lunes de la semana")
    dificultad = models.CharField("dificultad", max_length=1)
    tipo = models.SlugField("objetivo", max_length=40)
    atributo = models.SlugField("atributo que entrena", max_length=80, blank=True)
    titulo = models.CharField("titulo", max_length=120)
    descripcion = models.CharField("descripcion", max_length=255)
    objetivo = models.PositiveIntegerField("objetivo")
    estado = models.CharField("estado", max_length=12, choices=Estado.choices, default=Estado.OFRECIDO)
    botin = models.CharField("botin", max_length=255, blank=True)
    cerrado = models.DateField("cerrado", null=True, blank=True)

    class Meta:
        verbose_name = "portal"
        verbose_name_plural = "portales"
        ordering = ["-lunes", "dificultad"]
        constraints = [
            models.UniqueConstraint(fields=["lunes", "dificultad"], name="portal_unico_por_dificultad")
        ]

    def __str__(self):
        return f"Portal {self.dificultad} · {self.titulo} ({self.lunes})"
