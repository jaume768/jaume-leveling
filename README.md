# Sistema · Jaume

Aplicación web personal de un solo usuario que une un sistema de progresión
(niveles, XP, misiones, rangos) con la gestión comercial real de un
desarrollador freelance (pipeline, facturas, clientes, proyectos).

La especificación funcional está en `docs/`. El contexto permanente para
trabajar en el repositorio, en `CLAUDE.md`.

---

## Arranque en local

Requisitos: Docker y Docker Compose. Nada más — ni Python, ni Node, ni Postgres
en la máquina.

```bash
git clone <url-del-repositorio> jaume-leveling
cd jaume-leveling

cp .env.example .env     # make up lo hace solo si falta
make up                  # construye y levanta web + db
make migrate             # aplica migraciones y carga los datos iniciales
make css                 # compila Tailwind (descarga el binario la primera vez)
```

Abre **http://localhost:8000**.

Para entrar en el admin, que es la interfaz de emergencia:

```bash
docker compose exec web python manage.py createsuperuser
```

### Comandos del día a día

| Comando | Qué hace |
|---|---|
| `make up` | Levanta el proyecto en http://localhost:8000 |
| `make down` | Para los contenedores |
| `make logs` | Sigue los logs de `web` |
| `make shell` | Shell de Django dentro del contenedor |
| `make migrate` | Aplica migraciones |
| `make test` | Ejecuta la batería de tests |
| `make css` | Compila Tailwind (`WATCH=1` para modo vigilancia) |

Los estilos **no se recompilan solos**: después de tocar una plantilla, pasa
`make css` o deja `make css WATCH=1` en una terminal aparte.

### Tareas programadas

Dos comandos de gestión, pensados para cron (ver la sección de despliegue):

```bash
docker compose exec web python manage.py chequeo_diario --simular
docker compose exec web python manage.py recordatorio_revision
```

`chequeo_diario` detecta y penaliza facturas sin reclamar, propuestas sin
seguimiento, semanas sin acción comercial y exceso de proyectos abiertos.
`--simular` enseña lo que haría sin escribir nada. `--fecha AAAA-MM-DD` permite
probar con fechas simuladas.

**Sin cron, las penalizaciones no se aplican solas.** En local hay que lanzar el
comando a mano; en el VPS lo hace el cron de las 07:00.

---

## Acceso

La instancia entera está detrás del login (`LoginRequiredMiddleware`): sin sesión,
cualquier ruta redirige a `/entrar/`. Se sale por `/salir/` (POST, desde el botón
de la barra lateral). No hay registro ni recuperación por correo: un solo usuario.

```bash
docker compose exec web python manage.py createsuperuser
```

Los tests entran autenticados por defecto (`conftest.py` sobreescribe el fixture
`client`); `client_anonimo` sirve para comprobar que el login protege.

## Qué comprueba el sistema

### Penalizaciones

| Situación | XP | Cuándo se aplica |
|---|---|---|
| Semana con 0 acciones comerciales | −150 | `chequeo_diario` (cron) |
| Factura vencida > 15 días sin reclamar | −200 | `chequeo_diario` (cron) |
| Propuesta sin seguimiento > 7 días | −100 | `chequeo_diario` (cron), una vez por semana |
| WIP > 2 proyectos abiertos | −100 | `chequeo_diario` (cron), una vez por semana |
| Proyecto por debajo de 1.500 € | −250 | al guardar el proyecto, exige motivo escrito |
| Bloque con Alexandra cancelado | −150 | al cerrar la revisión con la casilla sin marcar |

La revisión semanal **no penaliza** si no se hace: el documento la puntúa con
60 XP pero no castiga su falta.

### XP por hechos comerciales

Se concede cuando el hecho ocurre, una sola vez por objeto:

| Hecho | XP | Disparador |
|---|---|---|
| Propuesta formal enviada | 80 | oportunidad a «Propuesta enviada» |
| Proyecto cerrado ≥ 1.500 € | 250 | oportunidad a «Ganado» |
| Proyecto rechazado por precio bajo | 150 | oportunidad a «Perdido» con la casilla marcada |
| Contrato recurrente firmado | 350 | cliente activo que pasa a tener MRR |
| Entrega aceptada | 200 | proyecto a «Entregado» |
| Dinero cobrado | 1/10 € | factura marcada como cobrada |

