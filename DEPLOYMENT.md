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

## Production (Docker — recommended)

The fastest, most reproducible path to production is the bundled Docker
Compose stack (PostgreSQL, Redis, the Django app under Gunicorn, and Nginx
with automatic Let's Encrypt TLS), driven by a single idempotent script.

**On a clean Ubuntu VPS**, as root, with `annet.naleli.co.za` (or your own
domain) already pointed at the server's public IP:

```bash
git clone <this-repo-url> annet-platform
cd annet-platform
bash deploy.sh
```

That's it — one command. `deploy.sh`:

1. Installs Docker Engine + the Compose plugin if not already present.
2. Generates every secret it needs (`SECRET_KEY`, database password, Redis
   password, admin password) into a root-only `.env` file — nothing to
   edit by hand, ever. Re-running the script reuses existing secrets
   rather than regenerating them.
3. Builds the application image, brings up PostgreSQL and Redis, then the
   Django app — which runs migrations, collects static files, and ensures
   a platform admin account exists automatically on every start
   (`apps.core.management.commands.ensure_superuser`, idempotent: it never
   resets an existing account's password).
4. Brings up Nginx and requests a Let's Encrypt certificate for the
   configured domain, switching Nginx to HTTPS once issued. If DNS or
   networking isn't ready yet, it falls back cleanly to HTTP-only with a
   clear warning — just re-run `bash deploy.sh` once DNS propagates to
   retry certificate issuance; nothing else gets re-created.
5. Prints the site URL, the admin sign-in URL, and — **only the first time
   the admin account is created** — its email and generated password (also
   saved to `DEPLOYMENT_CREDENTIALS.txt`, permissions 600). Copy it to a
   password manager and delete the file.

Optional overrides (environment variables, all have sane defaults):

```bash
DOMAIN=annet.naleli.co.za bash deploy.sh   # change the target domain
ADMIN_EMAIL=ops@example.org bash deploy.sh # admin login + Let's Encrypt contact
SKIP_TLS=true bash deploy.sh               # stay on HTTP only (e.g. testing before DNS is live)
```

**Day-2 operations:**

```bash
docker compose logs -f web          # application logs
docker compose logs -f nginx        # access/error logs
docker compose exec web python manage.py <command>   # any management command
docker compose down                 # stop the stack (data volumes are preserved)
docker compose down -v              # stop AND delete all data — irreversible
bash deploy.sh                      # pull latest code, rebuild, redeploy — safe to re-run any time
```

**What `deploy.sh` deliberately cannot do for you:** configure a real SMTP
provider (it defaults to the console email backend — password reset and
verification emails print to `docker compose logs web` until you set real
`EMAIL_HOST_*` values in `.env` and redeploy), since that requires
credentials only you can supply. Everything else needed to reach a working
`https://<domain>/` is fully automated.

**Architecture:** see `Dockerfile` (multi-stage build, non-root, Gunicorn),
`docker-compose.yml` (service topology), `docker/django/entrypoint.sh`
(migrate/collectstatic/admin-bootstrap on every start), and
`docker/nginx/*.conf.template` (the HTTP-only and HTTPS Nginx configs
`deploy.sh` switches between). Redis is used only as Django's cache backend
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
