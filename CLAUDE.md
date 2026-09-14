# CLAUDE.md

Contexto permanente del repositorio. Léelo antes de tocar nada.

## 1. Qué es el proyecto

Aplicación web **personal y de un solo usuario** (Jaume) que une dos mundos en una
sola herramienta:

- **Sistema de progresión**: niveles, XP, misiones (diarias, semanales, mensuales y
  principales), rangos, jefes de rango, rachas y penalizaciones.
- **Gestión comercial real** de un desarrollador freelance: pipeline de contactos,
  clientes, propuestas, facturas y cobros, contratos recurrentes de mantenimiento y
  métricas del panel semanal.

La tesis del producto es que **las dos mitades son la misma**: cada acción comercial
real (un contacto, una propuesta enviada, una factura cobrada, un proyecto rechazado
por precio bajo) es lo que genera XP. No hay XP inventada: la progresión se deriva de
hechos registrados en el lado comercial.

La especificación funcional vive en `docs/`:

- `docs/sistema-v2.md` — el sistema calibrado: objetivos, atributos, rangos, misiones,
  tabla de XP, estrategia económica, plan de 90 días, panel de control. **Es la fuente
  de verdad numérica.**
- `docs/sistema-v3-maquiavelo.md` — capa estratégica sobre la v2. No cambia ninguna
  cifra; aporta criterio de decisión, el decálogo operativo y la relectura de las
  pruebas de rango. Úsalo para textos, tono y priorización, nunca para números.

Si ambos documentos parecen chocar, **gana la v2 en cifras y la v3 en criterio**.

## 2. Stack

- **Django 5** (vistas y plantillas clásicas, sin API)
- **PostgreSQL 16**
- **HTMX** para interactividad parcial (fragmentos de plantilla)
- **Alpine.js** para estado ligero en el cliente
- **Tailwind CSS vía Tailwind CLI** (sin Node build complejo)
- **Docker Compose** para desarrollo
- **SDK oficial `anthropic`** para las funciones de IA (revisión semanal asistida,
  redacción de mensajes comerciales, calibración). Modelos Claude actuales.

## 3. Convenciones

- **Idiomas**: español en todo lo visible (plantillas, etiquetas, mensajes, verbose_name,
  contenido). Inglés en el código: nombres de módulos, clases, funciones, variables,
  campos de modelo, ramas y commits.
- **Apps Django separadas por dominio**. Cada dominio del sistema es su propia app
  (progresión/XP, misiones, pipeline, clientes, facturación, panel, etc.).
- **La lógica de negocio va en `services.py` de cada app.** Nunca en las vistas, nunca
  en los modelos. Los modelos son datos y validaciones simples; las vistas son finas:
  reciben la petición, llaman a un servicio, devuelven plantilla o fragmento.
- Las reglas de XP, rachas y penalizaciones se implementan como funciones puras y
  testeables en servicios, con los valores en constantes/configuración, no dispersos.
- Plantillas: una plantilla completa por página y fragmentos separados para las
  respuestas HTMX.

## 4. Restricciones explícitas

- **Sin Django REST Framework.** No hay API; el HTML es la interfaz.
- **Sin React** ni ningún framework SPA. HTMX + Alpine bastan.
- **Sin Celery** ni colas ni brokers. Si hace falta algo periódico, un comando de
  gestión invocado por cron.
- **Sin multiusuario**: un solo usuario, sin equipos, sin roles, sin permisos, sin
  tenancy. Auth mínima para proteger la instancia.
- **Sin dependencias innecesarias.** Añadir un paquete requiere justificación explícita.
- **Prioridad absoluta a la simplicidad sobre la elegancia.** Ante la duda, la solución
  más aburrida y directa. Nada de abstracciones preventivas ni capas "por si acaso".

## 5. Reglas de negocio clave

### Niveles y XP

- Nivel de partida: **45 de 100**. Rango: **Operador**.
- **Tramo 41-60: 2.000 XP por nivel.** Ritmo esperado: ~1 nivel cada 3 semanas.
- Objetivo semanal realista: **500-750 XP**. Techo semanal: **1.000 XP**.

### XP por resultados (con topes semanales)

| Acción | XP | Tope |
|---|---|---|
| Contrato recurrente firmado | 350 | — |
| Proyecto cerrado ≥ 1.500 € | 250 | — |
| Dinero cobrado | 1 XP / 10 € | 400/sem |
| Entrega aceptada por el cliente | 200 | — |
| Propuesta formal enviada | 80 | 240/sem |
| Conversación comercial real (≥ 10 min) | 60 | 300/sem |
| Proyecto rechazado por precio bajo | 150 | 150/sem |
| Petición de referido | 50 | 150/sem |
| Testimonio o caso publicado | 100 | — |
| Automatización propia con ahorro medido | 120 | 240/sem |
| Publicación con contenido real | 40 | 80/sem |

### XP de soporte

