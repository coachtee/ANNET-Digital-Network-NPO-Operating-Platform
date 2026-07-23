# ANNET Digital Network & NPO Operating Platform — Master Build Specification

**Status:** Approved v1.0 (frozen as the source of truth for this repository)
**Date:** 23 July 2026
**Technology Owner:** Naleli Innovations
**Initial Deployment:** ANNET — Alliance of NPO Networks

> This document is the permanent, durable source of truth for this build. Conversation history is not persisted between sessions — this file, `ARCHITECTURE.md`, `DATA_MODEL.md`, `IMPLEMENTATION_PLAN.md`, `SECURITY.md`, `DEPLOYMENT.md`, `UAT_GUIDE.md` and `CHANGELOG.md` are. Any future work on this repository (by a human or by Claude) should start by reading these files, not by re-deriving intent from scratch.

---

## 1. Product Vision

The project transforms ANNET's digital presence from a primarily informational website and membership application process into an integrated digital civil society network platform combining:

> Modern ANNET Website + NPO Directory + Digital Membership + NPO Operations + Compliance Readiness + Governance + Projects + Programme Delivery + M&E + Financial Accountability + Impact + Network Intelligence

One connected digital journey:

```
Discover ANNET → Explore the Network → Join ANNET → Create Organisation →
Build Organisation Profile → Complete Health Check → Generate Compliance
Passport → Submit Membership Application → ANNET Verification →
Become ANNET Member → Access NPO Workspace → Manage Organisation →
Deliver Programmes → Measure Impact → ANNET Network Intelligence
```

The platform does **not** replace government regulatory systems (SARS, DSD, CIPC, Master's Office, Information Regulator). It helps organisations understand potentially applicable obligations, manage deadlines, maintain governance information and evidence, manage programmes, monitor performance, account for expenditure, prepare reports, and demonstrate impact.

**The system must never automatically represent an organisation as legally compliant merely because records have been entered.** Preferred terminology: *Compliance Readiness*, *Evidence Recorded*, *Action Required*, *Overdue*, *Ready for Submission* — never *Certified Compliant* unless an independent authoritative verification mechanism exists (none does in this build).

## 2. Product Ownership

- **Naleli Innovations** owns the core software, source code, product IP, the generic compliance rules framework, product architecture and reusable modules.
- **ANNET** is the anchor deployment, network operator, first platform customer and membership authority.
- The core platform is **not** hard-coded exclusively for ANNET — see `apps/networks` (`Network` model) and the `PLATFORM_NAME` / `NETWORK_SHORT_NAME` / `NETWORK_TAGLINE` environment variables. The architecture supports future deployments for other NPO networks, associations, federations, foundations and funders.

## 3. Core Product Architecture

Four experiences on one shared data platform with strict permission boundaries:

```
PLATFORM
   ├── PUBLIC PLATFORM   (directory, profiles, opportunities, resources, insights, join)
   ├── NPO WORKSPACE     (org profile, compliance, governance, projects, programmes, M&E,
   │                       finance lite, reporting)
   ├── ANNET WORKSPACE   (network members, applications, verification, network health,
   │                       capacity needs, network impact)
   └── FUNDER WORKSPACE  (later phase)
```

## 4. Recommended Technology Stack (as built)

- **Backend:** Django 5.2, modular monolith. Domain-oriented apps under `apps/`.
- **Database:** PostgreSQL in staging/production; SQLite supported for local dev (`DB_ENGINE` env var).
- **Frontend:** Django templates + a small shared CSS design system (`static/css/base.css`) + `django-htmx` available for progressive enhancement. No SPA framework.
- **Deployment:** Single-VPS-friendly — Gunicorn + WhiteNoise for static files + Nginx reverse proxy. No Celery/Redis/message queues/Kubernetes.

## 5. Design System

White primary backgrounds, light neutral surfaces, dark text, subtle borders, generous spacing, simple line-style badges, restrained brand colour (deep forest green), clean tables and cards, minimal shadows. The authenticated workspace sidebar is white/light-neutral with a thin left accent bar on the active item — not a coloured SaaS sidebar. See `static/css/base.css` and `templates/workspace_base.html` / `templates/base.html`.

## 6–43. Full functional specification

Sections 6 through 43 of the original specification (Public Website, NPO Directory, Public Organisation Profile, Authentication, User Roles, Organisation Onboarding, Organisation 360°, Compliance Passport, Compliance Rules Engine, Compliance Calendar, Organisation Health Check, Governance, Policy Register, Document Vault, Grants & Funding, Project Management, Programme Management, Beneficiary Management, Attendance, Kiosk Mode, Monitoring & Evaluation, Financial Accountability, Reporting, Impact Dashboard, ANNET Membership, ANNET Network Dashboard, Capacity Development Intelligence, Opportunity Hub, Funder Workspace, Audit Trail, POPIA and Security, Multi-Tenancy, MVP Scope, Out of Scope, Development Principle) describe the full functional requirements this build implements. Rather than duplicate that entire text a second time here, treat the original **Master Build Specification v1.0** and the accompanying **Master Implementation Prompt** (as supplied to Claude at project kickoff) as authoritative for functional detail; `IMPLEMENTATION_PLAN.md` maps every one of those sections to the concrete Django app, model and view that implements it, and `DATA_MODEL.md` documents the resulting schema precisely.

Key non-negotiable principles carried through the implementation:

- **Terminology discipline** (section 1/14): never display "Compliant" — only "Compliance Readiness" / "Evidence Recorded" / "Submitted" / "Overdue" / "Not Applicable".
- **Independent registration capture** (section 12 Step 3): DSD, CIPC, SARS PBO, Section 18A and Master's Office status are captured as five independent nullable booleans on `Organisation` — never inferred from one another.
- **Preserve governance history** (section 18/20): `GovernanceOfficial` records are never deleted on resignation — `status` changes to `resigned` and the row is kept.
- **Policy version history** (section 19/21): `PolicyVersion` rows accumulate; old versions are never deleted when a new one is uploaded.
- **Data minimisation** (section 26/39): `Beneficiary` has no mandatory ID-number or address fields; anonymous outreach uses `AttendanceRecord.headcount` with no `Beneficiary` row at all.
- **Self-approval prevention** (section 30/52): enforced at both the model (`Expense.clean()`) and view layer.
- **No fabricated metrics** (section 32/52): every number on the Impact Dashboard and public homepage is computed live from the database — see `apps/impact/views.py` and `apps/sitepublic/views.py`.
- **Least privilege / capability-based RBAC** (section 8): see `apps/core/permissions.py`.

## 44. Definition of Success

An organisation can discover ANNET, apply digitally, build a reusable profile, understand compliance readiness, maintain governance information, manage policies/evidence, set up a funded project, deliver a programme, record attendance/headcounts, monitor indicators, capture expenses/receipts, and produce an impact view. ANNET can manage applications, manage members, understand network capacity, identify organisations requiring support, view aggregated programme activity, and demonstrate network reach and impact. **All of the above is implemented and exercised by the automated test suite's golden-path test** (`apps/organisations/tests.py::SmokeTestGoldenPath`) and was additionally verified manually against seeded demo data — see `UAT_GUIDE.md`.

## 45. The Product Principle

- For the NPO: *"Is my organisation healthy, are we managing our obligations, and are we achieving our mission?"*
- For ANNET: *"How strong is our network, where do our members need support, and what collective impact are we making?"*
- For a future funder: *"Is the organisation capable of delivering, what is happening with the programme I funded, and what impact is being achieved?"*
