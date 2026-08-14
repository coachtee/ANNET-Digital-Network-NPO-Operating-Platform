# Programme Workspace — Architecture Proposal

Status: **proposal only — nothing in this document has been implemented.** No models, views, templates, migrations or tests have been changed. This is the inspection + design output requested before any coding starts.

Scope of inspection: `apps/programmes`, `apps/projects`, `apps/monitoring_evaluation`, `apps/expenses`, `apps/attendance`, `apps/beneficiaries`, `apps/impact`, `apps/reporting`, `apps/grants`, plus the parts of `apps/organisations` and `apps/documents` that these apps depend on.

Note on the DSD reference material: no uploaded DSD application form or applicant guideline is accessible in this session (no file was attached to this conversation for me to read). Section 3 below is built from the structure you supplied in your message, cross-checked against South African DSD NPO funding-application conventions from general knowledge. If you have the actual PDF, attach it and I will reconcile this section against it before implementation.

---

## 1. Current Architecture

Today, "programme delivery" is five separately-owned apps that share foreign keys but no shared UI:

```
Organisation
 ├─ programmes.Programme  (id, name, description, programme_area, status,
 │                          locations JSON, services JSON,
 │                          target_beneficiary_groups JSON,
 │                          theory_of_change_summary, grants M2M)
 │   └─ programmes.Activity (programme FK required; name, scheduled_date,
 │                            location, status) — NOT linked to Project
 │
 ├─ projects.Project      (organisation FK required; programme FK OPTIONAL,
 │                          grant FK optional; name, description, manager,
 │                          start_date, end_date, budget, status)
 │   └─ projects.ProjectTask (project FK required; title, assignee,
 │                             due_date, is_milestone, status)
 │
 ├─ monitoring_evaluation.Outcome   (programme FK required)
 ├─ monitoring_evaluation.Output    (programme FK required; outcome FK optional)
 ├─ monitoring_evaluation.Indicator (programme FK required; outcome/output FK optional;
 │                                    target_value, auto_from_attendance)
 │   └─ monitoring_evaluation.IndicatorPeriodValue (indicator FK; actual_value, period)
 │
 ├─ beneficiaries.Beneficiary (organisation FK; programme FK REQUIRED)
 ├─ attendance.AttendanceRecord (organisation FK; programme FK REQUIRED;
 │                                 activity FK optional; beneficiary FK optional)
 ├─ attendance.KioskSession (programme FK required)
 │
 ├─ expenses.Budget       (project FK, OneToOne — no programme-level budget exists)
 │   └─ expenses.BudgetLine (budget FK; category, allocated_amount)
 ├─ expenses.Expense      (project FK REQUIRED — no programme-level expense exists)
 │
 ├─ grants.Grant          (organisation FK; funder_name, amount, dates,
 │                          reporting_requirements) — the actual "Funding" model
 │
 ├─ impact.* — no models at all; impact_dashboard() is a pure aggregation view
 │             over Programme/Activity/Indicator/Grant/ComplianceObligation
 └─ reporting.* — no models at all; four view functions generate CSV/PDF
                  on demand, all organisation-wide (not programme-scoped)
```

**Views/URLs today** (`apps/*/urls.py`, all under `/app/<org-slug>/...`):

| Concern | URL name | Scope |
|---|---|---|
| Programme list/detail | `programmes:list`, `programmes:detail` | org / one programme |
| Projects | `projects:list`, `projects:detail` | org-wide list, no programme filter in the URL |
| M&E | `monitoring_evaluation:dashboard`, `programme_me`, `indicator_detail` | org-wide dashboard **and** a separate programme-scoped page that already exists |
| Attendance | `attendance:list`, `record`, `kiosk_launch` | org-wide, no programme filter |
| Beneficiaries | `beneficiaries:list`, `create` | org-wide, **already accepts `?programme=<id>`** |
| Finance | `expenses:list`, `project_expenses`, `review_expense` | org-wide list + project-scoped detail |
| Impact | `impact:dashboard` | org-wide only |
| Reporting | `reporting:list` + 3 CSV/PDF endpoints | org-wide only |

**`apps/programmes/views.py::programme_detail`** is exactly the page you flagged: it renders activities + indicators + a beneficiary count, and has the inline `ActivityForm` POST handler you want removed. It has no idea Projects, Finance, Impact or Reports exist.

