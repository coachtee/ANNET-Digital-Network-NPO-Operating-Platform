# Architecture

## Overview

Django 5.2 modular monolith. One codebase, one database, 22 domain-oriented apps under `apps/`, a single `config/` project package. No microservices, no message queue, no Celery/Redis — reminders and any future scheduled work run as management commands invoked by cron (see `DEPLOYMENT.md`).

```
config/                 settings, root urls, wsgi/asgi
apps/
  core/                 cross-cutting: permissions (RBAC), base models, storage, validators,
                         context processors, seed_demo_data management command
  accounts/              custom User model (email login), auth views
  organisations/         Organisation (the single master record), OrganisationMembership,
                         onboarding wizard, org-context-switch middleware, health check engine
  networks/               Network (multi-tenant network deployments), NetworkStaffRole,
                         ANNET network dashboard, capacity intelligence
  memberships/            ANNET membership application lifecycle
  compliance/             ComplianceRule (configurable), ComplianceObligation, rules engine,
                         Compliance Passport & Calendar
  governance/              officials, meetings, resolutions, COI declarations
  policies/                policy register with versioned documents
  documents/               private document vault + secure download endpoint
  grants/, projects/, programmes/    funded-delivery lifecycle
  beneficiaries/, attendance/        3-mode beneficiary data + attendance/headcount/kiosk
  monitoring_evaluation/  outcomes/outputs/indicators/actuals
  expenses/                Finance Lite: budgets, expense claims, approval workflow
  reporting/, impact/     derived reports (PDF/CSV) and live-computed impact dashboard
  opportunities/          funding/training/tender/event listings
  audit/                  append-only audit log + thread-local request context
  sitepublic/             the public ANNET website
templates/                 shared base templates + one directory per app
static/css/base.css        the whole visual design system
```

## Multi-tenancy

`Organisation` (`apps/organisations/models.py`) is the single master record — the same row backs the public directory profile, ANNET membership, compliance, governance, projects, programmes and reporting (spec section 13). Every organisation-scoped model has a direct or indirect FK to `Organisation`.

Tenant isolation is enforced in exactly one place per request: **`apps.organisations.services.get_organisation_or_404_for_user(user, slug)`**. It returns 404 unless the requesting user holds an active `OrganisationMembership` on that organisation (or is a Platform Super Administrator). Every workspace view resolves its organisation through this function (or the equivalent `apps.core.mixins.organisation_or_404`) before touching any org-scoped model — see the tenant-isolation tests in `apps/organisations/tests.py` and `apps/documents/tests.py`.

`apps.organisations.middleware.OrganisationContextMiddleware` resolves `request.organisation` for the signed-in user's *active* workspace (stored in the session, re-validated against real active memberships on every request — never trusted blindly) so a user belonging to multiple organisations can switch context (`organisations:switch`).

## RBAC — capability-based permissions

`apps/core/permissions.py` defines two independent scopes:

- **Organisation scope** — `ORG_ROLE_*` constants (Org Admin, Executive Director, Board Member, Treasurer, Compliance Officer, Project Manager, M&E Officer, Finance Officer, Staff, Volunteer) each map to an explicit set of capabilities (`"compliance.manage"`, `"expenses.approve"`, …) via `ORG_ROLE_CAPABILITIES`. Checked with `has_org_capability(user, organisation, capability)`.
- **Network scope** — `NETWORK_ROLE_*` (Network Administrator, Membership Officer) via `NETWORK_ROLE_CAPABILITIES`, checked with `has_network_capability(user, network, capability)`.

`User.is_platform_admin` (distinct from Django's `is_superuser`, which only governs `/admin/`) implicitly holds every capability in every scope — the one explicit escape hatch, checked directly rather than implied by naming.

Views check capabilities explicitly (`if not has_org_capability(...): raise PermissionDenied`) rather than scattering `if request.user.role == "x"` checks — adding a new role only means editing the capability set in one file.

## Compliance rules engine

`apps.compliance.models.ComplianceRule` is content, not code: `authority`, `applicable_entity_types`, `required_registration_statuses` (JSON), `trigger_type`, `frequency`, `deadline_rule` (JSON), `evidence_requirements`, `official_source`, `last_verified_at`. `apps.compliance.services.sync_obligations_for_organisation(organisation)` evaluates every active rule against the organisation's captured attributes and computes a due date (`compute_due_date`) for three trigger types: financial-year-relative, fixed annual date, and anniversary-of-founding. It's idempotent — safe to call on every Compliance Passport page load and from the onboarding wizard.

## Health Check scoring

`apps.organisations.health.compute_health_check(organisation)` computes seven dimension scores (Registration, Compliance, Governance, Policies, Programme Management, M&E, Financial Accountability) from real records, each returning `reasons` and `recommended_actions` lists so the score is explainable in the UI ("Why this score?"), never a black box, and never labelled as legal certification.

## File storage

Two storage roots:

- `MEDIA_ROOT` / `MEDIA_URL` — public files only (organisation public logos, network logos). Served directly.
- `PRIVATE_MEDIA_ROOT` — everything else (compliance evidence, board minutes, policy documents, expense receipts) via `apps.core.storage.private_storage`, a `FileSystemStorage` subclass whose `.url()` always raises `NotImplementedError`. Private files are only ever served through a permission-checked view (`apps.documents.views.download_document`, `apps.expenses.views.download_receipt`) that re-validates organisation membership on every request. See `apps/documents/tests.py::DocumentIDORTests` for the enforcement test, and the note in `apps/core/storage.py` about why `base_url=None` alone does **not** achieve this (a real bug caught and fixed during this build).

## Audit trail

`apps.audit.middleware.AuditContextMiddleware` stashes the current request's user/IP in thread-local storage; `apps.audit.services.log_action(action, organisation, obj, changes, actor)` is called explicitly at points of business significance (org created, compliance status changed, document uploaded, membership decided, expense reviewed, …) rather than generically from model signals, so audit entries stay meaningful.

## What is deliberately NOT built

Per spec section 40 / section 41 ("implement the simplest extensible solution, do not introduce unnecessary infrastructure"): no Celery/Redis, no microservices, no full accounting/general ledger, no payroll, no case management system, no AI chatbot, no SPA framework. Project/task management is intentionally lightweight (spec section 24: "do not attempt to replicate Asana").
