# Programme Workspace — Architecture Proposal (v3, DSD-reconciled)

Status: **proposal only — nothing in this document has been implemented.** No models, views, templates, migrations or tests have been changed.

## DSD source material — now reconciled

The three uploaded files have been read in full and used as the actual source for this revision (not paraphrase):

- `NDSD_GUIDELINE_ON_COMPLETING_2027/28_2029/30_APPLICATION_FORM2.docx` — the applicant guideline, walking through every section of the application form
- `2027_2029/30_NDSD_STANDARD_APPLICATION_FORM.docx` — the actual fillable form, including the real Part C table structures (column-by-column)
- `Website_constitution_checklist.docx` — NPO constitution clause checklist (section 12(2) of the NPO Act). This is unrelated to Programme architecture — it's about the organisation's founding document, not programme planning — so it isn't used below and stays fully out of scope, consistent with "do not touch Constitution... yet."

Everything DSD-specific in this document is now grounded in the real form text, not inference. Two places below are still explicitly flagged as gaps the real document exposes, not filled in with invented detail (§8).

---

## 0. Decisions confirmed this round

1. Programme Plan extends `Programme` directly for V1. No separate versioned plan model.
2. `expenses.Budget` is generalised to belong to either a Programme or a Project, mutually exclusive.
3. Staffing/resources: simple structured fields only where the chain-of-connection actually needs them (`Activity.responsible_person`) — no staff-roster subsystem in V1.
4. DSD is a reporting/application **profile** over the generic model, not a driver of the core schema. Confirmed below with the real Part C structure.

**New governing rules from this round**, both incorporated below:

- **Programme is the only container the user needs to understand.** The underlying relationships (`Activity → Output`, `Activity → BudgetLine`, `Activity → User`) are implementation detail. The user-facing IA is exactly `Organisation → Programme → Project → Activity`, navigated inside one Programme Workspace via `Plan | Projects | Activities | People | M&E | Finance | Evidence | Reports`.
- **Progressive context inheritance.** Creating an Activity inside a Project inside a Programme must pre-fill everything the system already knows (organisation, programme, project, period, location, manager, relevant outputs, budget context) so the user only supplies what's genuinely new. Detailed in §1.2.

---

## 1. Governing Principles

### 1.1 Programme as the sole user-facing container

The six new relationships proposed in v2 (`Activity.project`, `Activity.outputs`, `Activity.responsible_person`, `Activity.budget_line`, `ProjectTask.activity`, `Project.objective`/`location`) are all still correct and still needed — the real DSD form's Part C, Section C3.1 table (quoted verbatim in §8) independently confirms exactly this shape: one row per Activity, columns for Output Indicators, Expected Results, Personnel and Resources, Area of Operation, and Budget Costs. **What changes this round is not the schema, it's that none of these relationships are ever surfaced to the user as things to "connect."** They're populated automatically (§1.2) or chosen from an already-filtered dropdown (e.g. "which Output does this contribute to" only lists Outputs that already belong to this Programme) — never presented as a generic relational picker.

### 1.2 Progressive context inheritance — what gets pre-filled, and from where

```
Organisation
  └─ Programme "Youth Digital Literacy"        (status, period: start_date/end_date)
       └─ Project "Digital Skills Bootcamp"    (location, manager, own Budget)
            └─ Activity "HTML & CSS Workshop"  (creating this now)
```

When the user clicks "New Activity" from inside a Project (the normal path), the create form is seeded with:

