#!/usr/bin/env bash
# Copia de seguridad de la base de datos: pg_dump comprimido, con fecha,
# conservando las 14 últimas.
#
#   ./backup.sh              guarda en ./backups
#   ./backup.sh /otra/ruta   guarda donde le digas
#
# Cron (a las 03:15 cada día):
#   15 3 * * * cd /srv/jaume-leveling && ./backup.sh >> /var/log/jaume-backup.log 2>&1
#
# Esta base de datos guarda tu histórico comercial: clientes, facturas, cobros
# y la progresión entera. Perderla es perder el sistema.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

COMPOSE="docker compose -f docker-compose.prod.yml"
DESTINO="${1:-./backups}"
CONSERVAR=14

# Las credenciales salen del .env, nunca del propio script.
set -a
# shellcheck disable=SC1091
[ -f .env ] && . ./.env
set +a
DB_USER="${POSTGRES_USER:-sistema}"
DB_NAME="${POSTGRES_DB:-sistema}"

mkdir -p "$DESTINO"
FECHA="$(date +%Y%m%d-%H%M%S)"
FICHERO="$DESTINO/sistema-$FECHA.sql.gz"

printf '[%s] Copiando %s...\n' "$(date '+%F %T')" "$DB_NAME"

# --clean --if-exists deja el volcado listo para restaurar sobre una base existente.
$COMPOSE exec -T db pg_dump \
  --username "$DB_USER" \
  --dbname "$DB_NAME" \
  --clean --if-exists --no-owner --no-privileges \
  | gzip -9 > "$FICHERO"

# Un volcado vacío o truncado es peor que ninguno: se detecta y se borra.
if ! gzip -t "$FICHERO" 2>/dev/null; then
  rm -f "$FICHERO"
  printf '[%s] ERROR: el volcado salió corrupto. No se ha guardado nada.\n' "$(date '+%F %T')" >&2
  exit 1
fi
TAMANO=$(stat -c%s "$FICHERO")
if [ "$TAMANO" -lt 1024 ]; then
  rm -f "$FICHERO"
  printf '[%s] ERROR: el volcado ocupa %s bytes. Sospechoso; descartado.\n' "$(date '+%F %T')" "$TAMANO" >&2
  exit 1
fi

printf '[%s] Guardado %s (%s)\n' "$(date '+%F %T')" "$FICHERO" "$(du -h "$FICHERO" | cut -f1)"

# --- Rotación: se conservan las 14 más recientes ---------------------------
SOBRANTES=$(ls -1t "$DESTINO"/sistema-*.sql.gz 2>/dev/null | tail -n +$((CONSERVAR + 1)) || true)
if [ -n "$SOBRANTES" ]; then
  printf '%s\n' "$SOBRANTES" | while read -r viejo; do
    rm -f "$viejo"
    printf '[%s] Rotada: %s\n' "$(date '+%F %T')" "$viejo"
  done
fi

TOTAL=$(ls -1 "$DESTINO"/sistema-*.sql.gz 2>/dev/null | wc -l)
printf '[%s] Listo. %s copias conservadas.\n' "$(date '+%F %T')" "$TOTAL"

# Para restaurar:
#   gunzip -c backups/sistema-AAAAMMDD-HHMMSS.sql.gz | \
#     docker compose -f docker-compose.prod.yml exec -T db psql -U sistema -d sistema
