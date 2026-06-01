#!/bin/bash
set -e

cd "$(dirname "$0")/.."

docker compose run --rm rtl-sdr python3 app/main.py

# Devolver permisos de archivos generados por Docker al usuario de WSL
sudo chown -R "$USER:$USER" data || true