| Field | Pre-filled from | User must still provide |
|---|---|---|
| `programme` | the Project's own `programme` FK — set silently, never shown as a choice | — |
| `project` | the Project the user is inside — set silently | — |
| `location` | defaults to `Project.location`; shown as an editable field, not hidden, since a specific activity can happen elsewhere | only override if different |
| Activity date bounds | the date picker is constrained to fall within `Programme.start_date`/`end_date` when those are set — a soft guide via min/max attributes, not a hard block | the actual date |
| `responsible_person` | defaults to `Project.manager` in the dropdown's initial selection; the dropdown itself is scoped to the organisation's active members (existing pattern, same as `ProjectTask.assignee`) | only override if someone else runs this specific activity |
| `outputs` (choices offered) | the multi-select only lists `Output`s that already belong to this Programme (via `programme.outputs`) — never a global list | tick which ones apply, or none |
| `budget_line` (choices offered) | the dropdown only lists `BudgetLine`s from this Project's own `Budget` (falling back to the Programme's own Budget if the Project has none) — never a global list | pick one, or leave blank |

This is the concrete mechanism behind "the user should only have to provide what is genuinely new." Nothing here is a new model or a background job — it's how the Activity creation view builds its form: `instance` pre-population plus scoped `queryset` filtering, the same pattern `ProjectForm.__init__(organisation=...)` already uses today to scope its `grant`/`programme`/`manager` fields (§4 of v1, unchanged reuse).

### 1.3 DSD as a profile, not the product model

Confirmed by the real source (§8): DSD requires **Part C to be completed separately for each service specification**, and its budget section (C6.2) explicitly says "Must be aligned to the budget as per section C3.1 above" and must not mix unrelated programmes/projects. Bohlale's generic model — Programme → Project → Activity, with the generalised Budget attaching to exactly one Programme or Project — already satisfies this without knowing what DSD is. The DSD-shaped export (§8) is a **read-only view over existing data**, parameterised by "which Project is this Part C for," never a stored DSD concept in the core schema. The same underlying data also has to serve foundations, corporate funders, international donors and purely internal reporting — none of those get a special code path either; they're all just different templates over the same Programme/Project/Activity/Output/Indicator/Budget data.

---

## A. Programme Information Architecture

```
Organisation
 └─ Programme Workspace                                  (one screen, tabbed)
      ├─ Overview   (default landing — dashboard, per your original brief)
      ├─ Plan       (DSD-aligned narrative + structured fields, §8)
      ├─ Projects   (table + create; each row opens a Project Workspace)
      ├─ Activities (table across the whole programme, with/without a project)
      ├─ People     (beneficiaries + attendance, programme-scoped)
      ├─ M&E        (Outcomes → Outputs → Indicators → Targets/Actuals)
      ├─ Finance    (Programme's own Budget + rollup across child Projects)
      ├─ Evidence   (Documents linked to this Programme/Project/Activity)
      └─ Reports    (Programme/Project/Funder/M&E/Financial/DSD-shaped exports)
```

Note: your message lists the tab bar as `Plan | Projects | Activities | People | M&E | Finance | Evidence | Reports` (no separate "Overview" named). I've kept **Overview as the default landing tab** because it directly answers the still-standing instruction from two messages ago — "the default page should be an operational dashboard" — Plan then becomes the tab for the narrative/DSD-aligned fields specifically, rather than also being the landing page. If you'd rather Plan *be* the landing page and drop Overview entirely, say so; it's a one-line change to which tab is default, not a structural one.

The Project Workspace is IA-identical one level down:

```
Programme "Youth Digital Literacy"
 └─ Project Workspace: "Digital Skills Bootcamp"
      ├─ Overview
      ├─ Activities
      ├─ Tasks
      ├─ People
      ├─ Budget
      ├─ Expenses
      ├─ Evidence
      └─ Reports
```

---

