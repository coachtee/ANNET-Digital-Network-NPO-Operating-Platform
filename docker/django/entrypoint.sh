#!/usr/bin/env bash
# Runs once per container start, before handing off to the CMD (gunicorn).
# Safe to run every time — every step here is idempotent.
set -euo pipefail

echo "[entrypoint] waiting for database..."
python <<'PYEOF'
import os
import sys
import time

import psycopg2

if os.environ.get("DB_ENGINE") != "postgresql":
    sys.exit(0)

deadline = time.time() + 60
last_error = None
while time.time() < deadline:
    try:
        psycopg2.connect(
            dbname=os.environ.get("DB_NAME", "annet_platform"),
            user=os.environ.get("DB_USER", "annet_platform"),
            password=os.environ.get("DB_PASSWORD", ""),
            host=os.environ.get("DB_HOST", "db"),
            port=os.environ.get("DB_PORT", "5432"),
            connect_timeout=3,
        ).close()
        print("[entrypoint] database is ready.")
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        last_error = exc
        time.sleep(1)

print(f"[entrypoint] database never became ready: {last_error}", file=sys.stderr)
sys.exit(1)
PYEOF

echo "[entrypoint] running migrations..."
python manage.py migrate --noinput

echo "[entrypoint] collecting static files..."
python manage.py collectstatic --noinput

if [ -n "${DJANGO_SUPERUSER_EMAIL:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
    echo "[entrypoint] ensuring platform admin account exists..."
    python manage.py ensure_superuser
fi

if [ "${LOAD_DEMO_DATA:-false}" = "true" ]; then
    echo "[entrypoint] loading demo data..."
    python manage.py seed_demo_data || echo "[entrypoint] seed_demo_data skipped/failed (non-fatal)"
fi

echo "[entrypoint] starting: $*"
exec "$@"
