# Changelog

All notable changes to this repository. Format loosely follows Keep a Changelog; dates are UTC.

## 2026-07-24 — Final production readiness review

Reviewed the repository against the production-readiness checklist ahead of merging this branch: verified `Dockerfile`, `docker-compose.yml` and `deploy.sh` are present and correct, and added the operational scripts that were missing.

### Added
- `update.sh` — the normal way to ship a code change to a deployed instance: refuses to run over uncommitted local changes, backs up the database first (via `backup.sh`), `git pull --ff-only`s, rebuilds the image, restarts the stack, and verifies the app responds afterwards.
- `backup.sh` — dumps the PostgreSQL database (gzipped `pg_dump`) and both media volumes (public and private) to `./backups/` with a UTC timestamp; prunes old backups beyond a configurable retention count; safe to run without stopping the stack.
- `restore.sh` — restores a named backup, with an explicit typed confirmation before it drops/recreates the database and overwrites media volumes (or `--yes` for scripted use); `--list` shows what's available.
- Favicon assets (`static/img/favicon.ico`, `favicon-32.png`, `favicon-180.png`), circular-masked and extracted from the approved mockup's logo emblem — the only official ANNET branding asset available (no vector/high-res file was ever supplied). Wired into every page via a new `templates/partials/favicon.html` include.
- Production settings hardening: `SECURE_REFERRER_POLICY`, `FILE_UPLOAD_PERMISSIONS`/`FILE_UPLOAD_DIRECTORY_PERMISSIONS` (uploaded files, including private compliance evidence and receipts, are no longer group/world-readable by default), `EMAIL_SUBJECT_PREFIX`, and an optional `ADMINS`/`MANAGERS` + `AdminEmailHandler` wiring (via `ADMIN_EMAIL`) so unhandled server errors can be emailed once a real SMTP provider is configured. `deploy.sh` now writes `ADMIN_EMAIL` into the generated `.env` automatically.

### Fixed
- `.gitignore` was missing `/backups/`, `/docker/letsencrypt/` and `/docker/certbot-webroot/` — all three will contain real secrets/data (database dumps, TLS private keys) on a live deployment and must never be committed. Added before any of them could be created.

### Decisions made explicit
- **Logo:** the only ANNET branding asset available in this build is the approved mockup screenshot, from which the logo emblem was cropped at 80×80px native resolution. That's legible as a favicon (inherently tiny/abstracted) but too low-quality to use as the header/sidebar mark without looking like a regression from the current clean CSS badge — so the header keeps the text-based "AN" mark in brand colours, and obtaining real vector/high-res artwork from Naleli/ANNET is flagged as a pre-launch item (`IMPLEMENTATION_PLAN.md` item 3), not silently worked around with a blurry asset.
- **`update.sh`/`backup.sh`/`restore.sh` scope:** treated as operational/deployment tooling (infrastructure to safely run and maintain the already-built product), not new product features — consistent with the instruction not to add features during this review.

### Verified (no code changes needed)
- Deployment to `annet.naleli.co.za` is fully automated end-to-end via `bash deploy.sh` (see the 2026-07-24 Docker entry below for how this was validated in a sandbox that blocks Docker Hub).
- `python manage.py check --deploy` produces **zero** warnings under production-equivalent settings (`DEBUG=False`, a real-length `SECRET_KEY`, `ADMIN_EMAIL` set).
- Full test suite: 13/13 passing.
- No secrets, generated configs, or test artifacts are tracked in git (`docker/nginx/active.conf`, `DEPLOYMENT_CREDENTIALS.txt`, `.env`, `backups/`, TLS material — all correctly gitignored and confirmed absent from `git ls-files`).
- Re-checked every spec-listed release blocker (cross-tenant exposure, IDOR, unauthenticated private document access, broken auth, missing server-side authorisation, failing migrations/tests, fake metrics, unvalidated uploads, expense self-approval, beneficiary data exposure, hard-coded secrets) against the current automated test suite and code — none present.

## 2026-07-24 — Dockerized production deployment

Added a fully automated, idempotent one-command production deployment for a clean Ubuntu VPS: `bash deploy.sh`.