## B. Programme Workspace Wireframe

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Programmes / Youth Digital Literacy                          [breadcrumb]│
│                                                                            │
│ Youth Digital Literacy                              [Status: Active]     │
│                                                                            │
│ ┌─ Readiness ──────────────────────────────────────────────────────────┐ │
│ │ Ready for reporting                                                   │ │
│ │ ✓ Programme plan  ✓ Beneficiaries  ✓ Projects  ✓ Activities          │ │
│ │ ✓ Indicators  ✓ Budget  ✗ Evidence  ✗ Funding                        │ │
│ │ Missing: at least one funding source, evidence for this period        │ │
│ └────────────────────────────────────────────────────────────────────── │
│                                                                            │
│ [Period: Apr 2027–Mar 2030] [Projects: 2] [Activities: 6] [People: 84]   │
│                                                                            │
│  Overview │ Plan │ Projects │ Activities │ People │ M&E │ Finance │      │
│  Evidence │ Reports                                                      │
│  ─────────                                                                │
│                                                                            │
│  Outcomes & Indicators                        Upcoming work              │
│  ┌────────────────────────────────┐           ┌───────────────────────┐ │
│  │ Outcome           Indicator  %  │           │ HTML & CSS Workshop    │ │
│  │ Digital literacy  Youth ...  62%│           │ Tue 14 Oct · Bootcamp  │ │
│  └────────────────────────────────┘           └───────────────────────┘ │
│                                                                            │
│  Projects                                      Budget vs Actual          │
│  ┌────────────────────────────────┐           ┌───────────────────────┐ │
│  │ Digital Skills Bootcamp  Active │           │ R120,000 / R180,000    │ │
│  │ Community Outreach     Planning │           │ 67% of programme       │ │
│  └────────────────────────────────┘           │ budget spent            │ │
│                                                 └───────────────────────┘ │
│                                                                            │
│  Items requiring attention                                               │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ No funding source linked yet.                          Add →       │ │
│  │ Community Outreach project has no activities yet.       Add →      │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

Same visual language already established in the last two redesign passes: `.summary-bar` for the compact metrics row, `.tabs`, dense `.card-flat` tables — no new components.

---

