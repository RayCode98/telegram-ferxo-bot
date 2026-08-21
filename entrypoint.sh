#!/bin/sh
set -eu
echo "[FreXo] Applying database migrations..."
alembic upgrade head
echo "[FreXo] Starting bot..."
exec python main.py
