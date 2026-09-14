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
seguimiento, semanas sin acción comercial, exceso de proyectos abiertos y
revisiones sin cerrar. `--simular` enseña lo que haría sin escribir nada.
`--fecha AAAA-MM-DD` permite probar con fechas simuladas.

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