## C. Project Workspace Wireframe

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Programmes / Youth Digital Literacy / Digital Skills Bootcamp            │
│                                                                            │
│ Digital Skills Bootcamp                               [Status: Active]   │
│ Manager: Thandiwe M. · Location: Khayelitsha · Apr 2027 – Mar 2028        │
│                                                                            │
│  Overview │ Activities │ Tasks │ People │ Budget │ Expenses │ Evidence │  │
│  Reports                                                                  │
│  ─────────                                                                │
│                                                                            │
│  Objective: Equip 50 unemployed youth with entry-level digital skills    │
│                                                                            │
│  Activities                                    Budget vs Actual          │
│  ┌────────────────────────────────┐           ┌───────────────────────┐ │
│  │ HTML & CSS Workshop   Planned   │           │ R45,000 / R60,000      │ │
│  │ Intro to Excel        Delivered │           │ 75% spent               │ │
│  └────────────────────────────────┘           └───────────────────────┘ │
│                                                                            │
│  Tasks                                          People reached: 38       │
│  ┌────────────────────────────────┐                                     │
│  │ Book venue           Done       │                                     │
│  │ Print certificates   To Do      │                                     │
│  └────────────────────────────────┘                                     │
└──────────────────────────────────────────────────────────────────────────┘
```

`objective` is the new `Project.objective` field (§E) — it's the DSD C3.1 "Objective" line surfaced plainly, but it's just a text field on Project, useful for any funder, not DSD-specific.

---

## D. New Programme Wizard

Unchanged mechanism from v2 (reuse `Organisation.onboarding_step`-style dispatcher). Step content, confirmed against the real Part C structure:

| # | Step | Backs onto | DSD Part C section it satisfies (confirmed) |
|---|---|---|---|
| 1 | Programme details | `Programme.name`, `programme_area`, `status` | C1 (service reference is export-time input, not stored here — §1.3) |
| 2 | Need / background / purpose | `Programme.description`, `need_and_background`, `theory_of_change_summary` | C2.1 |
| 3 | Beneficiaries | `Programme.target_beneficiary_groups` (existing JSON) | C2.2 |
| 4 | Geographic coverage | `Programme.locations` (existing JSON) | C2.3 |
| 5 | Programme period | `Programme.start_date`, `end_date` (new) | C2.4 (time-related elements narrative stays free text within `need_and_background` — no separate structured field, since the guideline's list — time of day/week/month/season/school calendar — is illustrative prompting, not a data schema) |
| 6 | Outcomes | `monitoring_evaluation.Outcome` rows | Maps to DSD's "Objective" grouping in C3.1 — see §8 |
| 7 | Outputs | `monitoring_evaluation.Output` rows | Feeds "Expected Results" in C3.1 |
| 8 | Indicators and targets | `monitoring_evaluation.Indicator` rows | C3.2 |
| 9 | Projects | `projects.Project` (+ new `objective`, `location`) | Per-service breakdown when a Programme covers >1 service — confirmed, not inferred (§8) |
| 10 | Activities | `programmes.Activity` (+ new `project`/`outputs`/`responsible_person`/`budget_line`, all pre-filled per §1.2) | C3.1 row-level detail |
| 11 | Staffing/resources | `Programme.staffing_plan` (narrative) + `Activity.responsible_person` already set in step 10 | Partially — C4 wants a full staff roster with demographics; V1 does not build this (§8 gap #1) |
| 12 | Budget | Programme-level `Budget`/`BudgetLine` (generalised model) | C6.2 conceptually, single-year only in V1 (§8 gap #2) |
| 13 | Funding | `Programme.grants` M2M | C7 |
| 14 | Review and create | Read-only summary; sets `status` + wizard completion | — |

Every step after #1 stays skippable/resumable.

---

## E. Existing → New Model Mapping

| Existing model (unchanged) | New field(s) | Type | Purpose |
|---|---|---|---|
| `programmes.Programme` | `start_date`, `end_date` | Date, nullable | Programme period (C2.4) |
| | `need_and_background`, `implementation_plan`, `staffing_plan`, `previous_experience`, `monitoring_plan`, `funding_request_notes` | Text, blank | Plan tab narrative (C2.1, C3, C4 summary, C5, C3.2 narrative, C7) |
| | `wizard_step` | CharField + choices | Drives the guided wizard (§D) |
| `programmes.Activity` | `project` | FK → `projects.Project`, nullable | Activity can sit inside a specific project |
| | `outputs` | M2M → `monitoring_evaluation.Output` | What this activity produces — reaches Indicators/Outcomes transitively |
| | `responsible_person` | FK → User, nullable | Personnel (C3.1) — simple, no roster |
| | `budget_line` | FK → `expenses.BudgetLine`, nullable | Budget cost (C3.1) at activity granularity |
| `projects.Project` | `objective`, `location` | Text/Char, blank | Per-service detail (C3.1 "Objective", C2.3 per-project) |
| `projects.ProjectTask` | `activity` | FK → `Activity`, nullable | Task scoped to a specific activity, optional |
| `expenses.Budget` | `programme` (new, nullable) + `project` (existing, now nullable) | FK×2, exactly-one-set constraint | Programme-level or Project-level budget, never mixed (C6.2 rule) |

**No new models.** `monitoring_evaluation.{Outcome,Output,Indicator,IndicatorPeriodValue}`, `beneficiaries.Beneficiary`, `attendance.AttendanceRecord`, `grants.Grant`, `documents.Document` are all unchanged — reused exactly as they are today.

---

## F. Data Flow — One Source of Truth, Many Reports

```
                         ┌─────────────────────────────────────┐
                         │   Programme / Project / Activity     │
                         │   Outcome → Output → Indicator       │
                         │   Beneficiary / AttendanceRecord     │
                         │   Budget → BudgetLine → Expense      │
                         │   Grant                              │
                         │   Document (evidence, GFK)            │
                         └───────────────┬───────────────────────┘
                                         │  (read-only queries, filtered
                                         │   by programme_id / project_id)
              ┌──────────────┬───────────┼───────────┬──────────────┬────────────┐
              ▼              ▼           ▼           ▼              ▼            ▼
        Programme        Project      M&E         Financial      Funder      DSD-shaped
        Report           Report       Report      Report         Report      Report
        (umbrella,       (one         (Outcomes/  (Budget vs     (whatever   (Part C
        everything       service,     Outputs/    Actual,        a specific  layout, one
        under this       Part-C-      Indicators, expense        funder's    Project =
        programme)       shaped)      targets vs  detail)        agreement   one service
                                       actuals)                   asks for)   specification)
