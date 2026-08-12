# Bohlale Impact — Transformation Assessment

Prepared before any structural changes were made, per the requested process:
inspect first, identify what's reusable, then transform. This document is
the record of that inspection. It will go stale as the transformation
proceeds — treat `IMPLEMENTATION_PLAN.md` as the live status tracker once
work starts, and this file as the point-in-time decision record.

Scope note: this assessment covers the codebase as it stood immediately
before the Bohlale Impact rebrand — a Django modular monolith (22 apps
under `apps/`) originally built for a single network deployment ("ANNET").

---

## 1. What already exists and can be reused as-is

These are structurally sound and need **branding/terminology changes only**
— no schema or logic changes:

| Area | App(s) | Notes |
|---|---|---|
| Auth, custom User model | `accounts` | Email-based login, verify/reset flows. Nothing Bohlale-specific to change beyond emails/templates. |
| Multi-tenancy / org boundary | `organisations` | `Organisation` + `OrganisationMembership` is the tenant-isolation choke point (`apps.organisations.services.get_organisation_or_404_for_user`). This is the right foundation for "each organisation has its own data boundary" (requirement 18) — it already works this way. |
| Capability-based RBAC | `core.permissions` | Two independent scopes (org-scoped, network-scoped), least-privilege per role, `is_platform_admin` escape hatch. Adding new capabilities (cases, monitoring, programme admin) is additive — the framework doesn't need to change, only the capability sets. |
| Governance, Policies, Documents | `governance`, `policies`, `documents` | Board/meetings/minutes/resolutions, versioned policies, private document vault. Directly reusable; no Bohlale-specific concepts here. |
| Grants, Projects | `grants`, `projects` | Generic funding/delivery tracking, no ANNET-specific coupling. |
| Compliance | `compliance` | Rules engine + Passport + Calendar. Generic (SARS/DSD/CIPC/Master's Office), not ANNET-specific at all. |
| Finance Lite | `expenses` | Budgets/expenses/approvals. Generic. |
| M&E (outcomes/indicators) | `monitoring_evaluation` | This is *results* M&E (targets/actuals), distinct from the new "Community Monitoring" concept in the brief (facility/activity monitoring forms) — see §3 below, don't conflate the two. |
| Audit logging | `audit` | Generic action log, already used across every app. |
| Reporting / Impact | `reporting`, `impact` | **No models of their own** — pure aggregation/presentation over other apps' data. Cheap to extend once underlying models grow. |
| Opportunities | `opportunities` | Funding/training/tender/event/partnership listings. Generic `Opportunity` model with a `network` FK — already programme-aware in principle (see §2). |
| Attendance / Kiosk | `attendance` | `AttendanceRecord` + `KioskSession` (tokenised, unattended, time-bound). This is a real, working foundation for the "Kiosk Mode" vision in requirement 15 — not a placeholder. |

**Also directly reusable:** the entire Docker/Coolify deployment pipeline
(`Dockerfile`, `docker-compose.yml`, `COOLIFY.md`, `/health/` endpoint),
the test suite structure, and the capability-based permission-checking
pattern used throughout every view.

---

## 2. What needs modification (not rebuilt — extended)

### `apps.networks` — this is already 80% of the "Programme/Network" architecture

`Network` (name, slug, tagline, description, logo) + `NetworkStaffRole`
(user ↔ network with a role) is a generic multi-tenant network model. ANNET
is described in its own docstring as merely *"the anchor/initial Network
record; the architecture supports future deployments for other networks
without code changes."* This is exactly the shape requirement 5/11 asks
for (`Black Sash → Programme → Partner Organisations → ...`).

**What's actually missing** is not the model — it's that four call sites
assume there is only ever one `Network` row, via a single helper:

```python
# apps/networks/services.py
def get_primary_network():
    return Network.objects.order_by("created_at").first()
```

Used in `networks/views.py`, `memberships/views.py`, `opportunities/views.py`
(×2). The docstring on this function already flags it as a deliberate
shortcut: *"Extending to multiple concurrent networks later only requires
swapping this lookup for a request-scoped one."* That prediction was
correct — this is a bounded, well-understood piece of work, not a rewrite.

### `apps.memberships.MembershipApplication` — the generic "apply to join a programme" workflow already exists

Draft → Submitted → Information Requested → Approved ("Active Member") →
Declined/Withdrawn, with an append-only `MembershipStatusEvent` audit
trail. This is precisely the workflow requirement 11 describes ("submit an
application… review, approve, reject, request information"). **The one
real gap:** `MembershipApplication` has no `network` FK — it implicitly
applies to whatever `get_primary_network()` returns. Adding that FK (with
a data migration defaulting existing rows to the current ANNET/primary
network) turns this from "the ANNET application" into "an application to
join any programme/network" with no other logic changes needed.

### `Organisation.is_annet_member` and related naming

A handful of ANNET-specific names sit on top of generic mechanics:
`is_annet_member` (property), `network_memberships` (related_name — fine
to keep as-is, it's accurate), "ANNET Members Only" filter option, "ANNET
Network" sidebar section label. These are rename-only.

### `Beneficiary` — coupled to a single `Programme`, needs to become a real "Person"

```python
class Beneficiary(TimeStampedModel):
    organisation = models.ForeignKey("organisations.Organisation", ...)
    programme = models.ForeignKey("programmes.Programme", ...)  # required, one only
    ...
```

Requirement 9 asks for one person to participate in *multiple* programmes
or cases. The current model can't express that — a beneficiary belongs to
exactly one programme by design. This needs a real schema change (§3), not
a rename.

### Public site navigation and organisation profile

The public site (`sitepublic` app, already redesigned once this session
into an enterprise-style homepage) needs its navigation reconsidered per
requirement 5 (Discover NPOs / Opportunities / Partnerships / Resources /
Events / Insights / Community) and organisation profiles extended per
requirement 6 (Services, Programmes, Projects, Impact, Events,
Opportunities, Verification status sections). The `Organisation` model
already carries most of the underlying data (`sectors`, `programme_areas`,
`public_verification_status`, etc.) — this is templates + a few new
profile sections pulling from `programmes`/`opportunities`, not new models.

### Workspace navigation (sidebar)

Currently a flat list grouped into three ad-hoc sections (Compliance &
Governance / Delivery / Insight). Requirement 7 asks for a five-group IA
(Overview / Operations / Evidence / Impact / Administration). This is a
template + capability-check reorganisation — the underlying pages mostly
already exist; a few (Team, Roles & Permissions, Settings as dedicated
pages) don't yet.

---

## 3. What new models are required

These don't exist today and need real schema work — listed in the order
they naturally depend on each other:

1. **`Person`** (new, in a new app or folded into `beneficiaries`) — the
   entity `Beneficiary` should have been: an organisation-scoped person
   record *not* tied to a single programme. `ProgrammeParticipation`
   (Person ↔ Programme, many-to-many with its own metadata: enrolled_at,
   status, exit_reason) replaces the current hard FK. Existing
   `Beneficiary`/`AttendanceRecord` rows migrate onto `Person` +
   `ProgrammeParticipation` — this is the one genuinely delicate migration
   in the whole plan (see §8, do this early and alone).

2. **`Case`** (new app, e.g. `apps.cases`) — case_number (org-scoped
   sequence), person (FK to `Person`), opened_by, date, issue, category,
   service_provider, description, advice_provided, action_taken, a
   `Referral` sub-record (referred_to, referred_at, referral_notes), a
   `FollowUp` sub-record (list, not single — cases often need several),
   status (`new → in_progress → referred → follow_up → resolved →
   closed`), outcome, and supporting evidence via the existing `documents`
   app (reuse `Document`, add a `case` FK — don't build a second file
   vault). Program-scoped visibility follows the same `network`/programme
   FK pattern as everything else.

3. **`MonitoringForm` / `MonitoringSubmission`** (new app, e.g.
   `apps.monitoring`) — deliberately **not** the same app as
   `monitoring_evaluation` (that's results/indicators M&E; this is
   field-activity monitoring — "Community Facility Monitoring" style
   forms). A `MonitoringForm` defines a reusable question set (owned by an
   organisation or a programme); a `MonitoringSubmission` is one filled-in
   instance (date, location, facility, answers as structured JSON,
   findings, evidence, actions, follow-up). Schema-flexible questions
   (JSONField) rather than a fixed column set, since question sets will
   differ per programme/use case (this is also what makes the eventual
   offline/Android sync tractable — a submission is a self-contained JSON
   payload).

4. **`ProgrammeApplication`** — *reuse* `MembershipApplication` once it
   carries a `network` FK (§2) rather than building a parallel model.
   "Apply to join Black Sash's programme" and "apply to join Bohlale
   Impact" become the same workflow against different `Network` rows —
   this is the crux of "don't hard-code Black Sash."

5. **`MembershipPlan` / `OrganisationSubscription`** (new, small) — for
   requirement 13 (Community vs Impact tiers). Needs only: a plan
   identifier, a set of feature flags/capability gates, and a status field
   on `Organisation` (or a linked subscription record) that capability
   checks can read — **not** billing/payment integration, which is
   explicitly out of scope for now ("do not hard-code final pricing yet").

**Not net-new, but needs a decision:** whether `Document` (existing,
private-storage-backed) is reused for case/monitoring evidence and photos,
or a lighter-weight `Evidence`/`Photo` model is added. Recommendation:
reuse `Document` — it already has org-scoped private storage, permission
checks, and an audit trail; don't duplicate that.

---

## 4. What new workflows are required

- **Case workflow**: `New → In Progress → Referred → Follow-up → Resolved
  → Closed`, as a state machine on `Case.status`, mirroring the existing
  `ComplianceObligation`/`MembershipApplication` pattern (status choices +
  an append-only status-event log for audit trail — that pattern already
  exists twice in the codebase, reuse it a third time rather than
  inventing a new one).
- **Programme application workflow**: already exists end-to-end
  (`MembershipApplication` states) — just needs the `network` FK so it can
  target any programme, not only the primary one.
- **Programme-scoped data authorisation**: a programme administrator (e.g.
  Black Sash staff) needs to see case/monitoring data *for organisations
  participating in their programme* without seeing that organisation's
  unrelated internal data (its other programmes, its finances, etc.). This
  is a new authorisation shape — not "org member" and not "platform
  admin," but "network staff with read access scoped to cases/monitoring
  tagged to their programme." Needs a new capability
  (`programme.cases.view`, `programme.monitoring.view`) checked against
  *both* the network staff role *and* a case/submission's programme
  linkage, not just organisation membership.
- **Organisation profile publication workflow**: mostly exists
  (`is_publicly_listed`, `public_verification_status`) — extend the
  onboarding/settings flow to cover the new profile sections (services,
  programmes shown publicly, opportunities).
- **Kiosk intake workflow** (requirement 15): the existing `KioskSession`
  token pattern generalises well — "Get Help / Register / Request
  Assistance / Report a Problem" become new kiosk-mode intake forms that
  create a `Case` (status=new) instead of only an `AttendanceRecord`. Real
  workflow, but scoped small: don't build all six kiosk actions at once —
  wire the pattern once (one action end-to-end) before replicating it.

---

## 5. What RBAC/permissions changes are required

The framework itself doesn't change (§1) — only the capability sets:

- **New org-scoped capabilities**: `cases.view`, `cases.manage`,
  `monitoring.view`, `monitoring.manage`, `people.view`, `people.manage`
  (renaming/extending today's `beneficiaries.*`).
- **New network-scoped capabilities**: `network.programme.applications.review`
  (generalising today's `membership.review`/`membership.decide`, which are
  fine to rename rather than duplicate), `network.cases.view`,
  `network.monitoring.view` — programme staff reading authorised
  cross-organisation data (requirement 18: "programme-level permissions").
- **A third scope may be needed**: today's model is *organisation-scoped*
  or *network-scoped*. "Black Sash sees authorised programme data from
  Partner Org A" is neither — it's *network-scoped access to a subset of
  Partner Org A's org-scoped data*. This needs an explicit rule: a
  network-staff capability check additionally filters cases/submissions to
  `WHERE programme_link.network = <the staff member's network>` — i.e. the
  capability grants "view", the queryset filter enforces "only this
  programme's data." Get this filter wrong and an organisation's
  unrelated data leaks to a programme partner — this is the single
  highest-risk permissions change in the whole plan and deserves its own
  focused review + tests when it's built, not a quick pass alongside
  everything else.
- **Role additions**: a `case_worker` org role (narrower than `staff`:
  `people.manage`, `cases.manage`, no finance/governance access) matches
  requirement 8's "do not expose complex terminology to ordinary community
  workers" — a deliberately small, simple role.

---

## 6. What can be done immediately (no schema risk)

1. **Full brand transformation** — logo, colour system (from the supplied
   Bohlale mark), typography, terminology, navigation labels, settings
   defaults, emails, page titles/metadata, seed data copy. Zero data-model
   risk; every ANNET string identified is either a template literal, a
   `config()` default, or seed-data copy — not a schema element.
2. **`network` FK on `MembershipApplication`** + generalising
   `get_primary_network()` — small, well-isolated migration with a clear
   default-value strategy (point existing rows at the current network).
3. **Public nav / organisation profile reorganisation** — templates only,
   built on data that already exists on `Organisation`.
4. **Workspace sidebar IA reorganisation** — templates only.
5. **RBAC capability renames** (`membership.*` → generalised names) —
   mechanical, low risk, already unit-testable via the existing
   `has_org_capability`/`has_network_capability` pattern.

## 7. What should be built later (real schema/workflow work, sequenced)

1. **`Person` + `ProgrammeParticipation`**, migrating `Beneficiary` data —
   do this first among the "later" items, because Cases and Monitoring
   both want to reference `Person`, not `Beneficiary`.
2. **Case management app** (`apps.cases`) — depends on `Person`.
3. **Community Monitoring app** (`apps.monitoring`) — independent of
   Cases, can be built in parallel with it once `Person` exists (monitoring
   submissions may optionally reference a person/facility, but don't have
   to).
4. **Programme-scoped authorisation** (§5's third scope) — needed once
   Cases/Monitoring exist and a real second network/programme (Black Sash)
   is provisioned to test against.
5. **Membership tiers / subscription gating** — once there's something
   real to gate (Cases/Monitoring/People are the "Impact" tier features).
6. **Android API surface** — a DRF (or similar) API exposing
   People/Cases/Monitoring/Referrals for the same backend, once those
   models are stable. Building this before the underlying models settle
   would mean re-doing the API contract.
7. **Offline sync semantics** for Android — last, and hardest: needs a
   conflict/merge strategy (e.g. per-record `updated_at` + client-generated
   UUIDs, which this codebase already uses as primary keys everywhere —
   that choice was made early in this project specifically because it
   makes offline-generated records collision-free later, so no schema
   change is needed for that part).
8. **Kiosk mode expansion** beyond the first intake action.

## 8. Recommended implementation order

```
1. Brand transformation (Phase 1)               — no dependencies
2. Programme/Network generalisation              — no dependencies
   (network FK on MembershipApplication,
    remove get_primary_network() singleton)
3. Person + ProgrammeParticipation model,         — depends on nothing new;
   migrate Beneficiary data onto it                 do this alone, verify
                                                      migration correctness
                                                      before building on it
4. Case management app                            — depends on (3)
5. Community Monitoring app                        — depends on (3), parallel to (4)
6. Programme-scoped authorisation                  — depends on (2), (4), (5)
7. Public profile + workspace IA reorganisation     — can happen any time after (1),
                                                       independent of 2-6
8. Membership tiers / subscription gating           — depends on (4) or (5) existing
9. Android API surface                              — depends on (3), (4), (5) being stable
10. Offline sync                                    — depends on (9)
11. Kiosk mode expansion                            — depends on (4)
```

Steps 1 and 2 are being executed now, in this pass. Step 3 (the `Person`
migration) is deliberately isolated as its own next step — it's the one
change in this whole plan that touches existing data, so it gets built and
verified on its own before Cases or Monitoring are built on top of it.

---

## Rebrand checklist (from the codebase scan)

Non-doc source files referencing ANNET (28 files): `templates/sitepublic/*`,
`templates/partials/*` (header/footer/favicon), `static/css/base.css`,
`static/css/brand.css`, `static/js/site.js`, `apps/sitepublic/*`,
`apps/organisations/*`, `apps/networks/*`, `apps/memberships/*`,
`apps/core/*` (context processor, management command), `apps/accounts/*`,
`apps/reporting/*`, `config/settings.py`, `.env.example`, plus migration
files (`memberships`, `expenses`, `documents` — these contain ANNET only in
historical `help_text=`/comment strings, not in actual column names; safe
to leave migration history as-is and fix `help_text` going forward only if
touched for another reason, per "never edit an applied migration").

Reference documents (`MASTER_BUILD_SPEC.md`, `ARCHITECTURE.md`,
`DATA_MODEL.md`, `IMPLEMENTATION_PLAN.md`, `CHANGELOG.md`, etc.) also
reference ANNET extensively — these are historical build records, not
runtime branding. They'll be superseded by updated equivalents as part of
the transformation rather than find-and-replaced in place, to keep the
history of *why* honest.
