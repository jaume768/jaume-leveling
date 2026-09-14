#!/usr/bin/env bash
# Despliegue en el VPS: pull, build, migrate, collectstatic, restart.
#
#   ./deploy.sh            despliega
#   ./deploy.sh --sin-pull despliega lo que ya hay en local (sin git pull)
#
# Es idempotente: si algo falla, para antes de tocar nada más.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

COMPOSE="docker compose -f docker-compose.prod.yml"
CON_PULL=1
[ "${1:-}" = "--sin-pull" ] && CON_PULL=0

paso() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
error() { printf '\033[31mERROR: %s\033[0m\n' "$1" >&2; exit 1; }

# --- Comprobaciones previas -------------------------------------------------
[ -f .env ] || error "No hay .env en el servidor. Copia .env.prod.example y rellénalo."
grep -q '^SECRET_KEY=' .env || error "Falta SECRET_KEY en .env."
grep -q '^ALLOWED_HOSTS=' .env || error "Falta ALLOWED_HOSTS en .env."
grep -q '^ACME_EMAIL=' .env || error "Falta ACME_EMAIL en .env (lo pide Let's Encrypt)."

if [ "$CON_PULL" = "1" ]; then
  paso "Trayendo los últimos cambios"
  git pull --ff-only
fi

paso "Construyendo la imagen"
$COMPOSE build

paso "Levantando la base de datos"
$COMPOSE up -d db
# `run --rm` espera al healthcheck de db por el depends_on de web.

paso "Aplicando migraciones"
$COMPOSE run --rm web python manage.py migrate --noinput

paso "Recogiendo estáticos"
$COMPOSE run --rm web python manage.py collectstatic --noinput

paso "Reiniciando los servicios"
$COMPOSE up -d --remove-orphans

paso "Comprobando que responde"
for intento in $(seq 1 20); do
  if $COMPOSE exec -T web python -c "
import urllib.request, sys
try:
    urllib.request.urlopen('http://127.0.0.1:8000/', timeout=3)
except urllib.error.HTTPError as e:
    sys.exit(0 if e.code < 500 else 1)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
    printf 'La aplicación responde.\n'
    break
  fi
  [ "$intento" = "20" ] && error "La aplicación no responde. Mira: $COMPOSE logs web"
  sleep 2
done

paso "Estado"
$COMPOSE ps

printf '\n\033[32mDesplegado.\033[0m https://%s\n' "$(grep '^DOMINIO=' .env | cut -d= -f2 || echo jaumeleveling.com)"