```

Every report is a view function in `apps/reporting`, reusing the existing csv/reportlab generation code (v1 §11/v2 §11, unchanged), reading the exact same querysets the Programme/Project Workspace tabs already display. Nothing is precomputed into a separate report table — the same live-query discipline already enforced everywhere else in this codebase (`impact_dashboard`'s "every figure derived live" rule) applies here too.

---

## Programme Readiness (new requirement, item 5)

Not a percentage. A checklist, computed the same way `apps.organisations.health.compute_health_check` already works (reused pattern, not a new mechanism):

```python
def compute_programme_readiness(programme):
    checks = [
        ("plan", "Programme plan", bool(programme.need_and_background)),
        ("outcome", "Programme outcome", programme.outcomes.exists()),
        ("indicator", "At least one measurable indicator", programme.indicators.exists()),
        ("project", "Project", programme.projects.exists()),
        ("activity", "Activity", programme.activities.exists()),
        ("beneficiaries", "Beneficiaries", programme.beneficiaries.exists()),
        ("budget", "Budget", Budget.objects.filter(
             Q(programme=programme) | Q(project__programme=programme)).exists()),
        ("funding", "Funding information", programme.grants.exists()),
        ("evidence", "Evidence", Document.objects.filter(
             content_type=..., object_id__in=[programme.id, *programme.projects.values_list("id")]).exists()),
    ]
    missing = [label for key, label, ok in checks if not ok]
    return {"checks": checks, "missing": missing, "ready": not missing}
