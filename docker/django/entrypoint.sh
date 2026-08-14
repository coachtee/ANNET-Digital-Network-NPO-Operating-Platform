#!/usr/bin/env bash
# Runs once per container start, before handing off to the CMD (gunicorn).
# Safe to run every time — every step here is idempotent.
set -euo pipefail

# Fail fast rather than silently booting onto an ephemeral database.
#
# Without this guard, an unset DATABASE_URL falls back to SQLite at
# /app/db.sqlite3 — inside the container image layer, mounted by nothing and
# excluded by .dockerignore — so every restart started from an empty database
# and destroyed every registered user, organisation and programme. That was
# reported in UAT as "I can't log back in with the same credentials"; the real
# cause was that the account no longer existed. See apps/core/checks.py.
echo "[entrypoint] verifying database configuration..."
python manage.py check --deploy --fail-level ERROR

echo "[entrypoint] waiting for database..."
python <<'PYEOF'
import os
import sys
import time

import psycopg2

# Coolify's managed PostgreSQL resource is supplied as a single DATABASE_URL;
# a self-hosted/Docker Compose Postgres is supplied as discrete DB_* vars
# (see config/settings.py) — wait using whichever one is actually configured.
database_url = os.environ.get("DATABASE_URL")
if not database_url and os.environ.get("DB_ENGINE") != "postgresql":
    print("[entrypoint] no PostgreSQL configured; using SQLite (development only).")
    sys.exit(0)

deadline = time.time() + 60
last_error = None
while time.time() < deadline:
    try:
        if database_url:
            psycopg2.connect(database_url, connect_timeout=3).close()
        else:
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
