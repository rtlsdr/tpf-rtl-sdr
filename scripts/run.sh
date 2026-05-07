#!/bin/bash
set -e

cd "$(dirname "$0")/.."

docker compose run --rm rtl-sdr python3 app/main.py
