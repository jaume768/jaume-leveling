"""Guia operativa de cada mision: como se hace, el atajo y lo que no cuenta.

Es contenido, no logica: aqui solo viven las constantes. La funcion que las
sirve esta en `services.guia_de`.

Las cifras salen de `docs/sistema-v2.md` (secciones 5, 6, 7 y 10) y el tono de
`docs/sistema-v3-maquiavelo.md`: directo, en segunda persona, sin moralina.

Cada guia se indexa por el codigo de la mision ("D1", "S4", "M2") o, cuando no
lo lleva, por el titulo exacto de la mision principal.

Claves de cada guia:
  pasos     lista ordenada de lo que hay que hacer, concreto y accionable
  atajo     que hacer cuando el dia viene mal (opcional)
  no_cuenta que NO da la mision por hecha (opcional)
  nota      regla del sistema que conviene recordar aqui (opcional)
"""

GUIAS = {
    # --- Diarias -------------------------------------------------------------
    "D1": {
        "pasos": [
            "Abre el pipeline y mira los seguimientos. Si hay una propuesta con "
            "más de 7 días sin tocar, ese es tu contacto de hoy.",
            "Si no hay ninguno, coge uno nuevo: cliente antiguo, referido, o "
            "empresa del sector donde ya has entregado algo.",
            "Escríbele en cinco frases: qué has visto, qué harías, cuánto cuesta "
            "aproximadamente y una pregunta que solo se pueda responder sí o no.",
            "Anótalo en el pipeline antes de cerrar el portátil. Lo que no está "
            "en el pipeline no ha pasado.",
        ],
        "atajo": "Día malo: pasa al día mínimo. Tres líneas a una sola persona "
                 "mantienen la racha.",
        "no_cuenta": "Mirar LinkedIn, preparar una plantilla o «investigar el "
                     "mercado». Si no sale un mensaje enviado a una persona "
                     "concreta, no es D1.",
        "nota": "Es la única misión que impide el cero del mes siguiente. Se "
                "hace aunque estés entregando: apagar el pipeline al entregar es "
                "tu error histórico.",
    },
    "D1 mínima": {
        "pasos": [
            "Una sola persona. La primera que te venga a la cabeza.",
            "Tres líneas: qué recuerdas de su proyecto, qué se te ha ocurrido "
            "para él, y si quiere que se lo cuentes.",
            "Enviar y anotar. Se acabó el día.",
        ],
        "nota": "La versión mínima existe para los días de cansancio, urgencia o "
                "viaje. Mantiene la racha sin fingir un día normal.",
    },
    "D2": {
        "pasos": [
            "Cierra lo que esté a medias: guarda, sube el commit, apunta dónde lo "
            "has dejado.",
            "Escribe exactamente dos tareas para mañana. Dos, no cinco.",
            "Que la primera sea la que más pereza te da.",
        ],
        "atajo": "Si solo tienes un minuto, escribe las dos tareas y nada más.",
        "no_cuenta": "Replanificar la semana entera o rediseñar tu sistema de "
                     "tareas. Replanificar lo ya planificado son 0 XP.",
    },
    "D2 mínima": {
        "pasos": [
            "Dos tareas para mañana, escritas donde las vayas a ver.",
            "Nada más. Ni revisar, ni ordenar, ni priorizar.",
        ],
        "nota": "Que mañana no empiece en blanco. Ese es todo el objetivo.",
    },
    # --- Semanales -----------------------------------------------------------
    "S1": {
        "pasos": [
            "Son seis filas nuevas en el pipeline entre lunes y sábado. Salen "
            "solas si haces D1 cada día.",
            "Reparte: dos clientes antiguos, dos referidos, dos fríos del sector "
            "donde ya has entregado.",
            "El viernes cuenta los que llevas. Si vas por tres, el sábado son tres.",
        ],
        "no_cuenta": "Se cuentan contactos enviados, no respuestas. Que no te "
                     "contesten no te quita la misión.",
        "nota": "Seis por semana, estés entregando o no. Una semana a cero son "
                "−150 XP y el trabajo técnico no facturable queda bloqueado hasta "
                "que hagas seis.",
    },
    "S2": {
        "pasos": [
            "Elige algo que un cliente pueda ver: una pantalla, una automatización "
            "funcionando, un informe con un número.",
            "Trocéalo en los bloques de entrega de la semana.",
            "Envíalo o publícalo. «Casi listo» no es un entregable.",
        ],
        "atajo": "Si la semana se te ha ido, entrega la parte más pequeña que "
                 "siga siendo visible para alguien de fuera.",
    },
    "S3": {
        "pasos": [
            "Sale del trabajo de esta semana: un problema real, qué hiciste y qué "
            "número cambió.",
            "Veinticinco minutos cada una. No la reescribas cuatro veces.",
            "Publica con el número por delante.",
        ],
        "no_cuenta": "Opinión, motivación o teoría. Publicación sin trabajo real "
                     "detrás son 0 XP.",
    },
    "S4": {
        "pasos": [
            "Domingo 20:15. Abre Revisión y rellena las diez métricas del panel.",
            "Las ocho calculadas salen solas: tu trabajo es mirar qué está en rojo "
            "y por qué.",
            "Cierra con tres objetivos para la semana que entra. Tres.",
        ],
        "nota": "Es lo único del domingo que puntúa, y no penaliza si no la haces. "
                "Pero es la que calibra todo lo demás: sin ella el sistema se "
                "desvía y no te enteras.",
    },
    "S5": {
        "pasos": [
            "Cuatro sesiones según el plan.",
            "Anótalas el mismo día, no el domingo de memoria.",
            "Si fallas una, no intentes recuperar dos seguidas.",
        ],
        "no_cuenta": "El entreno nunca es castigo. No se usa para compensar una "
                     "semana mala.",
    },
    "S6": {
        "pasos": [
            "Los miércoles, la tarde del sábado y el domingo están fuera del "
            "sistema. No se negocian con trabajo.",
            "Si te piden algo para esas horas, la respuesta es otro hueco.",
            "Si cancelas un bloque por trabajo, recupéralo esa misma semana.",
        ],
        "nota": "Cancelar un bloque por trabajo son −150 XP. Es la misión que "
                "protege que sigas aquí dentro de seis semanas.",
    },
    # --- Mensuales -----------------------------------------------------------
    "M1": {
        "pasos": [
            "Formal significa escrita: alcance, precio y fecha de entrega.",
            "Tres opciones de precio. La de en medio es la que quieres que elijan.",
            "Nunca por debajo del suelo: 1.500 € web corporativa, 3.000 € "
            "ecommerce, 1.200 € automatización.",
        ],
        "no_cuenta": "«Le pasé un precio por WhatsApp» no es una propuesta formal.",
    },
    "M2": {
        "pasos": [
            "Un cierre nuevo o una renovación de mantenimiento, da igual cuál.",
            "50% por adelantado. Siempre, sin excepciones.",
            "Si es recurrente, planes de 79 €, 139 € o 249 €/mes según el caso.",
        ],
        "nota": "Es el resultado, no la actividad. Las propuestas enviadas ya "
                "puntuaron en M1.",
    },
    "M3": {
        "pasos": [
            "Abre Facturas y mira los vencimientos.",
            "Reclama el día 15 de vencimiento, no el 20 ni «cuando toque».",
            "Un mensaje corto con el número de factura, el importe y la fecha. Sin "
            "disculparte.",
        ],
        "nota": "Una factura vencida más de 15 días sin reclamar son −200 XP, y la "
                "reclamación pasa por delante de cualquier otra tarea.",
    },
    "M4": {
        "pasos": [
            "Coge un proyecto entregado y saca un número: horas ahorradas, ventas "
            "subidas, tiempo de carga bajado.",
            "Tres párrafos: problema, qué hiciste, el número.",
            "Publícalo y guarda el enlace como evidencia.",
        ],
        "no_cuenta": "Un caso sin número es un texto bonito. El número es el caso.",
    },
    "M5": {
        "pasos": [
            "Abre Calibración: las tres preguntas salen ya calculadas con tus "
            "datos del mes.",
            "Si la XP subió y el dinero no, parte por la mitad la XP de soporte.",
            "Una acción que nunca haces: bórrala o súbele la XP un 50%. Las dos "
            "cosas valen, quedarse mirando no.",
            "Repasa los quince atributos y sube los que hayan cumplido su hito, "
            "con el motivo escrito.",
        ],
        "nota": "Una vez al mes. Es lo que impide que el sistema se convierta en "
                "un juego que se gana sin ganar dinero.",
    },
    # --- Rango III · Especialista -------------------------------------------
    "S7": {
        "pasos": [
            "Elige un cliente al que ya hayas entregado. El trabajo reciente "
            "pesa más que el bueno de hace un año.",
            "Pregunta concreto, no en abstracto: «¿a quién conoces con una web "
            "que le esté fallando?». «Si sabes de alguien» no funciona.",
            "Anótalo en el pipeline aunque no te contesten.",
        ],
        "no_cuenta": "Publicar que aceptas referidos. Se pide a una persona, "
                     "por su nombre.",
        "nota": "Tu red está en 28 sobre 100 y el objetivo es tener quince "
                "dueños de negocio a los que puedas escribir sin presentarte. "
                "Esto es lo que la mueve.",
    },
    "M6": {
        "pasos": [
            "Tres opciones en la misma propuesta: reducida, la que quieres que "
            "elijan, y una cara con todo.",
            "La de en medio es la que vendes. Las otras dos existen para que "
            "esa parezca razonable.",
            "Ninguna por debajo del suelo de precio, ni siquiera la reducida.",
        ],
        "nota": "Tres opciones convierten un «sí o no» en un «cuál». Es la "
                "diferencia entre negociar el precio y negociar el alcance.",
    },
    "M7": {
        "pasos": [
            "Mira a tus clientes activos y busca una tarea que repitan a mano "
            "todas las semanas.",
            "Calcula qué les cuesta esa tarea al mes en horas.",
            "Ofrécelo por escrito con ese número delante y tu precio detrás.",
        ],
        "no_cuenta": "Proponer «algo con IA» sin decir qué tarea concreta "
                     "desaparece.",
        "nota": "Venderle a quien ya confía en ti cuesta la décima parte que "
                "conseguir un cliente nuevo.",
    },
    "M8": {
        "pasos": [
            "Coge el último proyecto entregado y saca lo que volverías a usar: "
            "estructura, textos, configuración, checklist de entrega.",
            "Guárdalo donde lo encuentres al empezar el siguiente.",
            "Anota qué te hizo perder tiempo y qué has cambiado para que no "
            "vuelva a pasar.",
        ],
        "nota": "Es lo que sube tu tarifa efectiva sin tocar el precio: mismo "
                "dinero, menos horas.",
    },
    "M9": {
        "pasos": [
            "Pídelo justo después de entregar, con el cliente contento.",
            "Facilítaselo: mándale dos frases escritas y que las corrija. Un "
            "folio en blanco no lo rellena nadie.",
            "Pide permiso explícito para publicarlo con su nombre.",
        ],
        "no_cuenta": "Un «muy bien, gracias» por WhatsApp sin permiso para "
                     "usarlo.",
    },
    # --- Rango IV · Constructor de sistemas ----------------------------------
    "M10": {
        "pasos": [
            "Elige lo que NO es tu ventaja: diseño, textos, soporte de primer "
            "nivel. Nunca el núcleo técnico.",
            "Empieza por una tarea pequeña y cerrada, con precio fijo acordado "
            "antes.",
            "Anota dos números al terminar: lo que te ha costado y las horas "
            "que te ha ahorrado. Sin esos dos números no sabes si delegar te "
            "sale a cuenta.",
        ],
        "atajo": "Si no tienes a nadie, la misión de este mes es encontrarlo: "
                 "un contacto, una tarifa y una tarea de prueba.",
        "no_cuenta": "Subcontratarte TÚ a una agencia. Eso es lo contrario: "
                     "construyes marca ajena con tu trabajo y a los tres años "
                     "te quedas sin territorio propio.",
        "nota": "Delegar es lo que rompe el techo de las 10 h/semana. Es la "
                "palanca del rango IV, no un lujo.",
    },
    "M11": {
        "pasos": [
            "Elige algo que repitas TÚ en cada proyecto y cronométralo una vez.",
            "Automatízalo. Si tardas más en automatizarlo que lo que vas a "
            "ahorrar en un año, no lo hagas.",
            "Vuelve a cronometrar y anota las dos cifras.",
        ],
        "no_cuenta": "Rediseñar tus herramientas sin medir el ahorro. Eso son "
                     "0 XP por definición.",
    },
    "S8": {
        "pasos": [
            "Diez minutos, el sábado o al cerrar el viernes.",
            "Cada hora trabajada, a su proyecto. Las que no sabes dónde meter "
            "son la señal más útil de la semana.",
            "Si un proyecto ya va por el doble de horas estimadas, páralo y "
            "mira por qué.",
        ],
        "nota": "Sin esto la tarifa efectiva sale vacía, y es la métrica que "
                "preside el panel: € del mes ÷ horas del mes, objetivo 40 €/h.",
    },
    # --- Rango V · Independiente ---------------------------------------------
    "M12": {
        "pasos": [
            "Suma lo facturado del año y mira qué porcentaje aporta el cliente "
            "más grande.",
            "Si pasa del 35%, escribe el plan para bajarlo: no se baja "
            "echándolo, se baja creciendo por otro lado.",
            "Revisa también quién es el segundo: si los dos primeros son el "
            "70%, tienes el mismo problema repartido.",
        ],
        "nota": "Un cliente que es el 40% de tu facturación no es un cliente: "
                "es un jefe que además puede despedirte sin indemnización.",
    },
    "M13": {
        "pasos": [
            "El 35% de lo cobrado este mes, a la cuenta separada. El día que "
            "cobras, no a final de trimestre.",
            "Ahí dentro está el IVA, el IRPF y la cuota. No es ahorro.",
            "Lo que queda en la cuenta principal sí es tuyo, y ya puedes "
            "mirarlo sin engañarte.",
        ],
        "no_cuenta": "«Ya lo apartaré cuando llegue el trimestre».",
    },
    # --- Rango VI · Fundador --------------------------------------------------
    "M14": {
        "pasos": [
            "Repasa lo cobrado del último año y busca el mismo problema "
            "resuelto a mano tres veces o más.",
            "Si lo encuentras, escribe en un folio qué parte es idéntica "
            "siempre y qué parte cambia por cliente.",
            "Si no lo encuentras, la respuesta de este mes es «todavía no», y "
            "también vale.",
        ],
        "no_cuenta": "Empezar un SaaS por una corazonada. Hasta que tres "
                     "clientes distintos hayan pagado por lo mismo, es una "
                     "distracción cara.",
    },
    # --- Principales de los rangos altos --------------------------------------
    "El Salto": {
        "pasos": [
            "Seis meses seguidos con 1.320 € netos al mes o más.",
            "Colchón de 20.000 € en la cuenta.",
            "Ningún cliente por encima del 35%.",
            "Con los tres números delante, presentas la baja.",
        ],
        "nota": "Se sale con números, no con hartazgo. Si te vas un martes "
                "malo sin las tres cifras, vuelves en seis meses.",
    },
    "El Primer Contrato sin Ti": {
        "pasos": [
            "Un proyecto entregado y cobrado en el que tú no escribes el "
            "código principal.",
            "Tú vendes, defines y respondes; otra persona ejecuta.",
            "Cobrado significa cobrado: en tu cuenta.",
        ],
        "nota": "Si todo pasa por tus manos no tienes una empresa, tienes un "
                "empleo caro que además te da los sustos.",
    },
    # --- Principales ---------------------------------------------------------
    "Cobro y Cierre": {
        "pasos": [
            "Los 2.000 € de Felycampo en tu cuenta, no «confirmados».",
            "Mantenimiento ofrecido por escrito a los cuatro clientes.",
            "Plazo: semanas 1-2.",
        ],
        "nota": "Es la prueba del jefe de rango «El Cobro Pendiente». El ascenso "
                "se verifica con números, no con sensación de progreso.",
    },
    "Renta": {
        "pasos": [
            "450 €/mes recurrentes firmados.",
            "Salen de dos o tres mantenimientos, no de uno grande.",
            "Plazo: semanas 1-6.",
        ],
        "nota": "El recurrente es lo único que hace que un mes malo no sea un mes "
                "a cero.",
    },
    "El Suelo": {
        "pasos": [
            "Dos proyectos cerrados a 1.500 € o más.",
            "Y uno rechazado por debajo del suelo, con el mes vacío.",
            "Plazo: semanas 4-13.",
        ],
        "nota": "Rechazar por precio bajo da 150 XP. Aceptarlo son −250 XP y "
                "documentar la excepción por escrito.",
    },
    "Vertical": {
        "pasos": [
            "Tres clientes del mismo sector.",
            "Una oferta escrita específica para ese sector.",
            "Plazo: meses 3-7.",
        ],
    },
    "Multiplicador": {
        "pasos": [
            "Una plantilla reutilizable extraída de un proyecto real.",
            "Una automatización que recorte un 40% el tiempo de entrega.",
            "Plazo: meses 6-12.",
        ],
        "nota": "Solo cuenta con el ahorro medido. Rediseñar tus propias "
                "herramientas sin medir son 0 XP.",
    },
}
