#!/bin/sh
set -eu

echo "[entrypoint] Running migrations..."
alembic upgrade head

PORT="${PORT:-8000}"
echo "[entrypoint] Starting uvicorn on port ${PORT}..."

exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --proxy-headers \
  --forwarded-allow-ips="*" \
  --no-server-header