**`apps/monitoring_evaluation/views.py::programme_me`** is a second, independent programme-scoped page (Outcomes/Outputs/Indicators, inline add-forms for each) that a user only reaches by clicking "Open M&E" and landing on the *org-wide* dashboard first, then picking their programme again from a list.

**Test coverage today**: `apps/programmes`, `apps/projects`, `apps/monitoring_evaluation`, `apps/attendance`, `apps/beneficiaries`, `apps/impact`, `apps/reporting`, `apps/grants` all have empty (3-line stub) `tests.py` files. Only `apps/expenses` has real tests (3, covering self-approval prevention). This is worth stating plainly: **the entire programme-delivery surface has no regression safety net today.**

---

## 2. Current Problems

1. **No programme-level container in the UI.** The relationships already exist in the data model (`Activity.programme`, `Beneficiary.programme`, `AttendanceRecord.programme`, `Outcome/Output/Indicator.programme`, `Project.programme`) but nothing renders them together. A user managing one programme has to independently visit Programmes, M&E, Projects, Attendance, Beneficiaries and Finance and manually keep the programme in their head each time.
2. **Programme detail page is a dead end**, not a workspace: activities + indicators + a count, full stop. No projects, no finance, no evidence, no reports, no outcomes/targets beyond a plain list.
3. **Two disconnected M&E pages** for the same programme: the org-wide `monitoring_evaluation:dashboard` and the already-good, programme-scoped `programme_me` — but nothing links `programmes:detail` to `programme_me` directly today.
4. **No programme-level financial picture.** `Budget`/`Expense` are hard-wired to `Project` only. A programme with three funded projects has no "budget vs actual" view anywhere — you'd have to open three separate project pages and add it up by hand.
5. **Attendance has no programme filter** in its URL/view (unlike Beneficiaries, which already has one) — a small, concrete gap.
6. **Programme creation is a single flat form** (`ProgrammeForm`: name, description, programme_area, theory_of_change_summary, status, grants) that never asks for the things the model already has room for — `locations`, `services`, `target_beneficiary_groups` are real `JSONField`s on `Programme` today that **no form exposes**. A programme is created essentially empty of DSD-relevant content, then the user is dropped on the dead-end detail page from problem #2 with no guidance on what to do next.
7. **No Programme has a defined period** (start/end dates) — the model has no such fields at all today.
8. **"Evidence" doesn't exist as a concept anywhere in programme delivery**, despite `documents.Document` already having a dormant `category="programmes"` choice and a working (but unused, for this purpose) generic FK (`content_type`/`object_id`/`related_object`) built for exactly this kind of cross-app linking — the same mechanism Step 3 of this project already used for governance evidence.
9. **Reporting is entirely organisation-wide.** There is no way to export a report scoped to one programme or one project; the four existing CSV/PDF endpoints (`reporting:*`) never take a programme/project id.
10. **Zero test coverage** across the whole programme-delivery surface (see above), which means today's "current problems" are also undocumented — there's no test suite that pins down what the current behaviour actually guarantees.

---

## 3. Proposed Architecture

Keep the existing five apps and their existing models as the source of truth. Do not fragment the same concept across new duplicate models. Add a thin set of new fields/links so a `Programme` can serve as a real container, and build one new template/view layer — the **Programme Workspace** and **Project Workspace** — that queries across the existing apps and presents them as tabs, instead of inventing new "workspace" models.

```
Organisation
 └─ Programme                              [apps.programmes — EXTEND]
     ├─ Programme Plan fields              [same model, EXTEND — see §5]
     ├─ Projects (0..n)                    [apps.projects — unchanged FK, already there]
     │   └─ Activities (0..n)              [apps.programmes.Activity — ADD optional
     │       ├─ Tasks (0..n)                project FK, keep programme FK required]
     │       ├─ Attendance / People          [apps.projects.ProjectTask — ADD optional
     │       └─ Evidence                     activity FK]
     ├─ Activities not tied to a project    [same Activity model — project FK stays null]
     ├─ Outcomes → Indicators → Targets     [apps.monitoring_evaluation — unchanged]
     ├─ Programme Budget                    [apps.expenses.Budget — GENERALISE, see §5]
     ├─ Funding                             [apps.grants.Grant — unchanged, already M2M/FK]
     └─ Reports                             [apps.reporting — ADD programme/project-scoped views]
```

