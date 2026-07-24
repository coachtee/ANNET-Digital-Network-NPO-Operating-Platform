# ANNET Digital Network & NPO Operating Platform

An integrated public website, association membership platform and NPO operating system, built as a Django modular monolith. Initial deployment: **ANNET — Alliance of NPO Networks**. Technology owner: Naleli Innovations.

## Start here

- **`MASTER_BUILD_SPEC.md`** — the frozen source-of-truth product specification.
- **`IMPLEMENTATION_PLAN.md`** — what's built, what isn't, and what to do next. Read this before starting any new work.
- **`ARCHITECTURE.md`** / **`DATA_MODEL.md`** — how it's put together.
- **`SECURITY.md`** — tenant isolation, RBAC, private file handling, and what's still outstanding before a production launch.
- **`DEPLOYMENT.md`** — local dev setup and production deployment.
- **`COOLIFY.md`** — step-by-step Coolify v4 deployment guide (the production platform for `annet.naleli.co.za`).
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

## Production deployment (Coolify)

ANNET is deployed to `annet.naleli.co.za` on [Coolify v4](https://coolify.io/):
connect this GitHub repository, create a PostgreSQL resource, create a Redis
resource, set the required environment variables, and click **Deploy**.
Coolify builds `Dockerfile` directly and fronts it with its built-in Traefik
proxy for TLS/domain routing — no deployment script is required. See
**`COOLIFY.md`** for the full environment variable reference and setup steps.

## Running tests

```bash
python manage.py test
```