```

Rendered on the Overview tab exactly as your wireframe shows: "Missing: ..." list when incomplete, a green checklist when everything required is present. No score, no percentage — a direct, honest yes/no per item, same spirit as the Health Check's per-dimension reasons/actions.

---

## 8. DSD Part C — Confirmed Structure and Flagged Gaps

Quoting the real Standard Application Form, Section C3.1 table columns (verbatim from the document):

> `ACTIVITIES TO IMPLEMENT PROJECT OR PROGRAMME` | `OUTPUT INDICATORS (targets and results of the actions/activities)` | `EXPECTED OR DESIRED RESULTS OF PROJECT, PROGRAMME (outcomes)` | `PERSONNEL AND RESOURCES (physical and material resources needed to achieve the Objectives)` | `AREA OF OPERATION` | `BUDGET COSTS (What are the financial costs & type of personnel...)`

— repeated once per `Objective:` block, ending in `Total per Objective`. This is the exact row-per-Activity shape already designed in §1.1/§E: **Output Indicators** = `Activity.outputs`, **Expected Results** = reached transitively via `Output.outcome`, **Personnel and Resources** = `Activity.responsible_person`, **Area of Operation** = `Activity.location` (existing field), **Budget Costs** = `Activity.budget_line`.

**"Objective" maps to Bohlale's existing `Outcome`** — DSD groups activities under an Objective and totals budget per Objective; Bohlale already groups Outputs under an Outcome, and Activities now link to Outputs. A DSD export groups its Activity rows by the Outcome reached through their linked Outputs, and sums `budget_line.allocated_amount` per group for "Total per Objective." This is a query in the export view, not a new field.

Section C3.2 (Indicators/Targets/Monitoring) maps exactly to the existing `Indicator.target_value` + `IndicatorPeriodValue.means_of_verification` — confirmed, no gap.

**Two real gaps, flagged rather than filled with invented fields:**

1. **Section C4 (Staffing Plan)** asks for a full roster of *every* staff member in the organisation (not just this programme) with name, qualifications, nationality, gender, race, role, and whether they work on this specific programme. This is materially bigger than `Activity.responsible_person` — it's organisation-wide HR/demographic data, the same category as the existing Board/Governance demographic fields (`GovernanceOfficial`), not something a Programme Workspace should own. **V1 does not build this.** A true DSD C4 export will need either a manual supplementary step at export time or a dedicated future staff-roster feature — explicitly out of scope now, matching decision #3 ("do not over-engineer a staffing subsystem yet").
2. **Section C6.2 (Operational Budget)** is broken out **by financial year** across the funding duration (up to 3 years), each budget item totalled per year and across years. The generalised `Budget`/`BudgetLine` model in this proposal is a flat total with no year dimension. **V1 does not build multi-year budgeting.** If a literal DSD-shaped budget export is needed later, the smallest addition would be an optional `BudgetLine.financial_year` field — deliberately not added now, since nothing else in Bohlale's finance model (`Expense`, `expenses:project_expenses`) has a year dimension either, and adding one only for DSD would contradict "DSD is a profile, not the product model."

Everything else in Part C (C1 service specification reference, C2.1–C2.4 description/beneficiaries/geography/time, C5 previous experience, C7 funding request, C8 declaration) is already covered by existing or newly-proposed fields, or is explicitly an export-time input (C1's service specification reference — §1.3) rather than a stored field.

---

## Migration/Cutover Strategy

Unchanged from v2 — repeated here for completeness, no changes needed:

1. `programmes`: add `Programme.start_date`, `end_date`, `need_and_background`, `implementation_plan`, `staffing_plan`, `previous_experience`, `monitoring_plan`, `funding_request_notes`, `wizard_step`; add `Activity.project`, `Activity.outputs`, `Activity.responsible_person`, `Activity.budget_line`.
2. `projects`: add `Project.objective`, `Project.location`; add `ProjectTask.activity`.
3. `expenses`: relax `Budget.project` to nullable, add `Budget.programme` (nullable) + exactly-one-set constraint.
4. No model changes to `beneficiaries`, `monitoring_evaluation`, `grants`, `documents`; `attendance` gets one new view-level query filter (`?programme=`), no model change.
5. All migrations are `ADD COLUMN`/`ALTER COLUMN ... DROP NOT NULL` — no data backfill, no destructive step. Full test suite run after each app's migration in sequence.
6. Cutover: `programmes:detail`, `monitoring_evaluation:programme_me`, `monitoring_evaluation:indicator_detail`, `expenses:project_expenses` all keep their existing URLs live — the new workspace tabs embed this content rather than replacing it, so nothing that already links to them breaks. The inline "Add Activity" form moves off the default page to its own lightweight create view (§1.2 covers what it pre-fills).

---

## Test Strategy

Unchanged in shape from v2, plus explicit coverage for the two new items this round:

1. Migration correctness, model-level constraint tests (`Budget` exactly-one-of), chain-of-connection tests (`Activity.outputs` → Outcome rollup, `Activity.budget_line` → Budget total) — as in v2.
2. **Progressive inheritance tests** (new): creating an Activity from within a Project pre-fills `programme`/`project` correctly and silently; the `outputs` and `budget_line` querysets offered are scoped to the right programme/project and never leak another programme's data (tenant-isolation-style).
3. **Programme Readiness tests** (new): each checklist item reflects real data (a programme with no Outcome shows "Programme outcome" as missing; adding one flips it); the `ready` flag is only true when every check passes.
4. Wizard, Workspace tab, Evidence/Document GFK, and Reporting tests — as in v2.
5. Full existing suite (currently 102 tests) stays green throughout.

Build order unchanged: **Programme → Project → Activity → People/Evidence → M&E → Finance → Reporting.**

---

## Confirmed out of scope this round

Person/Beneficiary migration, Case Management, Android, Kiosk mode, Constitution/Learning modules (including the constitution checklist document reviewed above), and any rebuild of already-working engines. Nothing will be built until you review this and say go.
