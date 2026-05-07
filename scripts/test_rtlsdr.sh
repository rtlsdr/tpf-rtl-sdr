#!/bin/bash
set -e

cd "$(dirname "$0")/.."

echo "[1] Verificando USB dentro del contenedor..."
docker compose run --rm rtl-sdr lsusb

echo ""
echo "[2] Probando adquisición RTL-SDR a 2.4 MS/s..."
echo "Cortar con Ctrl + C después de unos segundos."
docker compose run --rm rtl-sdr rtl_test -s 2400000