| Acción | XP | Tope |
|---|---|---|
| Entreno según plan | 20 | 80/sem |
| Sueño ≥ 7 h | 10/día | 50/sem |
| Bloques con Alexandra intactos toda la semana | 40 | 40/sem |
| Revisión semanal | 60 | 60/sem |

### Consumo

Curso o vídeo **con artefacto aplicado el mismo día**: 10 XP (máx. 20/sem).
Estudiar sin producir, replanificar lo ya planificado o rediseñar las propias
herramientas: **0 XP**. Esta regla es deliberada; no la ablandes.

### Rachas

- Se cuentan **días consecutivos con acción comercial (misión D1)**.
- Día 5 → multiplicador **×1,10**. Día 15 → **×1,25** (tope).
- El **día mínimo** (un mensaje de 3 líneas) mantiene la racha.

### Penalizaciones (correctivas, nunca humillantes)

| Situación | XP | Corrección obligatoria |
|---|---|---|
| Semana con 0 acciones comerciales | −150 | Bloqueo del trabajo técnico no facturable hasta 6 contactos |
| Factura vencida > 15 días sin reclamar | −200 | Reclamación antes que cualquier otra tarea |
| Aceptar proyecto por debajo de 1.500 € | −250 | Documentar por escrito la excepción |
| Propuesta sin seguimiento > 7 días | −100 | Seguimiento primero |
| 3 proyectos abiertos a la vez (WIP > 2) | −100 | Cerrar o congelar uno |
| Cancelar un bloque con Alexandra por trabajo | −150 | Recuperarlo esa misma semana |

Prohibido implementar castigos monetarios, ejercicio como castigo o restricción de
comida o sueño.

### Miércoles y domingo — regla estructural

**Los miércoles y los domingos están excluidos de rachas y penalizaciones.** El
miércoles no hay misiones (ni la mínima) y el domingo está fuera del sistema junto con
la tarde del sábado: no generan XP obligatoria, no rompen racha y no pueden producir
penalización. La única excepción prevista es la **revisión semanal del domingo 20:15**,
que sí puntúa (60 XP) pero **no penaliza si no se hace**. Cualquier cálculo de rachas,
vencimientos o penalizaciones debe saltarse estos dos días.

### Recuperación y calibración

- **Semana de Reinicio**, máximo 1 al mes: solo 3 contactos, 1 entregable pequeño y la
  revisión; XP ×1,5.
- **Calibración mensual**: si la XP sube sin subir ingresos ni recurrente, se reduce a la
  mitad la XP de soporte; una acción nunca realizada se borra o se le sube la XP un 50%.
- **Revisión de precio trimestral**: si aceptan más de 8 de cada 10 presupuestos, subir
  precio un 20%.

### Rangos

| # | Rango | Estado | Jefe de rango |
|---|---|---|---|
| I | Aspirante | superado | — |
| II | **Operador** | en curso (~70%) | **"El Cobro Pendiente"** — 2.000 € cobrados + 1 mantenimiento firmado, 4 semanas |
| III | Especialista | meses 1-7 | "El Suelo" — rechazar 900 € con el mes vacío |
| IV | Constructor de sistemas | meses 7-15 | "La Máquina" — entregar 2.500 € en menos horas que uno de 700 € |
| V | Independiente | meses 15-30 | "El Salto" — presentar la baja con los números |
| VI | Fundador | año 3+ | "El Primer Contrato sin Ti" |

El ascenso de rango **se verifica con números**, no con sensación de progreso.

### Umbrales comerciales que el sistema debe vigilar

- **Suelo de precio**: web corporativa 1.500 € (1.800 € desde el mes 4), ecommerce
  3.000 €, automatización/IA 1.200 €, hora suelta 65 €/h, auditoría 390 €.
- **50% por adelantado siempre**, sin excepciones.
- **Planes de mantenimiento**: Básico 79 €/mes · Estándar 139 €/mes · Ecommerce 249 €/mes.
- **Pipeline: 6 contactos/semana**, se esté entregando o no.
- **WIP máximo: 2 proyectos abiertos.**
- **Ningún cliente por encima del 35%** de la facturación anual.
- **Reclamación de factura al día 15** de vencimiento.
- **Métrica maestra: tarifa efectiva (€ del mes ÷ horas del mes).** Objetivo ≥ 40 €/h.
  Es el número que preside el panel.

### Panel semanal (10 métricas)

€ cobrados · € recurrentes activos · € vencidos sin cobrar · contactos nuevos ·
conversaciones/propuestas · precio medio propuesto · **tarifa efectiva** · revisión
hecha + WIP · entrenos y peso · bloques con Alexandra intactos. Más XP de la semana,
nivel y racha comercial.

## 6. Cómo trabajar en este repo

- Antes de implementar una regla, búscala en `docs/sistema-v2.md` y cita la cifra exacta;
  no inventes valores ni "redondees" topes.
- Los cambios de reglas de negocio se hacen en el servicio correspondiente y se
  acompañan de un test de la regla.
- El tono de los textos visibles es el de los documentos: directo, en segunda persona,
  sin moralina y sin humillación.
