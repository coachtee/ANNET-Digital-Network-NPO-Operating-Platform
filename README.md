# ANNET Digital Network & NPO Operating Platform

An integrated public website, association membership platform and NPO operating system, built as a Django modular monolith. Initial deployment: **ANNET — Alliance of NPO Networks**. Technology owner: Naleli Innovations.

## Start here

- **`MASTER_BUILD_SPEC.md`** — the frozen source-of-truth product specification.
- **`IMPLEMENTATION_PLAN.md`** — what's built, what isn't, and what to do next. Read this before starting any new work.
- **`ARCHITECTURE.md`** / **`DATA_MODEL.md`** — how it's put together.
- **`SECURITY.md`** — tenant isolation, RBAC, private file handling, and what's still outstanding before a production launch.
- **`DEPLOYMENT.md`** — local dev setup and production deployment.
- **`UAT_GUIDE.md`** — demo accounts and the workflows to walk through for user acceptance testing.
- **`CHANGELOG.md`** — what changed, when, and why.

## Quick start (local development)

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_demo_data   # optional: clearly-fictional demo data
python manage.py runserver
```

## Production deployment (Docker, one command)

On a clean Ubuntu VPS, as root:

```bash
bash deploy.sh
```

Builds and starts PostgreSQL, Redis, the Django app (Gunicorn) and Nginx
with automatic Let's Encrypt HTTPS for `annet.naleli.co.za`; generates all
secrets and the admin password automatically; idempotent — safe to re-run.
See `DEPLOYMENT.md` for details, overrides, and day-2 operations.

## Running tests

```bash
python manage.py test
```