Sobre la XP concedida se aplican, en orden: el multiplicador de racha, el ×1,5 de
la Semana de Reinicio si está activa, el tope por acción y el **techo semanal de
1.000 XP**. El techo mide XP ganada, no el saldo: una semana llena de
penalizaciones no abre más margen para seguir sumando.

### Semana de Reinicio

Máximo una al mes, se activa desde `/progresion/`. Baja la semana a lo mínimo
—la acción comercial diaria, un entregable y la revisión— y multiplica la XP por
1,5. Existe para que una mala semana tenga vuelta: sin ruta de regreso, el
segundo tropiezo es el último.

### Métrica maestra

`tarifa_efectiva()` mide **precio ÷ horas de los proyectos entregados en los
últimos 90 días**, ponderado por horas. No se calcula por mes a propósito: el
cobro y las horas no caen en el mismo mes (50% por adelantado en enero, entrega
en marzo), así que una tarifa mensual oscila sin querer decir nada. Un proyecto
en curso no cuenta: su precio y sus horas todavía no son definitivos. Sin
entregas en la ventana devuelve `None` en vez de una cifra inventada.
| Conversación comercial | 30 | toque rápido en el pipeline (vía misión D1) |

Lo que no cabe en un ritmo fijo —un referido de más, una publicación, un curso
con artefacto, una automatización medida— se registra a mano con el botón
**Registrar acción** del panel. Exige evidencia escrita y aplica el tope
semanal; las acciones que ya llegan solas (dinero cobrado, cierres, entregas)
no están en esa lista para no puntuar dos veces el mismo hecho.

### Escalado por rango

Las misiones no son las mismas en todos los rangos. `Mission.rango_min` y
`rango_max` deciden cuándo aparece y cuándo se retira cada una:

| Rango | Desbloquea |
|---|---|
| II Operador | principales «Cobro y Cierre» y «Renta» |
| III Especialista | S7 referido semanal · M6 propuesta con 3 opciones · M7 upsell de automatización · M8 plantilla de entrega · M9 testimonio · principales «El Suelo» y «Vertical» |
| IV Constructor | M10 delegar a un colaborador · M11 automatización medida · S8 horas por proyecto · principal «Multiplicador» |
| V Independiente | M12 concentración de clientes · M13 el 35% apartado · principal «El Salto» |
| VI Fundador | M14 problema productizable · principal «El Primer Contrato sin Ti» |

Las diarias, semanales y mensuales de base no llevan rango: son el ritmo fijo.
Las semanales y mensuales que se desbloquean **no se retiran nunca** (son
hábitos que se conservan); las principales sí desaparecen al superar su rango,
porque cierran ese rango y ya no son tu problema.

Dos umbrales suben solos al llegar a Especialista (`business/services.py`):
el **suelo de precio** de 1.500 € a 1.800 € y el **recurrente objetivo** de
450 €/mes a 800 €/mes. Los 6 contactos/semana y los 40 €/h no suben: el
documento los mantiene fijos en todos los rangos.

El marcador «X de Y completadas» del panel cuenta solo diarias y semanales.
Mensuales y principales son de otro plazo y llevan su recuento por grupo.

### Hoja de personaje

Los quince atributos de `docs/sistema-v2.md` §2, con su evidencia y lo que mueve
el siguiente +10, en `/personaje/`. Cada misión apunta a un atributo, y ese
atributo decide además si su XP cuenta como soporte o como resultado.

**Los atributos no se mueven solos.** Suben a mano en `/calibracion/`, con un
motivo obligatorio, y cada cambio queda en `AttributeLog`. Ese es el único
camino: `services.ajustar_atributo()` escribe el valor y el registro en la misma
transacción. En el admin ambos son de solo lectura, porque editarlos allí
dejaría el valor y el historial diciendo cosas distintas.