Key design decision — **Activity stays anchored to Programme, gains an optional link to Project.** Your target diagram nests Activities under Projects. Moving `Activity.programme` to `Activity.project` would be a breaking change: `AttendanceRecord`, `Beneficiary` and every M&E indicator with `auto_from_attendance=True` are keyed off `programme`, and `Project.programme` is *optional* — plenty of programmes will never have a Project at all, and still need Activities (a workshop series doesn't always need "project" overhead). So: **keep `Activity.programme` required, add `Activity.project` optional.** An activity delivered under a specific funded project sets both; a programme-level activity with no specific project just sets `programme`. This is additive — no existing row changes meaning, nothing breaks.

Same logic for **Tasks**: `ProjectTask.project` stays required (a task always belongs to a project — that's the existing, sensible constraint), and gains an optional `activity` FK so a task can optionally be scoped to one activity within that project.

**Evidence is not a new model.** Wire up `documents.Document`'s existing (but currently unused for this) generic FK: a "Evidence" tab in the Programme/Project/Activity workspace uploads a `Document` with `category=Document.CATEGORY_PROGRAMMES` and `related_object` pointing at the Programme, Project, or Activity. This reuses the exact mechanism already built and tested in Step 3 for governance evidence — no new upload/versioning/visibility code needed.

**Programme Budget is not a new model** — it's `expenses.Budget` generalised to attach to either a Programme or a Project:

```python
class Budget(TimeStampedModel):
    project = models.ForeignKey("projects.Project", null=True, blank=True, ...)
    programme = models.ForeignKey("programmes.Programme", null=True, blank=True, ...)
    # constraint: exactly one of project/programme must be set
```

`Expense.project` stays required (an expense is always incurred against a specific project's budget line — that's real, deliberate discipline the current self-approval-prevention design relies on). A programme's "budget vs actual" is then: `sum(Budget.total_amount for programme's own Budget) + sum(Budget.total_amount for each child Project's Budget)`, and actual = the same rollup over `Expense`. This gives programme-level totals **and** keeps project-level expense discipline unchanged.

**Funding needs no new model** — `Grant` already does this job (`Programme.grants` M2M, `Project.grant` FK). The "Funding" tab is a read view over data that already exists.

**Reports need no new model** — extend the existing CSV/PDF view functions in `apps/reporting/views.py` with programme-scoped and project-scoped variants (same reportlab/csv approach, just filtered querysets), plus a DSD-shaped export that reads the same underlying data. No submission integration, per your explicit instruction.

**"ONE SOURCE OF TRUTH":** every report (Programme, Project, Funder, M&E, Financial, DSD-shaped) reads from the same models — `Programme`, `Project`, `Activity`, `Outcome/Output/Indicator/IndicatorPeriodValue`, `Beneficiary`, `AttendanceRecord`, `Budget/BudgetLine/Expense`, `Grant`, `Document`. Nothing is duplicated into a report-specific table.

---

## 4. Existing Functionality That Can Be Reused As-Is

- **`monitoring_evaluation.programme_me` view/template** — already the exact "M&E tab" content (Outcomes, Outputs, Indicators, inline add-forms), already programme-scoped, already permission-checked (`me.view`/`me.manage`). Becomes the M&E tab's queryset/logic essentially unchanged; only the template wrapper changes (rendered inside the Programme Workspace's tab body instead of its own full page).
- **`projects.project_detail` view/template** — already a mini-workspace (Tasks + Budget + Expenses inline). Becomes the base for the Project Workspace with minimal change; already has the right permission checks (`projects.manage`).
- **`beneficiaries.beneficiary_list`** — already accepts `?programme=<id>`; the People tab links straight to it, or the query logic is inlined into the workspace view.
- **`impact.people_reached_for_organisation` and the wider `impact_dashboard` aggregation logic** — reusable per-programme by adding a programme filter to the same queries (`AttendanceRecord.filter(programme=...)` etc.), not a rewrite.
- **`organisations.health.compute_health_check` / `_programme_management` dimension** — the "items requiring attention" panel on the Programme Workspace can reuse the same recommended-actions pattern already proven on the Organisation Dashboard.
- **`documents` app in full** — upload form, visibility rules, versioning, download view, GFK — all reused as-is for Evidence, only the "what am I attached to" wiring is new.
- **`grants` app in full** — Funding tab is a read-only view over `Programme.grants`/`Project.grant`, no changes needed.
- **The Organisation onboarding wizard mechanism** (`apps/organisations/models.py::ONBOARDING_STEP_CHOICES`/`onboarding_step`, `apps/organisations/views.py::create`/`onboarding_step`/`_advance`) — this is a working, tested, proven step-wizard pattern already in the codebase. The Programme wizard should copy this exact mechanism (see §8), not invent a new one.
- **`reporting`'s CSV/PDF generation code** (csv.writer / reportlab patterns) — reused, just re-scoped querysets.
- **`apps.core.permissions.has_org_capability`** — every new view uses the same capability-check pattern already used everywhere else (`programmes.manage`, `projects.manage`, `me.manage`, `attendance.manage`, `beneficiaries.manage`, `documents.manage`, etc.) — no new permission scope needed, these all already exist.

---

## 5. Models That Need Modification

| Model | Change | Why | Breaking? |
|---|---|---|---|
| `programmes.Programme` | Add `start_date`, `end_date` (period); expose existing `locations`, `services`, `target_beneficiary_groups` in the form; add plan-narrative fields (see below) | No period fields exist at all today; JSON fields exist but no form ever writes to them | No — all new fields nullable/blank, existing rows unaffected |
| `programmes.Programme` | Add `wizard_step` (or reuse a similar pattern to `onboarding_step`) | Drives the guided-creation wizard | No — new field, default value |
| `programmes.Activity` | Add `project` FK, nullable | Lets an activity optionally sit inside a project, per your target diagram, without breaking programme-only activities | No |
| `projects.ProjectTask` | Add `activity` FK, nullable | Lets a task optionally sit under a specific activity | No |
| `expenses.Budget` | Make `project` nullable; add `programme` FK, nullable; add a `clean()`/constraint requiring exactly one of the two | Enables a Programme Budget without duplicating the Budget/BudgetLine model | **Existing `Budget.project` OneToOne rows are unaffected** (still set, still valid) — the migration only relaxes the field, it doesn't touch data |
| `documents.Document` | No schema change — wire up existing `category=CATEGORY_PROGRAMMES` + GFK from the new Evidence tab views | Reuse, not modification | No |
| `attendance` views | No model change — add a `?programme=` filter to `attendance_list`, matching the existing pattern already used in `beneficiary_list` | Small, additive | No |

### Programme Plan fields — proposed additions to `Programme` (not a separate model)

A separate `ProgrammePlan` model would only be justified if the plan needed independent versioning/approval workflow (like `PolicyVersion` does for policies). Nothing in your brief asks for that yet, and adding one now would be exactly the kind of unnecessary duplicate concept the brief explicitly warns against ("must not create duplicate Programme... concepts"). Recommendation: **extend `Programme` directly** with these DSD-aligned fields, all optional/blank so existing programmes remain valid:

- `need_and_background` (text) — service specification / description / need / motivation
- `implementation_plan` (text) — how the programme will be delivered
- `staffing_plan` (text) — staffing/resources narrative (a simple text field, not a new HR module — no existing model has role/FTE tracking, and building one is out of scope per "do not overbuild")
- `previous_experience` (text, blank) — only relevant for orgs with a delivery history; optional
- `monitoring_plan` (text) — how the programme will be monitored/reported on, separate from the structured Indicators themselves
- `funding_request_notes` (text, blank) — narrative funding ask, distinct from the structured `Grant` records

If you'd rather have Plan content live in its own model (e.g. to support a future "Plan approved by board" workflow, mirroring `Policy`/`PolicyVersion`), say so explicitly — it's a reasonable alternative, just not the minimal path, and it's the one open question in this section I'd like a decision on before implementation.

---

## 6. Models That Need to Be Added

**None**, under the recommendation above. Every requirement in your brief maps onto an existing model plus the modifications in §5:

| Your requirement | Maps to |
|---|---|
| Programme Plan | `Programme` (extended, §5) |
| Projects | `projects.Project` (exists) |
| Activities | `programmes.Activity` (exists, gains `project` FK) |
| Tasks | `projects.ProjectTask` (exists, gains `activity` FK) |
| People / Attendance | `beneficiaries.Beneficiary` + `attendance.AttendanceRecord` (exist) |
| Evidence | `documents.Document` + GFK (exists, gets wired up) |
| Outcomes | `monitoring_evaluation.Outcome` (exists) |
| Indicators / Targets | `monitoring_evaluation.Indicator` + `IndicatorPeriodValue` (exist) |
| Programme Budget | `expenses.Budget` (generalised, §5) |
| Funding | `grants.Grant` (exists) |
| Reports | new *views*, not new models, in `apps/reporting` |

If, during implementation, the Budget generalisation in §5 turns out to be messier than expected (e.g. the mutually-exclusive-FK constraint proves awkward in practice), the fallback is a small dedicated `ProgrammeBudget`/`ProgrammeBudgetLine` pair mirroring `Budget`/`BudgetLine` exactly — more duplication, but simpler mechanically. I recommend trying the generalised-`Budget` approach first.

---

## 7. Migration Strategy

All changes are additive (nullable new fields/FKs, relaxed nullability on one existing field). No destructive migrations, no data backfill required for correctness (existing rows keep working exactly as before with the new fields simply blank/null). Sequenced as:

1. `programmes`: add `Programme.start_date`, `end_date`, `need_and_background`, `implementation_plan`, `staffing_plan`, `previous_experience`, `monitoring_plan`, `funding_request_notes`, `wizard_step`; add `Activity.project` (nullable FK).
2. `projects`: add `ProjectTask.activity` (nullable FK).
3. `expenses`: relax `Budget.project` to nullable, add `Budget.programme` (nullable FK) + a `CheckConstraint`/`clean()` for exactly-one-set. Existing `Budget` rows already have `project` set, so they remain valid without any data migration.
4. No changes at all to `beneficiaries`, `attendance` (model-level), `monitoring_evaluation`, `grants`, `documents` — only their views/templates change.
5. Run `manage.py makemigrations` per app, review the generated SQL (should be pure `ADD COLUMN` / `ALTER COLUMN ... DROP NOT NULL`), run the full test suite before and after each app's migration to isolate any regression immediately.
6. Deploy order doesn't matter for zero-downtime since every change is additive; no need to stage model and code deploys separately.

---

## 8. Programme Wizard Flow

Reuses the Organisation onboarding mechanism (`onboarding_step` field + step-dispatch view + per-step `ModelForm` bound to the same instance) rather than a session-based multi-step form, because that pattern is already proven, tested (indirectly, via the onboarding smoke test) and familiar to anyone maintaining this codebase.

```
programmes:create  (POST creates the Programme immediately after step 1,
                     status=STATUS_PLANNED, wizard_step="details")
   ↓
programmes:wizard_step  (slug, programme_id, step)  — one URL, step-dispatched,
                          same shape as organisations:onboarding_step
```

| # | Step | Backs onto |
|---|---|---|
| 1 | Programme details | `Programme.name`, `programme_area`, `status` |
| 2 | Need / background / purpose | `Programme.description`, `need_and_background`, `theory_of_change_summary` |
| 3 | Beneficiaries | `Programme.target_beneficiary_groups` (JSON, already exists) |
| 4 | Geographic coverage | `Programme.locations` (JSON, already exists) |
| 5 | Programme period | `Programme.start_date`, `end_date` (new) |
| 6 | Outcomes | Create `monitoring_evaluation.Outcome` rows against this programme (reuses `OutcomeForm`) |
| 7 | Indicators and targets | Create `monitoring_evaluation.Indicator` rows (reuses `IndicatorForm`) |
| 8 | Projects | Create `projects.Project` row(s) with `programme` pre-set (reuses `ProjectForm`); optional step — a programme can finish the wizard with zero projects |
| 9 | Activities | Create `programmes.Activity` row(s) (reuses `ActivityForm`); optional |
| 10 | Staffing/resources | `Programme.staffing_plan` (new, free text for v1) |
| 11 | Budget | Create the programme-level `Budget`/`BudgetLine` (generalised model, §5) |
| 12 | Funding | Attach existing `Grant` records via `Programme.grants` M2M (reuses the same queryset restriction already in `ProgrammeForm`) |
| 13 | Review and create | Read-only summary of everything captured; submit sets `status` to the user's chosen value and `wizard_step` to a `complete` sentinel |

Every step after #1 is skippable/revisitable exactly like the organisation onboarding wizard already is (a user can leave and resume). Steps 6–12 are genuinely optional in substance — DSD requires them for a *submission-ready* programme, but Bohlale shouldn't block someone from saving a partially-planned programme and coming back later. The wizard nudges completeness; it doesn't gate it.

The **Project creation wizard** you described in §2 of your message is lighter — a Project's fields (name, objective, description, manager, dates, location, status, budget, funding source) mostly already exist on `Project` today except **`objective`** and **`location`**, which would need to be added as two more nullable fields on `Project` (not listed above because they weren't in your explicit "models that need modification" framing, but flagging them here for completeness — trivial additions, same additive-migration pattern). Given how few new fields that is, a single well-organised form (like the current `ProjectForm`, just with two more fields) is proportionate — a full 13-step wizard for a Project would be overbuilding relative to what a Project actually needs to capture.

