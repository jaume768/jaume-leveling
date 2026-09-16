"""Carga las misiones de docs/sistema-v2.md, sección 5.

Los valores (XP, tiempo, definicion de terminada y motivo) salen del documento.
Las excepciones estan marcadas con el comentario INVENTADO.
"""
from django.db import migrations

MISIONES = [
    # --- Diarias (máximo 2 obligatorias, 25-40 min) ---
    {
        "titulo": "D1 · Acción comercial",
        "tipo": "DIARIA",
        "orden": 1,
        "descripcion": "1 contacto nuevo o 1 seguimiento.",
        "definicion_terminada": "Enviado y anotado en el pipeline",
        "tiempo_estimado_min": 15,
        "xp": 30,
        "motivo": "Es lo único que impide el cero del mes siguiente.",
        "evidencia_requerida": True,
    },
    {
        "titulo": "D1 mínima · Un mensaje de tres líneas",
        "tipo": "DIARIA",
        "orden": 1,
        "es_minima": True,
        "descripcion": (
            "Versión de día malo: cansancio, urgencia o viaje. Un mensaje de tres "
            "líneas basta para mantener la racha."
        ),
        "definicion_terminada": "Mensaje enviado",
        "tiempo_estimado_min": 3,
        "xp": 15,  # INVENTADO: el documento no puntua la version mínima.
        "motivo": "Mantiene la racha sin fingir un día normal.",
        "evidencia_requerida": True,
    },
    {
        "titulo": "D2 · Cierre del día",
        "tipo": "DIARIA",
        "orden": 2,
        "descripcion": "5 min, 2 tareas para mañana.",
        "definicion_terminada": "Anotadas",
        "tiempo_estimado_min": 5,
        "xp": 15,
        "motivo": "Ataca tu atributo más bajo: organización.",
    },
    {
        "titulo": "D2 mínima · Dos tareas para mañana",
        "tipo": "DIARIA",
        "orden": 2,
        "es_minima": True,
        "definicion_terminada": "Anotadas",
        "tiempo_estimado_min": 2,
        "xp": 10,  # INVENTADO: el documento no puntua la version mínima.
        "motivo": "Que mañana no empiece en blanco.",
    },
    # --- Semanales ---
    {
        "titulo": "S1 · 6 contactos acumulados",
        "tipo": "SEMANAL",
        "orden": 1,
        "descripcion": "Incluido en D1.",
        "definicion_terminada": "6 filas nuevas en el pipeline",
        "tiempo_estimado_min": 0,
        "xp": 100,
        "motivo": "Pipeline sostenido entregues o no. Es tu punto de fuga historico.",
    },
    {
        "titulo": "S2 · 1 entregable visible",
        "tipo": "SEMANAL",
        "orden": 2,
        "definicion_terminada": "Enviado o publicado",
        "tiempo_estimado_min": 270,
        "xp": 120,
        "motivo": "Con 10 h/semana, la velocidad es dinero.",
    },
    {
        "titulo": "S3 · 2 publicaciones sobre trabajo real",
        "tipo": "SEMANAL",
        "orden": 3,
        "definicion_terminada": "Publicadas",
        "tiempo_estimado_min": 50,
        "xp": 80,
        "motivo": "Tienes 4 webs live y 0 casos. Es marca gratis tirada a la basura.",
        "evidencia_requerida": True,
    },
    {
        "titulo": "S4 · Revisión semanal (domingo 20:15)",
        "tipo": "SEMANAL",
        "orden": 4,
        "descripcion": "Vaciar bandeja, actualizar pipeline y cobros, panel y 3 objetivos.",
        "definicion_terminada": "Panel actualizado + 3 objetivos",
        "tiempo_estimado_min": 40,
        "xp": 60,
        "motivo": "8 revisiones seguidas es lo que mueve organización.",
    },
    {
        "titulo": "S5 · 4 entrenos",
        "tipo": "SEMANAL",
        "orden": 5,
        "descripcion": "Lunes, martes, jueves y viernes. Miércoles: descanso total.",
        "definicion_terminada": "Cumplidos",
        "tiempo_estimado_min": 0,
        "xp": 80,
        "motivo": "Adherencia: el único predictor real a largo plazo.",
    },
    {
        "titulo": "S6 · Bloques con Alexandra intactos",
        "tipo": "SEMANAL",
        "orden": 6,
        "descripcion": "Miércoles, sábado tarde y domingo. 0 cancelaciones.",
        "definicion_terminada": "Cumplidos",
        "tiempo_estimado_min": 0,
        # El documento agrupa S5 y S6 en una fila con "80 + 40". Se separan para
        # poder marcarlas por separado; la XP de cada parte es la del documento.
        "xp": 40,
        "motivo": "Si el sistema no respeta tus límites, lo abandonarás en seis semanas.",
    },
    # --- Mensuales ---
    {
        "titulo": "M1 · 2 propuestas formales enviadas",
        "tipo": "MENSUAL",
        "orden": 1,
        "definicion_terminada": "2 propuestas enviadas",
        "xp": 200,
        "motivo": "Sin propuestas no hay cierres.",
    },
    {
        "titulo": "M2 · 1 cierre o renovación",
        "tipo": "MENSUAL",
        "orden": 2,
        "definicion_terminada": "Contrato firmado o renovado",
        "xp": 300,
        "motivo": "Es el resultado, no la actividad.",
    },
    {
        "titulo": "M3 · 0 EUR pendientes de cobro fuera de plazo",
        "tipo": "MENSUAL",
        "orden": 3,
        "definicion_terminada": "Ninguna factura vencida sin reclamar",
        "xp": 200,
        "motivo": "2.000 EUR pendientes es la prueba de que falta cobrar a tiempo.",
    },
    {
        "titulo": "M4 · 1 caso de estudio publicado con número",
        "tipo": "MENSUAL",
        "orden": 4,
        "definicion_terminada": "Publicado, con un resultado medible dentro",
        "xp": 150,
        "motivo": "Prueba objetiva que sustituye a tu palabra.",
        "evidencia_requerida": True,
    },
    {
        "titulo": "M5 · Calibración del sistema",
        "tipo": "MENSUAL",
        "orden": 5,
        "descripcion": (
            "Si la XP sube sin subir ingresos, reduce a la mitad la XP de soporte. "
            "Revisión de precio si aceptan más de 8 de cada 10 presupuestos."
        ),
        "definicion_terminada": "Sistema recalibrado por escrito",
        "tiempo_estimado_min": 60,
        "xp": 100,
        "motivo": "Un sistema que no se calibra se convierte en decorado.",
    },
    # --- Principales ---
    {
        "titulo": "Cobro y Cierre",
        "tipo": "PRINCIPAL",
        "orden": 1,
        "descripcion": "Semanas 1-2.",
        "definicion_terminada": (
            "Los 2.000 EUR de Felycampo en cuenta + mantenimiento ofrecido a los 4 clientes"
        ),
        "xp": 600,
        "motivo": "Es dinero ya ganado. Cobrarlo es trabajo administrativo, no comercial.",
    },
    {
        "titulo": "Renta",
        "tipo": "PRINCIPAL",
        "orden": 2,
        "descripcion": "Semanas 1-6.",
        "definicion_terminada": "450 EUR/mes recurrentes firmados o más",
        "xp": 900,
        "motivo": "El dinero más barato que existe: clientes que ya confían en ti.",
    },
    {
        "titulo": "El Suelo",
        "tipo": "PRINCIPAL",
        "orden": 3,
        "descripcion": "Semanas 4-13.",
        "definicion_terminada": (
            "2 proyectos cerrados a 1.500 EUR o más, y uno rechazado por precio bajo"
        ),
        "xp": 1000,
        "motivo": "Es una prueba de carácter, no de negocio.",
    },
    {
        "titulo": "Vertical",
        "tipo": "PRINCIPAL",
        "orden": 4,
        "descripcion": "Meses 3-7.",
        "definicion_terminada": "3 clientes del mismo sector + una oferta con el nombre del sector",
        "xp": 1200,
        "motivo": "No conquistes diez sectores. Habita uno.",
    },
    {
        "titulo": "Multiplicador",
        "tipo": "PRINCIPAL",
        "orden": 5,
        "descripcion": "Meses 6-12.",
        "definicion_terminada": "Plantilla + automatización que recorten un 40% el tiempo de entrega",
        "xp": 1500,
        "motivo": "Que 10 h/semana produzcan lo que hoy producirian 25.",
    },
]


def cargar_misiones(apps, schema_editor):
    Mission = apps.get_model("missions", "Mission")
    for datos in MISIONES:
        Mission.objects.update_or_create(
            titulo=datos["titulo"], defaults={**datos, "activa": True}
        )


def borrar_misiones(apps, schema_editor):
    Mission = apps.get_model("missions", "Mission")
    Mission.objects.filter(titulo__in=[d["titulo"] for d in MISIONES]).delete()


class Migration(migrations.Migration):
    dependencies = [("missions", "0001_initial")]
    operations = [migrations.RunPython(cargar_misiones, borrar_misiones)]