### Calibración mensual

Misión M5, una vez al mes, 60 minutos. `/calibracion/` calcula las tres
preguntas de `docs/sistema-v2.md` §6 con los datos reales:

1. **¿Subió la XP sin subir los ingresos?** Compara XP neta, XP de soporte,
   € cobrados y € recurrentes de este mes con el anterior. Si la XP sube y el
   dinero no, avisa de que toca reducir a la mitad la XP de soporte.
2. **¿Qué acciones no has hecho ni una vez?** Lista las reglas de XP sin usar y
   propone el +50%. Con el historial vacío no responde: lo dice en vez de
   listarlas todas.
3. **¿Te aceptan demasiado?** Tasa de oportunidades ganadas frente a cerradas.
   Por encima del 80% avisa de que el precio es bajo. Es trimestral, y con menos
   de cinco cerradas dice que la muestra no vale.

La pantalla **propone, no cambia nada sola**: los topes y la XP de las reglas se
ajustan a mano en el admin. Un sistema que se recalibra solo deja de ser un
espejo.

### Ascenso de rango

**El nivel se detiene en el techo del rango hasta cumplir su criterio.** La XP
sigue acumulándose y no se pierde: en cuanto el criterio se cumple, el nivel
salta de golpe a donde le corresponda.

Los criterios están en `core/ranks.py`, partidos en requisitos medibles contra
los datos reales (euros cobrados, recurrente activo, casos publicados, semanas
con pipeline...). La pantalla `/niveles/` los muestra con lo que llevas de cada
uno. Los requisitos que el sistema no puede medir —un colchón en el banco, una
SL constituida— salen marcados como «A mano» y cuentan como no cumplidos.

---

## Despliegue en el VPS

Producción son tres contenedores: **web** (gunicorn), **db** (PostgreSQL 16) y
**caddy**, que consigue y renueva el certificado de Let's Encrypt solo. Ni la
base de datos ni gunicorn publican puertos: lo único expuesto es Caddy.

### Una sola vez

1. **DNS.** Apunta `jaumeleveling.com` y `www.jaumeleveling.com` a la IP del
   VPS con registros A (y AAAA si tienes IPv6). Caddy no puede emitir el
   certificado hasta que esto propague.

2. **Servidor.** Instala Docker y abre los puertos 80 y 443:

   ```bash
   curl -fsSL https://get.docker.com | sh
   ufw allow 80/tcp && ufw allow 443/tcp && ufw allow OpenSSH && ufw enable
   ```

3. **Código y configuración.**

   ```bash
   git clone <url-del-repositorio> /srv/jaume-leveling
   cd /srv/jaume-leveling
   cp .env.prod.example .env
   python3 -c "import secrets; print(secrets.token_urlsafe(64))"   # para SECRET_KEY
   nano .env       # rellena SECRET_KEY, POSTGRES_PASSWORD, DATABASE_URL, ACME_EMAIL
   ```

4. **Despliega.**

   ```bash
   ./deploy.sh
   ```

### Cada actualización

```bash
cd /srv/jaume-leveling && ./deploy.sh
```

`deploy.sh` hace, en este orden: comprobar el `.env`, `git pull`, construir la
imagen, levantar la base de datos, migrar, `collectstatic`, reiniciar los
servicios y comprobar que la aplicación responde. Si algo falla, para ahí.
`./deploy.sh --sin-pull` despliega lo que ya haya en el servidor.

### Copias de seguridad

**Esto no es opcional.** La base de datos guarda el histórico comercial entero:
clientes, facturas, cobros, pipeline y toda la progresión.

```bash
./backup.sh                  # volcado comprimido en ./backups
```

Guarda `sistema-AAAAMMDD-HHMMSS.sql.gz`, verifica que el fichero no salió
corrupto ni vacío (si lo está, lo borra y devuelve error) y conserva **las 14
copias más recientes**, rotando las anteriores.

Línea de cron, a las 03:15 cada día:

```cron
15 3 * * * cd /srv/jaume-leveling && ./backup.sh >> /var/log/jaume-backup.log 2>&1
```

