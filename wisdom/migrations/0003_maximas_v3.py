"""Carga los diez libros y el decálogo de docs/sistema-v3-maquiavelo.md.

Sustituye la carga parcial de 0002: los números 1-10 son los libros (principio,
aplicación y máxima) y los 11-22 el decálogo operativo.
"""
from django.db import migrations

# (numero, libro, titulo, principio, texto, aplicacion, tags)
LIBROS = [
    (1, "Libro I", "Virtù y fortuna",
     "La fortuna gobierna la mitad de nuestros actos y nos deja la otra mitad. Es un río "
     "que arrasa llanuras al desbordarse: no se le impide crecer, pero se le ponen diques "
     "mientras está tranquilo.",
     "Los diques se construyen cuando no hace falta. El que espera a la crecida ya perdió.",
     "Tu río se desbordó el año pasado: un mes 4.000 €, otro cero. Los diques son el "
     "recurrente, los seis contactos semanales, el colchón y los casos publicados. "
     "Ahora el río está tranquilo porque cobras una nómina: es exactamente cuando toca.",
     "pipeline,tiempo"),
    (2, "Libro II", "Las armas propias",
     "Maquiavelo desprecia a los mercenarios y a las tropas auxiliares: quien no se apoya "
     "en fuerzas propias no está seguro nunca.",
     "Depender de un solo cliente es servir a un señor y llamarlo libertad.",
     "Corsoft y un cliente que decide cuándo cobras son tropas auxiliares. Tus armas propias "
     "son el colchón, los contratos recurrentes, tu lista de contactos y tu plantilla de "
     "entrega. Ningún cliente por encima del 35%: se corrige sumando, no restando.",
     "dependencia,foco"),
    (3, "Libro III", "Las ofensas de golpe, los beneficios a gotas",
     "Las medidas duras se aplican todas a la vez, para que se sufran menos y se olviden "
     "antes; los beneficios se dan poco a poco, para que se saboreen más.",
     "Sube el precio una vez y cállate. Justificarse es confesar que no lo vales.",
     "Una sola corrección, hoy, y silencio después: suelo 1.500 €, ecommerce 3.000 €, "
     "hora 65 €. Tres subidas son tres incomodidades. Y los beneficios —el mes gratis, "
     "la hora extra, el favor del viernes— dosificados a lo largo del año.",
     "precio,negociacion"),
    (4, "Libro IV", "¿Temido o amado?",
     "Es más seguro ser temido que amado si hay que elegir, porque el amor depende de la "
     "voluntad ajena y el temor del propio poder. Pero hay que evitar por encima de todo "
     "ser odiado.",
     "Que tus condiciones den un poco de respeto y tus entregas ninguna duda.",
     "Temido no es desagradable: es que tus condiciones se tomen en serio. 50% por "
     "adelantado, alcance escrito con lo que no incluye, horario de respuesta declarado y "
     "fecha de entrega cumplida. Nadie respeta un proveedor barato; lo usa.",
     "negociacion,precio"),
    (5, "Libro V", "El león y el zorro",
     "El príncipe debe usar la fuerza del león, que espanta a los lobos, y la astucia del "
     "zorro, que reconoce las trampas.",
     "Antes de decir el precio, averigua quién firma, qué teme y qué haría sin ti.",
     "Tu león ya existe: entregas un proyecto entero solo. El zorro está sin entrenar: "
     "quién decide de verdad, qué está comprando realmente, cuál es su alternativa y dónde "
     "está la trampa. Tu precio se fija contra su alternativa, no contra tus horas.",
     "negociacion,precio"),
    (6, "Libro VI", "El principado nuevo: cómo se ocupa una vertical",
     "Un territorio se mantiene con guarniciones, que es caro y ofende a todos, o con "
     "colonias, que cuesta poco y ata el territorio al conquistador. Y conviene ir a vivir allí.",
     "No conquistes diez sectores. Habita uno.",
     "La guarnición es perseguir a cincuenta empresas de todos los sectores. La colonia es "
     "un caso del sector con número real, una oferta con el nombre del sector dentro, "
     "presencia física y el segundo cliente referido por el primero.",
     "foco,pipeline"),
    (7, "Libro VII", "Los profetas desarmados",
     "Todos los profetas armados vencieron y los desarmados fracasaron. Tener razón no "
     "basta: hace falta poder sostenerla cuando la gente deja de creer.",
     "Nunca pidas un precio que no puedas permitirte que rechacen.",
     "La razón desarmada no cierra ventas: te dicen “es caro” y bajas. Tus armas son los "
     "13.000 €, la nómina, el recurrente y los casos publicados. Primero te armas, después "
     "impones precio. Al revés, al tercer “no” vuelves a los 800 €.",
     "precio,dependencia"),
    (8, "Libro VIII", "La tisis: prever el mal a distancia",
     "Los males del Estado son como la tisis: al principio fáciles de curar y difíciles de "
     "reconocer; con el tiempo, fáciles de reconocer e imposibles de curar.",
     "El problema barato y el problema caro son el mismo problema en dos momentos.",
     "Cinco días de retraso se corrigen con un email cordial. Dos mil euros se corrigen con "
     "un abogado. La diferencia de coste es de mil a uno. Actúa siempre en la columna de la "
     "izquierda: el retraso pequeño, el “ya que estás”, la semana sin contactar.",
     "cobro,tiempo"),
    (9, "Libro IX", "Los consejeros y la adulación",
     "Hay que elegir hombres prudentes, darles licencia para decir la verdad solo sobre lo "
     "que se les pregunta, y escucharlos con paciencia. Pero decidir uno mismo.",
     "Cobra por tu trabajo, escucha a los que te rechazaron y no discutas con la hoja de cálculo.",
     "Tus aduladores: el entorno cercano, los foros donde nadie factura y tú mismo cuando "
     "planificas en lugar de vender. La verdad está en los que dijeron que no, en la tarifa "
     "efectiva y en un solo interlocutor que facture tres veces más que tú.",
     "negociacion,foco"),
    (10, "Libro X", "La ocasión",
     "La fortuna es amiga de los jóvenes porque son menos cautos y la dominan con audacia. "
     "No dice que la temeridad funcione: dice que la excesiva cautela pierde ocasiones que "
     "no se repiten.",
     "La prudencia que nunca actúa no es prudencia, es miedo con buenos modales.",
     "Tus ocasiones abiertas: 23 años sin deudas y 16 meses de colchón, la IA aplicada a "
     "pymes en su ventana corta, el mercado alemán en Mallorca y unos clientes con el "
     "trabajo aún reciente. Audacia calculada: mover cuando tienes con qué aguantar el error.",
     "tiempo,foco"),
]

