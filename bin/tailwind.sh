#!/usr/bin/env bash
# Compila static/src/input.css -> static/css/app.css con el binario standalone
# de Tailwind. Sin Node. Descarga el binario la primera vez.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${TAILWIND_VERSION:-v4.1.11}"
BIN="$ROOT/bin/tailwindcss"
INPUT="$ROOT/static/src/input.css"
OUTPUT="$ROOT/static/css/app.css"

detect_target() {
  local os arch
  os="$(uname -s)"
  arch="$(uname -m)"
  case "$os" in
    Linux)  os="linux" ;;
    Darwin) os="macos" ;;
    *) echo "Sistema operativo no soportado: $os" >&2; exit 1 ;;
  esac
  case "$arch" in
    x86_64|amd64) arch="x64" ;;
    aarch64|arm64) arch="arm64" ;;
    *) echo "Arquitectura no soportada: $arch" >&2; exit 1 ;;
  esac
  echo "${os}-${arch}"
}

if [ ! -x "$BIN" ]; then
  TARGET="$(detect_target)"
  URL="https://github.com/tailwindlabs/tailwindcss/releases/download/${VERSION}/tailwindcss-${TARGET}"
  echo "Descargando Tailwind ${VERSION} (${TARGET})..."
  curl -fsSL "$URL" -o "$BIN"
  chmod +x "$BIN"
fi

mkdir -p "$(dirname "$OUTPUT")"
exec "$BIN" --input "$INPUT" --output "$OUTPUT" "$@"