### Added
- `Dockerfile`: multi-stage build (build deps isolated from the runtime image), non-root `app` user, Gunicorn as the WSGI server, container `HEALTHCHECK`.
- `docker-compose.yml`: PostgreSQL 16, Redis 7, the Django app, Nginx, and a Certbot renewal loop, with healthchecks and `depends_on: condition: service_healthy` gating startup order. Fixed project name (`annet_platform`) for deterministic volume naming.
- `docker/django/entrypoint.sh`: waits for the database, runs migrations and `collectstatic`, and ensures a platform admin account exists — every container start, idempotently.
- `apps/core/management/commands/ensure_superuser.py`: non-interactive, idempotent superuser bootstrap from `DJANGO_SUPERUSER_EMAIL`/`DJANGO_SUPERUSER_PASSWORD` env vars. Unlike Django's built-in `createsuperuser --noinput`, it never touches an existing account's password on re-run, and reports `CREATED`/`EXISTS` so `deploy.sh` knows whether to display the generated password. Covered by new tests in `apps/core/tests.py`.
- `docker/nginx/http.conf.template` and `https.conf.template`: HTTP-only (ACME challenge + reverse proxy) and HTTPS (redirect + TLS termination, HSTS and security headers) Nginx configs, switched between by `deploy.sh` based on Let's Encrypt certificate state.
- `deploy.sh`: installs Docker if missing, generates all secrets (preserving them across re-runs), refuses to regenerate secrets against a pre-existing database volume, builds and starts the stack, attempts Let's Encrypt issuance with a graceful HTTP-only fallback if DNS/networking isn't ready, and prints the final URL and admin credentials (only when the admin account is newly created).
- Redis wired in as Django's cache backend (`django-redis`), configured via `REDIS_URL`; falls back to in-process memory caching automatically when unset, so local dev and the test suite never require Redis to be running.
- `DEPLOYMENT.md` restructured with the Docker path as the recommended production route; existing bare-metal instructions kept as an alternative.

### Fixed (found while validating the deployment, before shipping)
- **HTTP-only fallback would have 301-redirect-looped the entire site.** `SECURE_SSL_REDIRECT=True` was going to be hard-coded into `.env`, but Nginx only gets a working HTTPS listener *after* Let's Encrypt issuance succeeds — during the HTTP-only fallback window, that setting would force every request into a redirect to an HTTPS endpoint that didn't exist. Caught by actually standing up Gunicorn + Nginx locally (via apt-installed PostgreSQL/Redis/Nginx, since this sandbox's network policy blocks Docker Hub image pulls) and observing the redirect loop. Fixed by having `deploy.sh` track TLS state explicitly: `SECURE_SSL_REDIRECT` starts `False`, and is only flipped to `True` (with a container recreate) once a certificate is actually issued.
- **Nginx would have failed to start on most real Docker hosts.** The initial config templates included `listen [::]:80`/`listen [::]:443` (IPv6). Docker's default bridge network does not provide IPv6 to containers unless explicitly configured, and an unbindable `listen` directive stops Nginx from starting at all. Caught via a local `nginx -t`/`nginx -c` run against the rendered config. Removed the IPv6 listeners.

### Validation performed
Docker Hub image pulls are blocked by this sandbox's egress policy (confirmed via the proxy status endpoint: a 403 policy denial), so `docker compose up` itself could not be exercised directly here. Compensating validation performed instead: `docker compose config` (full YAML/variable-substitution validation), `shellcheck` (clean) and `bash -n` on `deploy.sh`/`entrypoint.sh`, and — most importantly — installing PostgreSQL, Redis and Nginx via `apt` and running the *actual* Django deploy sequence (`check --deploy`, `migrate`, `collectstatic`, `ensure_superuser` idempotency, the full test suite) against real PostgreSQL and Redis for the first time (previous testing was SQLite-only), then running Gunicorn behind the real rendered Nginx configs for both the HTTP-only and HTTPS-with-self-signed-cert states and confirming correct behaviour (200s, the 301 HTTP→HTTPS redirect, HSTS/security headers) end-to-end. The two fixes above were found this way. A live `bash deploy.sh` run against a real DNS-resolvable domain (including actual Let's Encrypt issuance) has not been performed and should be the first thing verified on the real target VPS.

## 2026-07-23 — UAT screenshot review fixes

Launched the application with seeded demo data, screenshotted all major public and authenticated screens, and compared against the approved mockup at the user's request.

