# UAT Guide

## Status

**READY FOR UAT** — foundation plus all 8 MVP phases have a working, tested implementation (see `IMPLEMENTATION_PLAN.md` for exactly what "done" means and the explicit list of known gaps). This is a genuine functional release candidate, not a mock-up. It is **not** yet production-launch-ready — see "Known limitations" below and `SECURITY.md` before going live with real user data.

## Getting a local instance running

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # DEBUG=True is fine for UAT
python manage.py migrate
python manage.py seed_demo_data
python manage.py runserver
```

Visit `http://127.0.0.1:8000/`.

## Demo accounts (all seeded, password `DemoPass!2026`)

| Email | Role |
|---|---|
| `platform-admin@example.com` | Platform Super Administrator (also a Django admin superuser at `/admin/`) |
| `network-admin@example.com` | ANNET Network Administrator — network dashboard, capacity intelligence, membership review queue |
| `admin0@example.com` | Organisation Administrator for **Siyafunda Community Technology Centre** (publicly listed, verified) |
| `admin1@example.com` | Organisation Administrator for **Karoo Women's Health Trust** |
| `admin2@example.com` | Organisation Administrator for **Ubuntu Youth Development Network** |
| `admin3@example.com` | Organisation Administrator for **Limpopo Early Childhood Development Trust** |
| `admin4@example.com` | Organisation Administrator for **Eastern Cape Environmental Justice Forum** (not publicly listed — use this one to sanity-check that private organisations don't leak into the public directory) |
| `pm0..pm4@example.com` | Project Manager for the corresponding organisation |

These are obviously fictional demo accounts — never use these credentials or seed data in a production deployment (`seed_demo_data` refuses to run when `ENVIRONMENT=production`).

## Where to start

Start from the homepage (`/`) as a logged-out visitor, then work through **Workflow A** below signed in as a fresh account you register yourself — that's the flow a real NPO would experience end-to-end, and it's the one covered by the automated golden-path test.

## Workflows to verify

### Workflow A — NPO joining ANNET
1. `/` → **Join the Alliance**.
2. Register a new account.
3. You're dropped straight into **Create your organisation** (step 1 of onboarding).
4. Complete all 8 steps: Identity → Legal Structure → Registration Status → Governance (add at least one official) → Activities → Compliance Profile (obligations auto-generate from what you entered) → Health Check (review the "Why this score?" explanations) → finish.
5. Land on the workspace home. Note the ANNET membership status card.
6. Go to **Membership** → submit an application with a motivation.
7. Sign out, sign in as `network-admin@example.com` → **Membership Applications** → open the application you just submitted → approve it (or request more information and check it round-trips back to the applicant).
8. Sign back in as your own account — the workspace home should now show "ANNET Member".

### Workflow B — Programme delivery
Signed in as `admin0@example.com` (Siyafunda): **Programmes** → open the seeded programme → note the seeded activity, indicator and beneficiaries. Add a new activity, add a new indicator, record an attendance entry (try both a named beneficiary and an anonymous headcount), then check **Impact Dashboard** and **M&E** reflect it. Try **Launch Kiosk** on the Attendance page — copy the generated link into a private/incognito window (no login) and check in.

### Workflow C — Expense approval
Signed in as `pm0@example.com`: **Finance Lite** → open the seeded project → submit a new expense with a receipt file. Sign out, sign in as `admin0@example.com` → review and approve it. Then try approving an expense **you yourself submitted** — confirm the platform blocks it.

### Workflow D — Compliance
Signed in as `admin0@example.com`: **Compliance Passport** → note the auto-generated obligations (DSD/CIPC/SARS/POPIA) with computed due dates. Open one, update its status, upload a piece of evidence, and check the submission history updates. Check **Compliance Calendar** groups it correctly under Overdue/Upcoming/Completed.

### Workflow E — ANNET network view
Signed in as `network-admin@example.com`: **Network Dashboard** → filter by province, check the aggregate numbers (member count, average compliance readiness, organisations requiring support). **Capacity Intelligence** → check organisations scoring below 50% on a dimension appear in the right bucket. Confirm no individual beneficiary data appears anywhere on these pages.

### Tenant isolation check (do this — it's a release blocker if it fails)
Signed in as `admin0@example.com`, try to directly visit another organisation's workspace URL, e.g. `/app/karoo-womens-health-trust/`. You should get a 404, not the other organisation's data. This exact scenario has an automated regression test (`apps/organisations/tests.py::TenantIsolationTests`), but it's worth eyeballing once.

## Running the automated test suite

```bash
python manage.py test
```
Expected: all tests pass (11 at the time of writing — golden path, tenant isolation, expense self-approval, document IDOR). Treat any failure as a release blocker.

## Known limitations (be aware, not surprised)

- `/about/` and `/resources/` public pages contain clearly-labelled placeholder copy — the real annet.org.za site blocked automated fetching, so nothing was scraped; real copy needs to be supplied and reviewed before production publication.
- `/privacy/` and `/terms/` are explicitly flagged as placeholders pending legal review — not a real POPIA notice yet.
- No scheduled reminder emails yet (compliance deadlines, policy reviews, governance term expiry) — the underlying date fields exist; see `IMPLEMENTATION_PLAN.md` item 3.
- No rate limiting on login/password-reset yet.
- Funder Workspace is out of scope for this build (explicitly a later phase in the spec).
- Governance meeting minutes: the model supports linking a document as a meeting's minutes, but there's no in-page "attach" control yet — link it via Django admin in the meantime if needed for UAT.

See `IMPLEMENTATION_PLAN.md` for the complete, prioritised list of what to build next.
