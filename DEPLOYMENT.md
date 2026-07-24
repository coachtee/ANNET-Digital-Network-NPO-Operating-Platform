# Deployment

## Local development

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # edit as needed — DEBUG=True is fine for local dev
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo_data     # optional — clearly-fictional demo data, refuses to run if ENVIRONMENT=production
python manage.py runserver
```

## Production (Coolify — recommended)

ANNET is deployed to production on [Coolify v4](https://coolify.io/) at
`annet.naleli.co.za`. Coolify builds this repository's `Dockerfile` directly,
runs it behind its built-in Traefik reverse proxy (TLS/domain routing), and
manages PostgreSQL and Redis as separate first-class resources. There is no
deployment script to run — every runtime setting is an environment variable
configured in the Coolify UI.

**See [`COOLIFY.md`](COOLIFY.md)** for the full step-by-step guide: creating
the PostgreSQL/Redis resources, the complete required-environment-variable
table, persistent volume configuration, health check setup, and domain/TLS
configuration.

In short: connect the GitHub repository, create a PostgreSQL resource, create
a Redis resource, set the environment variables documented in `COOLIFY.md`,
and click **Deploy**. `docker/django/entrypoint.sh` runs migrations, collects
static files, and (if `DJANGO_SUPERUSER_EMAIL`/`DJANGO_SUPERUSER_PASSWORD`
are set) bootstraps the initial admin account automatically on every
container start — idempotent, so redeploys are always safe to trigger.

**Architecture:** see `Dockerfile` (multi-stage build, non-root, Gunicorn
binding `0.0.0.0:8000`), `docker-compose.yml` (the app service definition —
also usable for a plain `docker compose up` outside Coolify, see
`COOLIFY.md`), `docker/django/entrypoint.sh` (migrate/collectstatic/
admin-bootstrap on every start), and `apps/core/views.py` (the `/health/`
liveness endpoint used by both the Dockerfile's `HEALTHCHECK` and Coolify's
health check setting). Redis is used only as Django's cache backend
(`django-redis`) — consistent with the "no Celery, no message queue"
architecture decision in `ARCHITECTURE.md`; it degrades to in-process
memory caching automatically if `REDIS_URL` isn't set (e.g. local dev).

## Production (bare-metal, no Docker)

This is the manual, non-containerized alternative — useful if Docker isn't
an option on your infrastructure. Prefer the Docker path above where you can.

This platform is designed to run comfortably on a single VPS — no Kubernetes, no message broker.

1. **PostgreSQL**
   ```bash
   sudo apt install postgresql
   sudo -u postgres createuser annet_platform
   sudo -u postgres createdb annet_platform -O annet_platform
   sudo -u postgres psql -c "ALTER USER annet_platform WITH PASSWORD '...';"
   ```
   Set in `.env`: `DB_ENGINE=postgresql`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` (or a single `DATABASE_URL`).

2. **Application**
   ```bash
   python3 -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env   # fill in real SECRET_KEY, DEBUG=False, ENVIRONMENT=production,
                           # ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, email settings, DB settings
   python manage.py migrate
   python manage.py collectstatic --noinput
   python manage.py createsuperuser
   ```
   Generate a real `SECRET_KEY` (never reuse the placeholder in `.env.example`):
   ```bash
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```

3. **Gunicorn** (systemd unit, e.g. `/etc/systemd/system/annet-platform.service`):
   ```ini
   [Unit]
   Description=ANNET Digital Network platform
   After=network.target postgresql.service

   [Service]
   User=www-data
   WorkingDirectory=/opt/annet-platform
   EnvironmentFile=/opt/annet-platform/.env
   ExecStart=/opt/annet-platform/venv/bin/gunicorn config.wsgi:application \
       --bind 127.0.0.1:8000 --workers 3 --timeout 60
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

4. **Nginx** reverse proxy, HTTPS via Let's Encrypt (certbot). Static files are served by WhiteNoise from within Gunicorn (`CompressedManifestStaticFilesStorage`, active automatically whenever `DEBUG=False`) — no separate Nginx static block is required, though one can be added for extra performance. **Do not** expose `PRIVATE_MEDIA_ROOT` through any Nginx `location` block — it is not meant to be served directly.

5. **Object/cloud storage for production media** (recommended over local disk for durability): swap `DEFAULT_FILE_STORAGE`/`STORAGES["default"]` for `django-storages` (S3-compatible) if required; `apps.core.storage.private_storage` should be pointed at a **private** bucket/prefix with no public read ACL if this route is taken — the `.url()`-raises contract must be preserved (subclass whichever backend is used the same way `PrivateFileSystemStorage` does here).

6. **Email** — set `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend` plus `EMAIL_HOST`/`EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD`/`EMAIL_PORT`/`EMAIL_USE_TLS` in `.env`. In `DEBUG` the console backend is used automatically — nothing is silently sent nowhere.

7. **Scheduled reminders** — no Celery. Add compliance/policy-review reminder processing as a management command (e.g. `apps/notifications/management/commands/send_reminders.py` — not yet implemented, see `IMPLEMENTATION_PLAN.md`) and a cron entry:
   ```
   0 7 * * * cd /opt/annet-platform && venv/bin/python manage.py send_reminders
   ```

8. **Backups** — standard `pg_dump` cron job for the database; back up `PRIVATE_MEDIA_ROOT` and `MEDIA_ROOT` alongside it (or rely on durable object storage if using option 5).

9. **Logging/monitoring** — `LOGGING` in `config/settings.py` logs to stdout/stderr by default (captured by systemd/journald). Point `django.security` and root loggers at a real aggregator (Sentry, etc.) before production launch — not yet wired up.

## Environment variables

See `.env.example` for the full list with inline documentation. Never commit a real `.env` file — it's git-ignored.

## Fresh-database verification

This is re-verified before every release-candidate claim in this repository:
```bash
rm -f db.sqlite3   # local sqlite dev only
python manage.py migrate
python manage.py check
python manage.py test
```
All migrations apply cleanly from empty on every commit referenced in `CHANGELOG.md`.
