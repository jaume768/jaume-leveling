"""Carga la tabla de XP de docs/sistema-v2.md, seccion 6.

Cada fila del documento es una XPRule. El tope semanal vacio significa sin tope.
"""
from django.db import migrations

REGLAS = [
    # --- Resultados ---
    ("contrato-recurrente-firmado", "Contrato recurrente firmado", 350, None, "RESULTADO"),
    ("proyecto-cerrado", "Contrato de proyecto cerrado (1.500 € o más)", 250, None, "RESULTADO"),
    ("dinero-cobrado", "Dinero cobrado (1 XP por cada 10 €)", 1, 400, "RESULTADO"),
    ("entrega-aceptada", "Entrega aceptada por el cliente", 200, None, "RESULTADO"),
    ("propuesta-enviada", "Propuesta formal enviada", 80, 240, "RESULTADO"),
    ("conversacion-comercial", "Conversación comercial real (10 min o más)", 60, 300, "RESULTADO"),
    ("proyecto-rechazado-precio-bajo", "Proyecto rechazado por precio bajo", 150, 150, "RESULTADO"),
    ("peticion-referido", "Petición de referido hecha", 50, 150, "RESULTADO"),
    ("testimonio-o-caso", "Testimonio o caso publicado", 100, None, "RESULTADO"),
    ("automatizacion-propia", "Automatización propia con ahorro medido", 120, 240, "RESULTADO"),
    ("publicacion-contenido-real", "Publicación con contenido real", 40, 80, "RESULTADO"),
    # INVENTADO: el documento puntúa la acción comercial como misión diaria (D1,
    # 30 XP) pero no le da una fila propia en la tabla. El toque rápido del
    # pipeline usa esta regla.
    ("accion-comercial", "Acción comercial: contacto nuevo o seguimiento", 30, None, "RESULTADO"),
    # --- Soporte ---
    ("entreno", "Entreno según plan", 20, 80, "SOPORTE"),
    ("sueno-7h", "Sueño de 7 h o más", 10, 50, "SOPORTE"),
    ("bloques-alexandra", "Bloques con Alexandra intactos toda la semana", 40, 40, "SOPORTE"),
    ("revision-semanal", "Revisión semanal", 60, 60, "SOPORTE"),
    # --- Consumo ---
    ("curso-con-artefacto", "Curso o vídeo con artefacto aplicado el mismo día", 10, 20, "CONSUMO"),
    # --- Penalizaciones ---
    ("semana-sin-comercial", "Semana con 0 acciones comerciales", -150, None, "PENALIZACION"),
    ("factura-vencida-sin-reclamar", "Factura vencida más de 15 días sin reclamar", -200, None, "PENALIZACION"),
    ("proyecto-por-debajo-del-suelo", "Aceptar un proyecto por debajo de 1.500 €", -250, None, "PENALIZACION"),
    ("propuesta-sin-seguimiento", "Propuesta sin seguimiento más de 7 días", -100, None, "PENALIZACION"),
    ("exceso-wip", "3 proyectos abiertos a la vez", -100, None, "PENALIZACION"),
    ("bloque-alexandra-cancelado", "Cancelar un bloque con Alexandra por trabajo", -150, None, "PENALIZACION"),
]


def cargar(apps, schema_editor):
    XPRule = apps.get_model("progression", "XPRule")
    for slug, nombre, xp, tope, categoria in REGLAS:
        XPRule.objects.update_or_create(
            accion_slug=slug,
            defaults={
                "nombre": nombre,
                "xp": xp,
                "tope_semanal": tope,
                "categoria": categoria,
                "activa": True,
            },
        )


def borrar(apps, schema_editor):
    XPRule = apps.get_model("progression", "XPRule")
    XPRule.objects.filter(accion_slug__in=[r[0] for r in REGLAS]).delete()


class Migration(migrations.Migration):
    dependencies = [("progression", "0001_initial")]
    operations = [migrations.RunPython(cargar, borrar)]
