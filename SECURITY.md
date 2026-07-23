# Security

## Tenant isolation

Every organisation-scoped view resolves its `Organisation` through `apps.organisations.services.get_organisation_or_404_for_user(user, slug)` (or the equivalent helper), which 404s unless the requesting user holds an active `OrganisationMembership` on that exact organisation, or is a Platform Super Administrator. No view trusts a client-supplied organisation slug/id without this check. Every detail/edit/delete/download endpoint for an org-scoped object additionally filters that object by `organisation=organisation` (see the `get_object_or_404(Model, id=..., organisation=organisation)` pattern used throughout `apps/*/views.py`).

Tested: `apps/organisations/tests.py::TenantIsolationTests` (Org 360, Compliance Passport), `apps/documents/tests.py::DocumentIDORTests` (private document download).

## RBAC

Capability-based, not role-name-based — see `ARCHITECTURE.md`. Every "manage" action checks `has_org_capability`/`has_network_capability` and raises `PermissionDenied` (HTTP 403) rather than silently no-op'ing or trusting client-side hiding of a button. `login_required` alone is never treated as sufficient authorisation anywhere in the codebase.

## Private file storage

Compliance evidence, board minutes, policy documents and expense receipts are stored under `PRIVATE_MEDIA_ROOT` — a directory entirely separate from `MEDIA_ROOT` — via `apps.core.storage.private_storage`. That storage's `.url()` method always raises `NotImplementedError`, so it is structurally impossible for a template to accidentally render a direct link to a private file. Every private file is served through an authenticated, permission-checked view (`documents:download`, `expenses:download_receipt`) that re-validates organisation membership on every request.

**Note on a bug found and fixed during this build:** the naive approach — `FileSystemStorage(base_url=None)` — does **not** disable URL generation; Django silently falls back to `settings.MEDIA_URL`, which would have produced a plausible-looking but structurally unsafe `/media/...` URL. This was caught by an automated test (`apps/documents/tests.py::test_document_file_has_no_public_url`) before being shipped, and fixed by subclassing `FileSystemStorage` and overriding `url()` to raise.

## Authentication

- Custom `User` model, email as the login identifier.
- Django's built-in `PasswordResetView`/`PasswordResetConfirmView` flow (tokenised, time-limited, single-use).
- Django's built-in password validators (`MinimumLengthValidator` raised to 10 chars, `CommonPasswordValidator`, `UserAttributeSimilarityValidator`, `NumericPasswordValidator`).
- Session cookies: `HttpOnly` always; `Secure` and HSTS enabled automatically whenever `DEBUG=False`.
- Kiosk devices never authenticate through the standard login form — `User.is_kiosk_only` is a hard-block flag (if such an account were ever used to sign in normally, `post_login_redirect` logs it straight back out). The real kiosk mechanism is a tokenised, time-limited, unauthenticated URL (`KioskSession`) scoped to exactly one programme.

## CSRF / XSS / clickjacking

- `CsrfViewMiddleware` on for every view; every form in every template includes `{% csrf_token %}`.
- Django's auto-escaping template engine is used throughout — no `|safe` filters or `mark_safe()` calls were introduced on user-supplied content anywhere in this codebase.
- `X_FRAME_OPTIONS = "DENY"`, `SECURE_CONTENT_TYPE_NOSNIFF = True`.

## File uploads

`apps.core.validators.validate_upload_file` enforces an extension allow-list (`ALLOWED_UPLOAD_EXTENSIONS`) and a size cap (`MAX_UPLOAD_SIZE_BYTES`, default 15MB) on every user-facing upload form: `DocumentUploadForm`, `PolicyVersionUploadForm`, `ExpenseForm.clean_receipt`, `OrganisationPublicProfileForm.clean_public_logo`.

## Self-approval prevention

`Expense.clean()` raises `ValidationError` if `reviewed_by == submitted_by`; `expenses.views.review_expense` additionally blocks this at the view layer before the form is even rendered. Tested in `apps/expenses/tests.py`.

## Audit logging

`apps.audit.services.log_action` records actor, organisation, action, object type/id, a JSON `changes` payload, IP address and timestamp for business-significant actions (organisation created, compliance status changed, document uploaded/downloaded, governance official added/resigned, policy version uploaded, grant/programme/project/beneficiary created, attendance recorded, expense submitted/reviewed, membership application submitted/decided). Never stores secrets, passwords or raw file contents.

## Production hardening (`DEBUG=False`)

Automatically enabled by `config/settings.py` whenever `DEBUG=False`: `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS` (1 year) with `includeSubDomains`/`preload`, and `SECURE_PROXY_SSL_HEADER` for a reverse-proxy deployment. See `.env.example`.

## Data minimisation / POPIA

- `Beneficiary` has no mandatory ID-number or address field; anonymous outreach never creates a `Beneficiary` row at all (see `DATA_MODEL.md`).
- `is_sensitive` on `Beneficiary` flags records needing enhanced access control (structural flag is in place; a dedicated permission gate beyond standard `beneficiaries.view`/`beneficiaries.manage` capabilities is a documented follow-up — see `IMPLEMENTATION_PLAN.md` known limitations).
- Network-level dashboards (`apps/networks/views.py`) aggregate only — no individual beneficiary data is ever surfaced at network scope.
- `/privacy/` and `/terms/` are explicitly labelled placeholders pending legal review — see `KNOWN LIMITATIONS` in `UAT_GUIDE.md`. They must not be treated as a real POPIA notice or terms of use until replaced.

## What this build does NOT yet include (be aware before production launch)

- No rate limiting on the login/password-reset endpoints (spec section 38 lists this as "where practical" — flagged as a pre-production follow-up, see `DEPLOYMENT.md`).
- No automated retention/deletion policy engine (spec section 39 asks only for retention *metadata support*, not automation — a `retention` field can be added to `Beneficiary`/`Document` as a follow-up).
- No Content-Security-Policy header (`django-csp` or equivalent) — recommended before production launch given the platform serves user-controlled `public_about` text (auto-escaped, but CSP is defence-in-depth).
- No automated `bandit`/`safety`/dependency-audit CI step configured yet — recommended before production launch.

## Reporting a vulnerability

This is an internal build; report security concerns directly to the Naleli Innovations technical lead rather than filing a public issue.