DECALOGO = [
    (11, "Libro III", "Un solo movimiento de precio, y silencio",
     "Las ofensas de golpe, los beneficios a gotas",
     "Sube el precio una vez y cállate. Justificarse es confesar que no lo vales.",
     "Suelo 1.500 €. No se justifica, no se sube por partes.", "precio"),
    (12, "Libro IV", "50% por adelantado, sin excepción",
     "¿Temido o amado?",
     "La excepción es lo que convierte una regla en una sugerencia.",
     "Sin excepciones. Ni para el cliente simpático.", "cobro,negociacion"),
    (13, "Libro II", "Ningún cliente por encima del 35%",
     "Las armas propias",
     "Depender de un solo cliente es servir a un señor y llamarlo libertad.",
     "La dependencia se corrige sumando clientes, no despidiendo.", "dependencia"),
    (14, "Libro I", "Seis contactos por semana, entregues o no",
     "Virtù y fortuna",
     "La fortuna solo entra por las puertas que dejas abiertas.",
     "Es tu dique. D1 es innegociable aunque estés entregando.", "pipeline"),
    (15, "Libro V", "Antes del precio: quién firma, qué teme, qué haría sin ti",
     "El león y el zorro",
     "Vender lo que dice que quiere es de león. Vender lo que de verdad quiere es de zorro.",
     "Pregunta siempre quién más tiene que ver esto antes de decidir.", "negociacion,precio"),
    (16, "Libro VI", "Un sector, no diez",
     "El principado nuevo",
     "No conquistes diez sectores. Habita uno.",
     "Colonia, no guarnición. Con la misma web cobras un 40-80% más.", "foco"),
    (17, "Libro VII", "Ármate antes de exigir",
     "Los profetas desarmados",
     "Nunca pidas un precio que no puedas permitirte que rechacen.",
     "Recurrente y casos primero; precio alto después.", "precio,dependencia"),
    (18, "Libro VIII", "Reclamar al día quince, no al noventa",
     "La tisis",
     "El problema barato y el problema caro son el mismo problema en dos momentos.",
     "Reclamación clara, una sola vez, con fecha y sin adornos.", "cobro,tiempo"),
    (19, "Libro IX", "Pregunta a los que dijeron que no",
     "Los consejeros y la adulación",
     "Un “no” explicado vale más que diez conversaciones agradables.",
     "Cada presupuesto rechazado exige una pregunta de seguimiento.", "negociacion"),
    (20, "Libro IX", "Mide la tarifa efectiva cada mes",
     "Los consejeros y la adulación",
     "La tarifa efectiva no adula. Es la única métrica que no puedes convencer de nada.",
     "€ del mes ÷ horas del mes. El único juez incorruptible.", "tiempo,foco"),
    (21, "Libro IV", "Fiabilidad absoluta",
     "¿Temido o amado?",
     "Un proveedor duro y puntual es un socio. Un proveedor duro e impuntual es un enemigo.",
     "Todo lo anterior solo funciona si entregas cuando dices.", "negociacion"),
    (22, "Libro II", "Los miércoles y el domingo no se tocan",
     "Las armas propias",
     "El príncipe que pierde su base no gobierna nada.",
     "Días protegidos: ni XP obligatoria, ni penalización, ni racha que romper.",
     "tiempo,foco"),
]

TODAS = LIBROS + DECALOGO


def cargar(apps, schema_editor):
    Maxim = apps.get_model("wisdom", "Maxim")
    # 0002 cargó el decálogo en los números 1-12; aquí se reorganiza entero.
    Maxim.objects.all().delete()
    for numero, libro, titulo, principio, texto, aplicacion, tags in TODAS:
        Maxim.objects.create(
            numero=numero, libro=libro, titulo=titulo, principio=principio,
            texto=texto, aplicacion=aplicacion, tags=tags,
        )


def borrar(apps, schema_editor):
    apps.get_model("wisdom", "Maxim").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("wisdom", "0002_decalogo")]
    operations = [migrations.RunPython(cargar, borrar)]