### Fixed
- Impact Dashboard and Indicator Detail used Django's truthy `{% if x %}` / `|default:` on metrics that can legitimately be `0` (Reporting Readiness, Avg. Target Achievement, indicator baseline/target/actual values). Since `0` is falsy in a template `{% if %}`, a real computed `0%` was rendering as "—" (no data) — misleading given the platform's explicit requirement that dashboard figures be real, not fabricated or misrepresented. Switched to explicit `is not None` checks.
- ANNET Network Dashboard's province tab bar: multi-word labels (e.g. "KwaZulu-Natal") were word-wrapping mid-label instead of the row wrapping cleanly, because `.tabs` had no `flex-wrap`. Added `flex-wrap: wrap` and `white-space: nowrap` on tab items.

## 2026-07-23 — Initial release candidate build

Built the full platform from an empty repository (just a README) to a working release candidate covering all 8 MVP phases from the Master Build Specification.

### Added
- Django 5.2 modular-monolith foundation: environment-driven settings, custom email-based `User` model, capability-based RBAC framework (`apps/core/permissions.py`), multi-tenant `Organisation`/`OrganisationMembership` model with server-side-enforced tenant isolation, audit logging framework.
- Public ANNET website: homepage with live-computed network statistics, NPO directory with search/filters, public organisation profiles, Join journey, About/Our Network/Resources/Insights/Privacy/Terms pages — all in a shared white/light-neutral design system matching the approved mockup.
- 8-step organisation onboarding wizard (Identity → Legal Structure → Registration Status → Governance → Activities → Compliance Profile → Health Check → complete).
- Compliance rules engine (`apps/compliance`) with configurable `ComplianceRule` content, automatic due-date computation (financial-year-relative / fixed-date / anniversary triggers), Compliance Passport and Compliance Calendar views, evidence upload and submission history.
- Explainable Organisation Health Check scoring across 7 dimensions (`apps/organisations/health.py`).
- Governance (officials with preserved resignation history, meetings, resolutions, COI declarations), Policy Register (versioned documents), private Document Vault with a single permission-checked download choke point.
- Grants, Projects, Programmes with the funded-delivery lifecycle; Beneficiaries (3 data-minimised modes); Attendance with manual/staff capture and a tokenised, unauthenticated Kiosk check-in flow.
- Monitoring & Evaluation (outcomes/outputs/indicators/actuals, with attendance-driven auto-computed indicators); Finance Lite (budgets, expense claims, receipt upload, approval workflow with self-approval prevention enforced at both model and view layers).
- Reporting (PDF organisation profile via reportlab, CSV exports) and Impact Dashboard (every metric computed live from real records — no hard-coded numbers).
- ANNET Membership application lifecycle and reviewer queue; ANNET Network Dashboard and Capacity Development Intelligence (aggregated only — no individual beneficiary data at network scope); Opportunity Hub (public listing + network-admin management).
- Development demo-data seeding command (`seed_demo_data`) — refuses to run when `ENVIRONMENT=production`.
- Automated test suite: golden-path end-to-end test (register → create org → full onboarding wizard → compliance passport generated → health check → workspace home), tenant-isolation tests, expense self-approval prevention tests, private-document IDOR tests. 11/11 passing.
- `MASTER_BUILD_SPEC.md`, `ARCHITECTURE.md`, `DATA_MODEL.md`, `IMPLEMENTATION_PLAN.md`, `SECURITY.md`, `DEPLOYMENT.md`, `UAT_GUIDE.md` (this changelog).

### Fixed
- `apps.core.storage.private_storage`: `FileSystemStorage(base_url=None)` does not disable URL generation as intended — Django silently falls back to `MEDIA_URL`. Found via an automated test before shipping; fixed by subclassing `FileSystemStorage` and overriding `url()` to always raise `NotImplementedError`, so private files (compliance evidence, expense receipts, board documents) can never produce a misleading public-looking link.
- WhiteNoise's `CompressedManifestStaticFilesStorage` requires `collectstatic` to have been run, which broke local dev/test runs before `collectstatic` was executed. Now only used when `DEBUG=False`; local dev/test use plain `StaticFilesStorage`.

### Known limitations (see `IMPLEMENTATION_PLAN.md` for the full, prioritised list)
- Public About/Resources copy is placeholder — annet.org.za returned HTTP 403 to automated fetches, so nothing was scraped; real copy needs confirmation before production.
- Privacy/Terms pages are explicitly flagged placeholders pending legal review.
- No scheduled reminder emails yet; no rate limiting on auth endpoints yet; Funder Workspace is out of scope for this build (per spec, a later phase).
