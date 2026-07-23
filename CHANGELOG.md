# Changelog

All notable changes to this repository. Format loosely follows Keep a Changelog; dates are UTC.

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