---

## 9. Programme Workspace Design

Replaces `programmes/programme_detail.html` (the inline-Activity-form dead end) with a tabbed workspace. URL structure stays `programmes:detail` (same route, so no link elsewhere in the codebase breaks) but the view gains a `tab` query param or path segment (`programmes:detail` + `?tab=projects`, matching the existing `.tabs` component pattern already built for the Organisation Dashboard and Staff Overview in the last two redesign passes — same CSS, same markup convention, no new component).

```
Breadcrumb: Programmes / {{ programme.name }}
Page header: {{ programme.name }}  ·  {{ programme.get_status_display }}  ·  {{ period }}

Compact summary bar (same .summary-bar component as the Organisation Dashboard):
  Status | Period | Active Projects | Active Activities | People Reached | Budget vs Actual

Tabs: Overview | Plan | Projects | Activities | People | M&E | Finance | Evidence | Reports

Overview (default landing tab — replaces the current bare default):
  - Programme summary (description, theory of change, beneficiary groups, locations)
  - Outcomes & Indicators table (Area / Score-or-latest-actual / Target — same table
    pattern as the Organisation Health table already built)
  - Projects table (name, status, budget, dates) — same dense-table pattern
  - Activities table (name, date, status, linked project if any)
  - People reached (reuses apps.impact logic, filtered to this programme)
  - Budget vs Actual (reuses the generalised Budget rollup from §3)
  - Upcoming work (activities with scheduled_date >= today, tasks with due_date >= today
    across the programme's projects)
  - Items requiring attention (same recommended-actions pattern as the Organisation
    Health dimensions: no outcomes defined yet / no indicators / budget not set /
    activities overdue, etc.)

Plan: the DSD-aligned narrative fields (§5) in an editable form, permission-gated
  the same way onboarding forms are (programmes.manage)

Projects: table of this programme's projects + "New project" (pre-fills programme),
  reusing projects/list.html's table markup

Activities: table of this programme's activities (with or without a project),
  the existing ActivityForm as a proper "New Activity" action — NOT inline on
  the default page anymore, moved to its own tab/modal-equivalent page

People: beneficiaries.beneficiary_list filtered to this programme (already
  supports ?programme=), embedded/linked

M&E: monitoring_evaluation.programme_me's existing content, reused near-verbatim

Finance: programme-level Budget/BudgetLine (new) + a rollup table of the
  programme's projects' budgets and expenses (links out to each project's
  own Finance for line-item detail — not duplicating project expense management)

Evidence: documents filtered to related_object=this programme (category=programmes),
  reusing the existing Document upload/list/download flow

Reports: programme-scoped exports (CSV/PDF) — Programme Report, M&E Report,
  Financial Report, Funder Report, DSD-shaped Report — all reading the same
  underlying querysets as the tabs above
```

