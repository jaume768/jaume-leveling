# ---- build: compila las dependencias en un venv aislado ----
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

# ---- assets: compila el CSS dentro de la imagen ----
#
# static/css/app.css es un artefacto, no fuente: esta en .gitignore. Si no se
# compila aqui, un despliegue desde un clon limpio se queda sin hoja de estilos
# y collectstatic falla al resolver el manifiesto. La version del CLI se fija
# en bin/tailwind.sh, asi que la compilacion es reproducible.
FROM python:3.12-slim AS assets

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src

# Solo lo que Tailwind necesita rastrear. Asi el cache no se invalida por
# cambios en Python que no tocan una sola clase.
# Todo lo que las directivas @source de input.css rastrean. Las apps van
# enteras porque algunas clases viven en Python (business/forms.py), no solo
# en plantillas.
COPY bin/tailwind.sh bin/tailwind.sh
COPY assets assets
COPY templates templates
COPY core core
COPY missions missions
COPY progression progression
COPY business business
COPY review review
COPY wisdom wisdom
COPY notebook notebook

RUN chmod +x bin/tailwind.sh && bin/tailwind.sh --minify

# ---- runtime: imagen final, sin toolchain y sin root ----
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --create-home app

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=app:app . /app

# El CSS compilado entra despues del codigo: el COPY anterior no lo trae porque
# .dockerignore excluye los artefactos. Tiene que existir antes de collectstatic.
COPY --from=assets --chown=app:app /src/static/css/app.css /app/static/css/app.css

# WORKDIR crea /app como root, asi que el usuario sin privilegios no podria
# crear staticfiles/ al ejecutar collectstatic. Se crea aqui, ya con dueno.
RUN mkdir -p /app/staticfiles && chown app:app /app /app/staticfiles

USER app

EXPOSE 8000

CMD ["gunicorn", "sistema.wsgi:application", "--bind", "0.0.0.0:8000"]