Junto con las tareas del sistema, el `crontab -e` del servidor queda así:

```cron
15 3 * * * cd /srv/jaume-leveling && ./backup.sh >> /var/log/jaume-backup.log 2>&1
0  7 * * * cd /srv/jaume-leveling && docker compose -f docker-compose.prod.yml exec -T web python manage.py chequeo_diario
0 19 * * 0 cd /srv/jaume-leveling && docker compose -f docker-compose.prod.yml exec -T web python manage.py recordatorio_revision
```

**Restaurar** una copia:

```bash
gunzip -c backups/sistema-20260914-031500.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T db psql -U sistema -d sistema
```

Prueba la restauración al menos una vez, en local, antes de necesitarla de
verdad. Una copia que nunca se ha restaurado no es una copia: es una carpeta.

Las copias viven en el mismo servidor, así que cubren un borrado accidental o
una migración mal aplicada, **no** la pérdida del VPS. Cuando tengas datos
reales, súbelas también fuera (`rclone`, `scp` a otra máquina, lo que sea).

---

## Variables de entorno

Todas se leen del `.env` con `django-environ`. En local, `.env.example`; en el
servidor, `.env.prod.example`.

| Variable | Obligatoria | Por defecto | Para qué |
|---|---|---|---|
| `DJANGO_SETTINGS_MODULE` | sí | `sistema.settings.dev` | `sistema.settings.prod` en el VPS |
| `SECRET_KEY` | **en producción** | clave de desarrollo | Firma de sesiones y CSRF. En producción la app **no arranca** con un marcador de posición o con menos de 50 caracteres |
| `DEBUG` | no | `False` | Siempre `False` en el servidor |
| `ALLOWED_HOSTS` | **en producción** | — | Lista separada por comas |
| `CSRF_TRUSTED_ORIGINS` | no | `https://` de cada host permitido | Solo si necesitas otro origen |
| `DOMINIO` | **en producción** | `jaumeleveling.com` | Dominio del certificado (lo usa Caddy) |
| `ACME_EMAIL` | **en producción** | — | Correo de Let's Encrypt para avisos de caducidad |
| `DATABASE_URL` | sí | `postgres://sistema:sistema@db:5432/sistema` | Conexión a PostgreSQL |
| `POSTGRES_DB` / `POSTGRES_USER` | no | `sistema` | Los usa el contenedor de la base de datos |
| `POSTGRES_PASSWORD` | **en producción** | — | Sin ella el compose de producción falla al arrancar |
| `TIME_ZONE` | no | `Europe/Madrid` | Zona horaria |
| `LOG_LEVEL` | no | `INFO` | Nivel de log en producción |
| `SECURE_SSL_REDIRECT` | no | `True` | Solo se desactiva para depurar |
| `CONN_MAX_AGE` | no | `60` | Segundos de reutilización de conexión |
| `ANTHROPIC_API_KEY` | no | vacío | Si falta, el consejo queda apagado y **todo lo demás funciona igual** |
| `ANTHROPIC_MODEL` | no | `claude-sonnet-5` | Modelo del consejero |

---

## Sobre los secretos

La clave de la API nunca debe acabar en el repositorio, en la imagen de Docker
ni en los logs. Lo que hay puesto para que eso se cumpla:

- `.env` está en `.gitignore` (junto a `.env.prod` y `.env.local`). Lo único
  versionado son las plantillas, siempre con los valores vacíos.
- `.dockerignore` excluye `.env` y `*.key`/`*.pem` de la imagen. Sin él, el
  `COPY . /app` del Dockerfile los hornearía en una capa legible con
  `docker history`.
- La clave se lee en tiempo de ejecución con `env_file`, nunca con `ARG` ni
  `ENV` en el Dockerfile.
- En producción, los logs de `anthropic`, `httpx` y `httpcore` están fijados a
  `WARNING`: su modo depuración escribe cabeceras, y ahí viaja la clave. **No
  pongas `ANTHROPIC_LOG=debug` en el servidor.**