**Removed from the default page**: the inline `ActivityForm`. Adding an activity becomes an explicit action (its own small form page, same pattern as `attendance:record` or `beneficiaries:create` today — a dedicated `programmes:create_activity` view, not a modal, keeping the "no unnecessary standalone screens" instruction in mind by making it a lightweight sub-page rather than a whole new IA branch).

---

## 10. Project Workspace Design

`projects/project_detail.html` is already closest to this shape and needs the least structural change — it already inlines Tasks + Budget + Expenses. Reorganise into the same tab pattern for consistency with the Programme Workspace and the rest of the redesigned shell:

```
Breadcrumb: Programmes / {{ programme.name }} / {{ project.name }}   (or
            just Projects / {{ project.name }} if the project has no programme)
Page header: {{ project.name }}  ·  {{ project.get_status_display }}

Summary bar: Status | Manager | Period | Budget vs Actual

Tabs: Overview | Activities | Tasks | People | Budget | Expenses | Evidence | Reports

Overview: objective, description, location, manager, dates, linked programme,
  linked grant/funding source, key stats

Activities: this project's activities (Activity.project FK, new) — the same
  Activity list/create views as the Programme Workspace's Activities tab,
  just filtered/pre-filled to this project instead

Tasks: existing ProjectTask list + form, unchanged, gains optional activity link

People: attendance/beneficiaries scoped to this project's activities
  (via Activity.project → AttendanceRecord.activity)

Budget: existing project_budget + BudgetLine, unchanged

Expenses: existing expenses:project_expenses content, embedded as a tab
  instead of (or in addition to) its own page

Evidence: documents filtered to related_object=this project

Reports: project-scoped exports, same generation code as Programme Reports,
  filtered one level deeper
```

