"""Amplia el Codice: frases del Sistema, de tu propio sistema v2 y clasicos.

Los numeros 1-22 siguen siendo los libros y el decalogo. A partir del 23 van
las frases nuevas. Las citas clasicas son de autores de dominio publico, en
traduccion libre; las del Sistema y las de sistema-v2 son propias.
"""
from django.db import migrations

# (numero, libro, titulo, texto, aplicacion, tags)
FRASES = [
    # --- El Sistema ---
    (23, "El Sistema", "Presencia", "El Sistema no te pide perfección. Te pide presencia.",
     "Un día malo con la misión mínima vale más que un día perfecto que nunca llega.", "disciplina,sistema"),
    (24, "El Sistema", "Cazar", "Un cazador no espera clientes. Los caza.",
     "Seis contactos a la semana, entregues o no.", "pipeline,sistema"),
    (25, "El Sistema", "La rutina", "El débil espera motivación. El cazador sigue la rutina.",
     "La misión diaria no se negocia con el estado de ánimo.", "disciplina,sistema"),
    (26, "El Sistema", "Subir", "El nivel no se regala: se arranca día a día.",
     "Cada XP que ves es un hecho registrado, no una intención.", "disciplina,sistema"),
    (27, "El Sistema", "El botín", "Cada contacto es una presa. Cada propuesta, un golpe. Cada cobro, botín.",
     "Si no está en el pipeline, no ha pasado.", "pipeline,cobro,sistema"),
    (28, "El Sistema", "Rango S", "Todo rango S fue un día un rango E que no se rindió.",
     "Hoy eres rango D. El Monarca empieza exactamente aquí.", "disciplina,sistema"),
    (29, "El Sistema", "Volver", "Tu ventaja no es el talento: es que vuelves cada día.",
     "La racha es la prueba. Protégela.", "disciplina,sistema"),
    (30, "El Sistema", "Las sombras", "Tus sombras trabajan mientras duermes.",
     "Cada mantenimiento firmado es ingreso que llega sin que tú estés.", "dependencia,sistema"),
    (31, "El Sistema", "Lo barato", "Rechazar lo barato también es ganar.",
     "Un proyecto por debajo del suelo te roba tres semanas de capacidad.", "precio,sistema"),
    (32, "El Sistema", "Medir", "Lo que no se mide, no sube de nivel.",
     "Horas reales por proyecto, cobros, contactos: si no se apunta, no existe.", "foco,sistema"),
    (33, "El Sistema", "Corsoft", "Hoy entrenas para la versión de ti que firma la salida.",
     "Cada misión de hoy es un ladrillo del punto de decisión del mes 12.", "tiempo,sistema"),
    (34, "El Sistema", "El precio", "El miedo a decir un precio cuesta más que cualquier penalización.",
     "Di el número y cállate.", "precio,negociacion,sistema"),
    (35, "El Sistema", "Diez horas", "Diez horas bien usadas valen más que cuarenta perdidas.",
     "Con 10 h/semana, la velocidad es dinero.", "tiempo,foco,sistema"),
    (36, "El Sistema", "La mazmorra", "La mazmorra se limpia planta a planta.",
     "No mires el jefe entero: mira la siguiente planta.", "foco,sistema"),
    (37, "El Sistema", "Cobrar", "Una presa sin cobrar no cuenta.",
     "Factura vencida: reclamación antes que cualquier otra tarea.", "cobro,sistema"),
    (38, "El Sistema", "El escudo", "Si fallas un día, el escudo te cubre. Si fallas dos, eres tú quien decide.",
     "El escudo es para el día malo, no para la semana floja.", "disciplina,sistema"),
    (39, "El Sistema", "Sistemas", "Las tareas se olvidan; los sistemas se quedan.",
     "Plantilla de entrega, guiones de propuesta, automatizaciones: construye una vez, cobra siempre.",
     "foco,sistema"),
    (40, "El Sistema", "Libertad", "La recompensa del cazador no es la XP: es la libertad que compra.",
     "La XP es el marcador. El colchón y el recurrente son la victoria.", "tiempo,sistema"),
    (41, "El Sistema", "El siguiente rango", "Cuando te cueste, piensa en el rango siguiente.",
     "Abre Estado y mira la silueta. Esa versión de ti ya existe si sigues.", "disciplina,sistema"),
    (42, "El Sistema", "Excusas", "No necesitas más tiempo. Necesitas menos excusas por hora.",
     "Quince minutos de acción comercial caben en cualquier día.", "tiempo,disciplina,sistema"),
    (43, "El Sistema", "El portal", "Los portales no esperan. Se cierran el domingo.",
     "Elige el portal el lunes y empieza el lunes.", "tiempo,sistema"),
    # --- Tu sistema v2 ---
    (44, "Sistema v2", "Predecible",
     "Tu problema no es facturar 1.000 €. Es facturarlos todos los meses.",
     "Ingreso predecible y pipeline: todo el sistema ataca eso.", "pipeline,dependencia"),
    (45, "Sistema v2", "La palanca",
     "La palanca no es trabajar más: es subir precio, cobrar recurrente y entregar más rápido.",
     "Antes de aceptar trabajo, pregúntate cuál de las tres mueve.", "precio,foco"),
    (46, "Sistema v2", "Tu red", "Tu red no es cero: es que no la has mirado como red.",
     "Gimnasio, Muay Thai, jiu-jitsu y cuatro clientes. Empieza por ahí.", "pipeline"),
    (47, "Sistema v2", "La tarifa", "El objetivo correcto no es una cantidad, es una tarifa.",
     "40 €/h efectivos o más. Por debajo, el proyecto te cuesta dinero.", "precio"),
    (48, "Sistema v2", "La web de 700", "Aceptar otra web de 700 € es quemar tres semanas de tu capacidad total.",
     "El suelo existe para protegerte de ti mismo.", "precio,tiempo"),
    (49, "Sistema v2", "El número", "Para dejar Corsoft no necesitas 1.880 €: necesitas 1.320 €/mes.",
     "Está más cerca de lo que crees. Hazlo aritmética, no fe.", "tiempo,dependencia"),
    (50, "Sistema v2", "Anti-acumulación", "Ninguna tecnología nueva sin una factura que la exija.",
     "Lo demás va a la lista «Después» y no se toca.", "foco"),
    (51, "Sistema v2", "El dinero más barato",
     "Tus clientes actuales ya confían en ti: ahí está el dinero más barato que existe.",
     "Cuatro conversaciones de mantenimiento antes que un cliente nuevo.", "pipeline,dependencia"),
    # --- Clásicos ---
    (52, "Séneca", "El tiempo", "No es que tengamos poco tiempo, es que perdemos mucho.",
     "Mira dónde se van tus 10 horas de esta semana.", "tiempo,estoicos"),
    (53, "Séneca", "Aplazar", "Mientras se aplaza, la vida pasa.",
     "La propuesta que no envías hoy es la que no cobrarás este mes.", "tiempo,estoicos"),
    (54, "Séneca", "El puerto", "Ningún viento es favorable para quien no sabe a qué puerto se dirige.",
     "Tu puerto: 2.500-3.000 €/mes en el mes 12.", "foco,estoicos"),
    (55, "Séneca", "La imaginación", "Sufrimos más en la imaginación que en la realidad.",
     "La llamada que temes dura diez minutos. El miedo, una semana.", "negociacion,estoicos"),
    (56, "Marco Aurelio", "El obstáculo",
     "Lo que impide la acción hace avanzar la acción. Lo que se interpone en el camino se convierte en el camino.",
     "El cliente que regatea es tu entrenamiento de precio.", "negociacion,estoicos"),
    (57, "Marco Aurelio", "Sé uno",
     "No pierdas más tiempo discutiendo cómo debe ser un hombre bueno. Sé uno.",
     "Deja de planificar el sistema perfecto. Haz la misión de hoy.", "disciplina,estoicos"),
    (58, "Marco Aurelio", "Los pensamientos", "La calidad de tu vida depende de la calidad de tus pensamientos.",
     "Revisión semanal: pensar con método una vez a la semana.", "foco,estoicos"),
    (59, "Epicteto", "Las opiniones",
     "No son las cosas las que nos perturban, sino las opiniones que tenemos sobre ellas.",
     "Un «no» de un cliente es un dato, no un juicio sobre ti.", "negociacion,estoicos"),
    (60, "Epicteto", "Decide quién ser",
     "Primero di quién quieres ser; después haz lo que tengas que hacer.",
     "Ya lo has dicho: Monarca. Ahora, la misión diaria.", "disciplina,estoicos"),
    (61, "Epicteto", "Dueño de sí", "Nadie es libre si no es dueño de sí mismo.",
     "La libertad de Corsoft empieza por la libertad de tus hábitos.", "disciplina,estoicos"),
    (62, "Miyamoto Musashi", "El yo de ayer",
     "Hoy es la victoria sobre el yo de ayer; mañana, sobre hombres inferiores.",
     "Compite contra tu semana pasada, no contra nadie.", "disciplina"),
    (63, "Miyamoto Musashi", "Lo inútil", "No hagas nada que no sirva para nada.",
     "Si no mueve dinero, recurrente o pipeline, que espere.", "foco"),
    (64, "Miyamoto Musashi", "Mirar lejos", "Percibe lo que no puede verse con los ojos.",
     "Lee el pipeline: quién lleva una semana sin toque ya se está enfriando.", "pipeline"),
    (65, "Sun Tzu", "Antes de luchar",
     "Los guerreros victoriosos primero ganan y después van a la guerra; los derrotados primero van a la guerra y después buscan ganar.",
     "La propuesta se gana antes de enviarla: en la conversación previa.", "negociacion"),
    (66, "Sun Tzu", "El caos", "En medio del caos también hay oportunidad.",
     "Cuando un cliente está desbordado, es cuando más valora un mantenimiento.", "pipeline"),
    (67, "Sun Tzu", "Conocerse", "Conoce al enemigo y conócete a ti mismo, y no temerás el resultado de cien batallas.",
     "Tus agujeros: Organización, Producto, Red profesional. Ya los conoces.", "foco"),
    (68, "Baltasar Gracián", "Lo breve", "Lo bueno, si breve, dos veces bueno.",
     "Propuestas de una página. Mensajes de tres líneas.", "negociacion"),
    (69, "Baltasar Gracián", "Hacer y parecer", "Hacer, y hacer parecer.",
     "Un caso publicado vale más que diez proyectos que nadie ve.", "foco"),
    (70, "Baltasar Gracián", "Saber negar", "Saber negar: no todo se ha de conceder.",
     "El «no» a lo barato es lo que da valor a tu «sí».", "precio,negociacion"),
    (71, "Baltasar Gracián", "El respeto propio", "Nunca perder el respeto a sí mismo.",
     "No rebajes el precio para caer bien.", "precio"),
    (72, "Lao Tse", "El primer paso", "Un viaje de mil millas comienza con un solo paso.",
     "Un contacto hoy. Solo uno.", "disciplina"),
    (73, "Heráclito", "El río", "Nadie se baña dos veces en el mismo río.",
     "Cada semana el mercado es otro: revisa, ajusta, vuelve a lanzar.", "tiempo"),
    (74, "Confucio", "No detenerse", "No importa lo despacio que vayas mientras no te detengas.",
     "Día mínimo antes que día perdido.", "disciplina"),
    (75, "Aristóteles", "El hábito", "Somos lo que hacemos repetidamente.",
     "La excelencia no es un acto: es la racha.", "disciplina"),
]


def cargar(apps, schema_editor):
    Maxim = apps.get_model("wisdom", "Maxim")
    for numero, libro, titulo, texto, aplicacion, tags in FRASES:
        Maxim.objects.update_or_create(
            numero=numero,
            defaults={"libro": libro, "titulo": titulo, "texto": texto,
                      "aplicacion": aplicacion, "tags": tags, "principio": ""},
        )


def descargar(apps, schema_editor):
    Maxim = apps.get_model("wisdom", "Maxim")
    Maxim.objects.filter(numero__in=[f[0] for f in FRASES]).delete()


class Migration(migrations.Migration):
    dependencies = [("wisdom", "0005_alter_systemprompt_slug")]
    operations = [migrations.RunPython(cargar, descargar)]