- Django oculta en los informes de error cualquier ajuste cuyo nombre contenga
  `API`, `KEY`, `SECRET`, `TOKEN`, `PASS` o `SIGNATURE`, así que
  `ANTHROPIC_API_KEY` no aparece en los trazados.
- Ningún código imprime, registra ni manda a plantilla el valor de la clave: a
  la vista solo llega un booleano de "hay clave o no".

Para comprobarlo en cualquier momento:

```bash
git ls-files | grep -E '^\.env$' && echo "PROBLEMA: el .env está versionado"
git log --all -p | grep -nE 'sk-ant-[A-Za-z0-9_-]{10,}'    # debe salir vacío
docker run --rm --entrypoint sh jaume-leveling-web -c 'ls /app/.env'  # no debe existir
```

---

## Arquitectura

```
core/         Perfil (singleton), rangos, atributos, panel principal
missions/     Misiones y su cumplimiento diario
progression/  XP, reglas, topes, rachas y penalizaciones automáticas
business/     Clientes, pipeline, facturas y proyectos
review/       Revisión semanal y registro de salud
wisdom/       Máximas, prompt versionado y consejo con IA
```

Convenciones y restricciones del proyecto: `CLAUDE.md`. En resumen: español en
lo visible e inglés en el código, la lógica de negocio en el `services.py` de
cada app, vistas finas, y ni DRF, ni React, ni Celery, ni multiusuario.

## Sistema de diseño

Los tokens viven en `assets/input.css`, dentro del bloque `@theme`. Son la
fuente de verdad visual: **ningún color, tamaño ni radio se escribe a mano en
las plantillas**, siempre a través de las clases que generan.

| Token | Valor | Para qué |
|---|---|---|
| `base` | `#0A0F14` | fondo de la aplicación |
| `surface-1` | `#111827` | barra lateral y superficies elevadas |
| `surface-2` | `#1A2230` | tarjetas |
| `surface-3` | `#263244` | hover y píldoras |
| `line` | `#334155` | bordes |
| `xp` | `#3B82F6` | acento azul: XP y estado activo |
| `ok` | `#22C55E` | completado |
| `warn` | `#F59E0B` | jefe de rango y avisos |
| `bad` | `#EF4444` | vencido y penalizaciones |
| `ink` / `ink-2` / `ink-3` | `#F8FAFC` / `#CBD5E1` / `#94A3B8` | texto principal, secundario y terciario |

Escala tipográfica: `text-display` (32/40) · `text-h2` (24/32) · `text-h3`
(20/28) · `text-h4` (18/28) · `text-body` (16/24) · `text-body-sm` (14/20) ·
`text-caption` (12/16). Todas las cifras llevan `tabular` para que no bailen.

Radios: `rounded-sm` 6px · `rounded-md` 12px · `rounded-lg` 16px.

Piezas reutilizables, declaradas como `@utility` en el mismo fichero: `card`,
`card-quiet`, `label`, `metric`, `pill-xp`/`pill-mut`/`pill-ok`/`pill-warn`/
`pill-bad`, `bar` + `bar-fill`, `btn`/`btn-sm`/`btn-xp`/`btn-warn`,
`nav-item`/`nav-item-on` y `check-todo`/`check-done`.

Los iconos son SVG en línea en `templates/_icono.html`. Se usan así:

```django
{% include "_icono.html" with icono="panel" clase="h-5 w-5" %}
```

La navegación (lateral y barra inferior de móvil) se declara una sola vez en
`core/services.py::NAVEGACION` y llega a las plantillas por el context
processor `core.context_processors.navegacion`.

Cada página pone su título en la cabecera pegajosa con los bloques `encabezado`
y `subtitulo`; el panel sobreescribe `cabecera` entera porque saluda en lugar de
titular.

### Compilar el CSS

`bin/tailwind.sh` usa el binario standalone de Tailwind (sin Node) y solo trae
builds de Linux y macOS. En Windows, compílalo dentro del contenedor:

```bash
docker compose exec -u root web bash -lc 'bin/tailwind.sh --minify'
```

En Linux o macOS vale `make css` (y `make css WATCH=1` para modo vigilancia).