Because a Project's parent Programme is optional, the workspace degrades gracefully for a standalone project (no Programme breadcrumb segment, no "back to programme" link) — this must NOT force every project to have a programme.

---

## 11. Testing Strategy

Given the near-total absence of existing tests in this area (§1), this rebuild is also the first real opportunity to put a safety net under programme delivery. Proposed coverage, mirroring the test patterns already established elsewhere in this codebase (`apps/accounts/tests.py`, `apps/staffadmin/tests.py`, `apps/organisations/tests.py`):

1. **Migration correctness**: a smoke test per app confirming `manage.py check` is clean and an existing `Budget`/`Activity`/`ProjectTask` row created before the migration still round-trips correctly with the new fields blank/null.
2. **Model-level tests**: the `Budget` mutually-exclusive-FK constraint (both set → error; neither set → error; exactly one → valid) — this is the one genuinely new piece of business logic being added.
3. **Wizard tests** (mirroring `apps.organisations.tests.SmokeTestGoldenPath`): create a programme through every wizard step, assert `wizard_step` advances correctly at each stage, assert a user can resume a partially-completed wizard, assert the final "Review and create" step is idempotent (doesn't duplicate Outcomes/Indicators/Projects if revisited).
4. **Programme Workspace tests** (mirroring `apps.organisations.tests.WorkspaceDashboardTests` from the last redesign): each tab returns 200 for a permitted user, 403 for a user without the relevant capability (`programmes.manage`, `me.view`, `projects.manage`, `attendance.view`, `documents.view`, etc. — reusing existing capability names), the Overview tab's "items requiring attention" and "budget vs actual" figures match real database aggregates (not fabricated), tabs link to real reachable URLs.
5. **Project Workspace tests**: same shape as above, plus a specific test that a Project with `programme=None` renders correctly (no orphaned-reference errors).
6. **Cross-app relationship tests**: an `Activity` with both `programme` and `project` set is queryable from both directions; attendance recorded against that activity's `AttendanceRecord.programme` still matches `Activity.programme` (data-consistency check, since `AttendanceRecord.programme` isn't derived from `Activity.project.programme` automatically — worth asserting this explicitly rather than assuming).
7. **Evidence/Document GFK tests**: uploading evidence against a Programme/Project/Activity sets `content_type`/`object_id` correctly, and the existing `_can_view_document` visibility check still applies unchanged.
8. **Reporting tests**: each new programme-scoped/project-scoped export endpoint returns the correct content-type and only includes rows belonging to that programme/project (tenant-isolation-style test, same pattern as `apps.organisations.tests.TenantIsolationTests`).
9. **Regression run**: full existing suite (currently 102 tests) must stay green throughout — every step above is additive, so nothing existing should need to change to keep passing.

Given the size of this surface, I'd implement and test §5's model changes first (in isolation, fully tested) before touching any view/template, exactly matching the priority order you gave: **Programme → Project → Activity → People/Evidence → M&E → Finance → Reporting.**

---

## Open decisions before implementation

1. **Programme Plan**: extend `Programme` directly (recommended, §5) vs. a separate versioned `ProgrammePlan` model. I need a decision if you want the latter.
2. **Programme Budget**: generalise `expenses.Budget` with a mutually-exclusive programme/project FK (recommended, §5/§6) vs. a dedicated parallel `ProgrammeBudget` model. I'd try the generalised approach first and fall back if it proves awkward — flag if you'd rather I go straight to the dedicated-model fallback.
3. **Staffing/resources**: a plain text field for v1 (recommended) vs. something more structured now. I'm recommending text-only to avoid building an HR/roles module that isn't otherwise asked for.
4. **DSD source document**: if you have the actual DSD form/guideline PDF, please attach it so I can reconcile §3/§8's field list against the real thing before implementation starts.

Nothing will be built until you confirm the direction on these four points (or tell me to proceed with the recommended defaults) and approve the overall approach.
