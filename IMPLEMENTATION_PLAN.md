# Implementation Plan & Status

This file is the living map from the Master Build Specification's MVP phases to what actually exists in this repository right now, and what to do next. Update it whenever you finish a unit of work — do not let it drift from reality.

## MVP phase status

| MVP | Scope | Status |
|---|---|---|
| MVP 1 — Platform Foundation | Auth, roles, organisations, multi-tenancy, audit | **Done.** `apps/accounts`, `apps/organisations`, `apps/core/permissions.py`, `apps/audit`. Tenant isolation tested. |
| MVP 2 — Public ANNET | Website, directory, org profiles, join | **Done.** `apps/sitepublic`. Real ANNET copy for About/Resources/Insights is a flagged placeholder pending confirmation (see below). |
| MVP 3 — Membership | Onboarding, applications, ANNET review, approval | **Done.** `apps/organisations` onboarding wizard (8 steps), `apps/memberships` application + review queue. |
| MVP 4 — Compliance & Governance | Passport, calendar, health check, governance, policies, documents | **Done.** `apps/compliance`, `apps/organisations/health.py`, `apps/governance`, `apps/policies`, `apps/documents`. |
| MVP 5 — Delivery | Grants, projects, programmes, activities, beneficiaries, attendance, headcount, kiosk | **Done.** `apps/grants`, `apps/projects`, `apps/programmes`, `apps/beneficiaries`, `apps/attendance`. |
| MVP 6 — Impact | M&E, indicators, targets, actuals, evidence, impact dashboard, reports | **Done.** `apps/monitoring_evaluation`, `apps/impact`, `apps/reporting` (PDF org profile, CSV compliance/attendance/expenses). |
| MVP 7 — Financial Accountability | Budgets, expenses, receipts, approvals, budget vs. expenditure | **Done.** `apps/expenses`. Self-approval prevention enforced and tested. |
| MVP 8 — Network Intelligence | ANNET dashboard, network health, capacity needs, programme stats, impact aggregation | **Done.** `apps/networks`. |

**Overall: all 8 MVP phases have a working, tested implementation.** This is a genuine functional release candidate for UAT — see the honest caveats below before treating it as launch-ready.

## What "done" means here (read this before assuming more than was built)

Every module above has: real Django models with migrations verified against a fresh database, server-side RBAC and tenant-isolation enforcement, working create/list/detail views and templates in the shared design system, and at least indirect exercise through the golden-path test. It does **not** mean every UI affordance implied by the spec's example screens exists pixel-for-pixel, or that every edge case has a dedicated automated test. Treat this as a strong, working foundation ready for structured UAT and iteration — not as a finished, pixel-polished, fully hardened consumer product.

## Explicit known gaps / next steps (in priority order)

1. **Real ANNET content.** `templates/sitepublic/about.html`, `resources.html` contain clearly-labelled placeholder copy because the live annet.org.za site returned HTTP 403 to automated fetches during this build (blocked, not scraped). Replace with confirmed ANNET-supplied copy before production publication.
2. **`/privacy/` and `/terms/`** are explicitly flagged placeholders — replace with legally reviewed POPIA notice and terms of use before launch. See `SECURITY.md`.
3. **Scheduled reminders** (compliance deadlines, policy review dates, governance term expiry) — the data model supports it (`ComplianceObligation.due_date`, `Policy.next_review_date`, `GovernanceOfficial.term_end`) but no `send_reminders` management command exists yet. Straightforward to add per `DEPLOYMENT.md` section 7 — do this next if reminders are a launch requirement.
4. **Enhanced access control for sensitive beneficiary records.** `Beneficiary.is_sensitive` exists as a flag but is not yet enforced by an additional permission gate beyond the standard `beneficiaries.view`/`beneficiaries.manage` capabilities. Add a dedicated capability (e.g. `beneficiaries.view_sensitive`) if/when a real sensitive-service programme is onboarded.
5. **Rate limiting** on login/password-reset — not yet added (spec section 38, "where practical"). `django-ratelimit` or equivalent is the straightforward path.
6. **Governance meeting minutes linking UI.** `GovernanceMeeting.minutes_document` exists on the model but the meeting detail template only links out to the general document vault — no in-page "attach this document as minutes" control yet.
7. **Funder Workspace** (spec section 35) — explicitly a later phase per the spec; no code exists for it. `Grant.responsible_manager` and the existing capability framework are the natural extension point when this is prioritised.
8. **CI pipeline** — no GitHub Actions workflow runs `manage.py test` on push yet. Recommended before merging further feature branches at scale.
9. **Opportunity → organisation matching** (spec section 34) — `Opportunity.target_sectors`/`target_provinces` fields exist but nothing consumes them yet; explicitly a "future functionality" item in the spec.

## Section → implementation map

| Spec section | Implementation |
|---|---|
| 7 Homepage | `apps/sitepublic/views.py::home`, `templates/sitepublic/home.html` |
| 8 Public NPO Directory | `apps/sitepublic/views.py::directory` |
| 9 Public Organisation Profile | `apps/sitepublic/views.py::organisation_public_profile` |
| 10 Authentication | `apps/accounts` |
| 11 User Roles | `apps/core/permissions.py` |
| 12 Organisation Onboarding | `apps/organisations/views.py::onboarding_step` (8-step wizard) |
| 13 Organisation 360 | `apps/organisations/views.py::org_360` |
| 14–15 Compliance Passport & Rules Engine | `apps/compliance` |
| 16 Compliance Calendar | `apps/compliance/views.py::calendar` |
| 17 Health Check | `apps/organisations/health.py` |
| 18 Governance | `apps/governance` |
| 19 Policy Register | `apps/policies` |
| 20 Document Vault | `apps/documents` |
| 21 Grants & Funding | `apps/grants` |
| 22 Project Management | `apps/projects` |
| 23 Programme Management | `apps/programmes` |
| 24 Beneficiary Management | `apps/beneficiaries` |
| 25 Attendance | `apps/attendance` |
| 26 Kiosk Mode | `apps/attendance/views.py::kiosk_launch/kiosk_entry` |
| 27 M&E | `apps/monitoring_evaluation` |
| 28 Finance Lite | `apps/expenses` |
| 29 Reporting | `apps/reporting` |
| 30 Impact Dashboard | `apps/impact` |
| 31 ANNET Membership | `apps/memberships` |
| 32 Network Dashboard | `apps/networks/views.py::dashboard` |
| 33 Capacity Intelligence | `apps/networks/views.py::capacity` |
| 34 Opportunity Hub | `apps/opportunities` |
| 36 Audit Trail | `apps/audit` |
| 38 Multi-Tenancy | `apps/organisations/services.py`, `apps/organisations/middleware.py` |
| 43 Demo/Seed Data | `apps/core/management/commands/seed_demo_data.py` |

## Development principle (carried forward)

Per spec section 41: do not redesign the architecture independently. Where a requirement is ambiguous, implement the simplest extensible solution and document the assumption here rather than guessing silently.
