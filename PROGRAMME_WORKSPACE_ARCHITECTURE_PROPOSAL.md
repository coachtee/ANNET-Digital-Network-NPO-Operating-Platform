# Programme Workspace — Architecture Proposal (v2, reviewed direction)

Status: **proposal only — nothing in this document has been implemented.** No models, views, templates, migrations or tests have been changed. This revises the v1 proposal with the four decisions as approved (with adjustments) and the DSD "chain of connection" principle.

**On the DSD source material**: I still do not have the actual DSD application form/guideline file accessible in this session's filesystem — I searched the repository and the container and found nothing DSD-related. Everything DSD-specific in this document is taken directly from what you have quoted or paraphrased in your messages (Part C's coverage list; "activities, targets, expected results/beneficiary changes, personnel/resources, area of operation and corresponding budget costs need to be connected"; the budget-must-be-service-specific rule; the multiple-service-specification/Part C rule). Anywhere I go beyond what you've directly told me, I've labelled it as my inference, not a sourced DSD requirement, per your instruction to flag rather than invent. If the PDF can be committed into the repo (e.g. `docs/reference/dsd-guideline.pdf`) or pasted as text, I'll reconcile this document against it before implementation.

## Decisions as approved

1. **Programme Plan**: extend `Programme` directly for V1. No separate versioned plan model.
2. **Programme Budget**: generalise `expenses.Budget` to belong to either a Programme or a Project, with a mutual-exclusivity rule.
3. **Staffing/resources**: simple structured fields only where the chain-of-connection rule below actually requires them — no staffing subsystem.
4. **DSD alignment**: your quoted material is the source of truth; unstated points are flagged, not invented.

## The governing principle (new, from this round)

You've identified the one piece the v1 proposal didn't yet model: activities, outputs, personnel, area of operation and budget cost need to be **connected to each other**, not just independently listed under a Programme. The result chain this needs to answer is:

```
Why are we doing this?  →  Programme.need_and_background / theory_of_change_summary
What activity delivers it?  →  Activity
What will it produce?  →  Activity.outputs  (NEW — link to monitoring_evaluation.Output)
Who benefits?  →  AttendanceRecord / Beneficiary (already linked via programme/activity)
Who delivers it / what resources?  →  Activity.responsible_person  (NEW — simple FK, no subsystem)
Where?  →  Activity.location  (already exists)
What does it cost?  →  Activity.budget_line  (NEW — optional FK into the generalised Budget)
How do we measure it?  →  Output → Indicator → IndicatorPeriodValue  (already exists,
                            now reachable from Activity via the new outputs link)
```

Three new, all-optional relationships on the existing `Activity` model close this loop. No new "linking" model is needed — every one of these already exists (`Output`, `User`, `BudgetLine`) except the join itself.

On **Part C / multiple service specifications**: you've told me DSD requires a separate Part C per distinct service/project/intervention, and that budgets must be service-specific, not mixed across programmes/projects. My reading (flagged as inference, since I haven't seen the form): this means the DSD-alignment granularity is not always "one Programme = one Part C." An organisation running one umbrella Programme with three distinct funded services should be able to produce three separate, clean Part-C-shaped exports — one per **Project** — each with its own description/objective/beneficiaries/budget, without those budgets bleeding into each other. This is already how the generalised Budget model works (§9) and why `Project` needs its own `objective`/`location` fields (§5), not just Programme-level narrative fields. Programme-level Plan fields (§3/§4) cover the umbrella "why does this Programme exist" narrative; Project-level fields cover the per-service Part C detail when a Programme has more than one fundable service. If this reading is wrong once you can share the actual document, it's a small correction (add/relabel fields), not a structural change.

---

## 1. Current Model Relationships

```
Organisation
 ├─ programmes.Programme (name, description, programme_area, status,
 │                         locations JSON, services JSON,
 │                         target_beneficiary_groups JSON,
 │                         theory_of_change_summary, grants M2M)
 │   └─ programmes.Activity (programme FK required; name, scheduled_date,
 │                            location, status) — no link to Project,
 │                            Output, personnel, or budget today
 │
 ├─ projects.Project (organisation FK required; programme FK optional;
 │                     grant FK optional; name, description, manager,
 │                     start_date, end_date, budget, status)
 │   └─ projects.ProjectTask (project FK required; title, assignee,
 │                             due_date, is_milestone, status)
 │
 ├─ monitoring_evaluation.Outcome (programme FK required)
 ├─ monitoring_evaluation.Output (programme FK required; outcome FK optional)
 ├─ monitoring_evaluation.Indicator (programme FK required; outcome/output
 │                                    FK optional; target_value,
 │                                    auto_from_attendance)
 │   └─ monitoring_evaluation.IndicatorPeriodValue (indicator FK; actual_value)
 │
 ├─ beneficiaries.Beneficiary (organisation FK; programme FK required)
 ├─ attendance.AttendanceRecord (organisation FK; programme FK required;
 │                                 activity FK optional; beneficiary FK optional)
 │
 ├─ expenses.Budget (project FK, OneToOne — no programme-level budget)
 │   └─ expenses.BudgetLine (budget FK; category, allocated_amount)
 │       └─ expenses.Expense (project FK required — not linked to BudgetLine
 │                             consistently at the Activity level today)
 │
 ├─ grants.Grant (organisation FK; funder_name, amount, dates,
 │                 reporting_requirements) — the Funding model
 │
 ├─ documents.Document (category=CATEGORY_PROGRAMMES already exists as a
 │                       choice; content_type/object_id/related_object GFK
 │                       exists and works — unused for programmes today)
 │
 ├─ impact.* — no models; pure aggregation views
 └─ reporting.* — no models; four org-wide CSV/PDF view functions
```

Full detail on views/URLs/test-coverage gaps is unchanged from v1 §1 — not repeated here to keep this document focused on what changed.

---

## 2. Target Model Relationships

```
Organisation
 └─ Programme                                    [EXTENDED — Plan fields, period]
     ├─ Outcomes
     │    └─ Outputs
     │         └─ Indicators → IndicatorPeriodValue (targets/actuals)
     │
     ├─ Projects (0..n)                          [EXTENDED — objective, location]
     │    ├─ own Budget (generalised, project-scoped)
     │    │    └─ BudgetLine → Expense
     │    ├─ Activities (Activity.project FK, NEW — optional)
     │    └─ Tasks (ProjectTask.activity FK, NEW — optional)
     │
     ├─ Activities not tied to a specific project (Activity.project = null)
     │    ├─ outputs            [NEW — M2M → monitoring_evaluation.Output]
     │    ├─ responsible_person [NEW — FK → User, nullable]
     │    ├─ budget_line        [NEW — FK → expenses.BudgetLine, nullable]
     │    ├─ location           [existing]
     │    ├─ AttendanceRecord (people reached)     [existing]
     │    └─ Document evidence (GFK)               [existing, wired up]
     │
     ├─ Beneficiaries / AttendanceRecord (programme-level people)
     ├─ own Budget (generalised, programme-scoped — overhead / shared costs
     │    not attributable to one project)
     ├─ Grant (funding, M2M — already exists)
     └─ Documents (evidence, GFK, category=programmes)
```

Every arrow in this diagram is either an existing FK (unchanged) or one of six new, nullable/optional fields:

| New field | On | Type | Purpose |
|---|---|---|---|
| `Activity.project` | `programmes.Activity` | FK, nullable | Activity can sit inside a specific project |
| `Activity.outputs` | `programmes.Activity` | M2M → `monitoring_evaluation.Output` | "What will this activity produce" |
| `Activity.responsible_person` | `programmes.Activity` | FK → User, nullable | "Who delivers it" — simple, no staffing subsystem |
| `Activity.budget_line` | `programmes.Activity` | FK → `expenses.BudgetLine`, nullable | "What does it cost" at the activity level |
| `ProjectTask.activity` | `projects.ProjectTask` | FK, nullable | Task can be scoped to one activity within its project |
| `Project.objective`, `Project.location` | `projects.Project` | text/char, blank | Service-specification-level detail for Part C granularity |

Plus the Programme extension (§4 in v1, unchanged: `start_date`, `end_date`, `need_and_background`, `implementation_plan`, `staffing_plan`, `previous_experience`, `monitoring_plan`, `funding_request_notes`, `wizard_step`) and the Budget generalisation (§9 below).

**No new models.** Six new fields/relations on existing models, all additive.

---

## 3. Programme Wizard

Unchanged mechanism from v1 (reuse the Organisation onboarding `onboarding_step`-style dispatcher — proven, tested pattern already in `apps/organisations`). Step content, updated for the new links:

| # | Step | Backs onto |
|---|---|---|
| 1 | Programme details | `Programme.name`, `programme_area`, `status` |
| 2 | Need / background / purpose | `Programme.description`, `need_and_background`, `theory_of_change_summary` |
| 3 | Beneficiaries | `Programme.target_beneficiary_groups` (existing JSON, now exposed) |
| 4 | Geographic coverage | `Programme.locations` (existing JSON, now exposed) |
| 5 | Programme period | `Programme.start_date`, `end_date` (new) |
| 6 | Outcomes | `monitoring_evaluation.Outcome` rows (reuses `OutcomeForm`) |
| 7 | Outputs | `monitoring_evaluation.Output` rows (reuses `OutputForm`) — **added as its own explicit step**, since Activities now link to Outputs directly and the wizard should ask "what will this programme produce" before asking about activities |
| 8 | Indicators and targets | `monitoring_evaluation.Indicator` rows (reuses `IndicatorForm`) |
| 9 | Projects | `projects.Project` row(s), `programme` pre-set (reuses `ProjectForm` + new `objective`/`location` fields) — optional |
| 10 | Activities | `programmes.Activity` row(s) (reuses `ActivityForm`), each optionally linked to a Project, one or more Outputs, a responsible person, and a budget line if one already exists — optional |
| 11 | Staffing/resources | `Programme.staffing_plan` (narrative) + optionally assigning `responsible_person` on the activities just created — no new step-specific model |
| 12 | Budget | Programme-level `Budget`/`BudgetLine` (generalised model, §9); if Projects were created in step 9, their own budgets are set from each Project's own workspace, not force-fed through this step (keeps this step from becoming an unbounded multi-project budget form) |
| 13 | Funding | Attach `Grant` records via `Programme.grants` M2M (reuses existing queryset restriction) |
| 14 | Review and create | Read-only summary; submit sets `status` and a `wizard_step` completion sentinel |

(Numbering shifted to 14 steps because Outputs is now split out as its own step — still the same 13 concerns from your original list, Outcomes/Outputs just separated to match the Output→Indicator/Activity linking this round introduced.)

Every step after #1 remains skippable/resumable, same as the Organisation wizard.

---

## 4. Programme Workspace

Unchanged shape from v1 §9 (breadcrumb → summary bar → tabs `Overview | Plan | Projects | Activities | People | M&E | Finance | Evidence | Reports`, replacing `programme_detail.html`'s inline Activity form), with the Overview tab's Activities table now able to show each activity's linked Output(s) and responsible person inline, and the Finance tab showing the programme's own Budget plus a rollup across child Projects' Budgets (§9). No structural change beyond what's needed to surface the three new Activity relationships.

---

## 5. Project Workspace

Unchanged shape from v1 §10 (`Overview | Activities | Tasks | People | Budget | Expenses | Evidence | Reports`). Overview tab gains `objective` and `location` (new fields) so a Project can stand alone as a clean, exportable "service specification" per the Part C reading above — this is the concrete reason those two fields were promoted from "flagged for completeness" in v1 to formally approved additions in this revision.

---

## 6. Activity/Task Relationship

This is the section that changed most this round.

- `Activity` belongs to exactly one `Programme` (required, unchanged) and optionally one `Project` (`Activity.project`, nullable).
- `Activity` optionally links to one or more `Output`s (`Activity.outputs`, M2M) — this is the "what will it produce" connection. Indicators are then reached transitively (`Output.indicators`, already exists), so "how do we measure it" doesn't need a second direct link from Activity.
- `Activity` optionally has one `responsible_person` (FK → `User`, nullable) — "who delivers it." Deliberately a single FK, not a roles/assignment model: mirrors the existing `ProjectTask.assignee` and `Grant.responsible_manager` pattern already used elsewhere in this codebase, so no new concept is introduced.
- `Activity` optionally links to one `budget_line` (FK → `expenses.BudgetLine`, nullable) — "what does it cost," at whatever granularity the organisation actually tracks (many small activities won't need line-item costing and can leave this blank; the Programme/Project-level Budget totals still work regardless).
- `Activity.location` (existing field) already answers "area of operation" per-activity; no change needed there.
- `Task` (`ProjectTask`) stays required-to-Project (a task is always project work) and gains an optional `activity` FK so a task can be scoped to the specific activity it supports, without forcing every task to have one (some project tasks — e.g. "sign the funding agreement" — aren't tied to any single activity).

This closes the DSD "connected" requirement using only new nullable fields on the two models that already exist for this purpose — no new join table beyond the one M2M (`Activity.outputs`, which Django implements as a plain through-table, not a new concept to maintain).

---

## 7. People/Attendance Relationship

Unchanged from today, because it already works: `Beneficiary.programme` (required) and `AttendanceRecord.programme` (required) + `AttendanceRecord.activity` (optional). The Programme Workspace's People tab is `beneficiaries.beneficiary_list` filtered to `?programme=<id>` (already supported); the Activities tab can show attendance/reach per activity via `AttendanceRecord.activity`. One small addition: `attendance_list`'s view gains a `?programme=` filter (matching the pattern `beneficiary_list` already has) so the Programme Workspace's People tab can show attendance records, not just beneficiary records, scoped to the programme.

---

## 8. M&E Relationship

Unchanged from today's already-good design: `Outcome → Output → Indicator → IndicatorPeriodValue`, all programme-scoped. The only change is the new `Activity.outputs` link (§6), which lets the M&E tab (reusing `monitoring_evaluation.programme_me` near-verbatim, per v1 §4) additionally show, per Output, which activities are meant to deliver it — a small "contributing activities" list, computed from the reverse of the new M2M, not a new query concept.

---

## 9. Budget/Funding Relationship

**Budget generalisation** (as approved): `expenses.Budget.project` becomes nullable; `expenses.Budget.programme` is added, nullable; a `clean()`/`CheckConstraint` enforces exactly one of the two is set. This directly satisfies the DSD rule you quoted — "the budget must be specific to the particular service/programme/project being funded, rather than mixing unrelated programmes and projects" — because each `Budget` row is still scoped to exactly one Programme or exactly one Project, never both, never neither, and `Expense.project` stays required, so expenditure is always traceable to one specific funded thing. A Programme's "total budget vs actual" view is a rollup (its own `Budget` + each child `Project`'s `Budget`), but the underlying data never mixes two different funded services' money into one record.

**Funding**: `grants.Grant` is unchanged and already does this job — `Programme.grants` (M2M, a programme can draw on multiple grants) and `Project.grant` (FK, a project is normally funded by one specific grant/agreement, which is exactly the DSD "one Part C, one funding request" shape). No model change.

---

## 10. Evidence Relationship

Unchanged from v1: no new model. `documents.Document` already has `category=CATEGORY_PROGRAMMES` and a working generic FK (`content_type`/`object_id`/`related_object`). The Evidence tab on both the Programme and Project workspaces uploads/lists `Document`s with `related_object` pointing at the Programme, Project, or (new, since Activity is now a richer object) Activity instance. Existing visibility rules (`_can_view_document`) and versioning are reused unchanged.

---

## 11. Reporting Relationship

Unchanged from v1: no new model. New programme-scoped and project-scoped view functions in `apps/reporting`, reusing the existing csv/reportlab generation code, filtered querysets. Because of the Part C reading above, the **Project-level export is the one that should most closely match a DSD Part C shape** (one service, one budget, one set of activities/outputs) — the Programme-level export is the umbrella "everything under this programme" report. Both read the same underlying data; neither is a separate source of truth.

---

## 12. Migration/Cutover Strategy

**Migrations** (all additive, same as v1 §7, updated field list):

1. `programmes`: add `Programme.start_date`, `end_date`, `need_and_background`, `implementation_plan`, `staffing_plan`, `previous_experience`, `monitoring_plan`, `funding_request_notes`, `wizard_step`; add `Activity.project` (nullable FK), `Activity.outputs` (M2M), `Activity.responsible_person` (nullable FK), `Activity.budget_line` (nullable FK).
2. `projects`: add `Project.objective`, `Project.location`; add `ProjectTask.activity` (nullable FK).
3. `expenses`: relax `Budget.project` to nullable, add `Budget.programme` (nullable FK) + exactly-one-set constraint.
4. No model changes to `beneficiaries`, `monitoring_evaluation`, `grants`, `documents`; `attendance` gets one new view-level query filter, no model change.
5. Every migration is `ADD COLUMN` or `ALTER COLUMN ... DROP NOT NULL` — no data backfill, no destructive step. Run `manage.py check` and the full test suite after each app's migration in sequence (programmes → projects → expenses) to isolate any regression immediately.

**Cutover** (how the new UI replaces the old, without breaking existing links):

- `programmes:detail` keeps its exact URL shape (`<slug>/<programme_id>/`) — only the template/view content changes, so nothing that links to a programme elsewhere in the app (dashboard, tabs, breadcrumbs) needs to change.
- The inline "Add Activity" form currently on that page moves to a dedicated `programmes:create_activity` sub-page (same lightweight pattern as `attendance:record`/`beneficiaries:create`), reachable from the new Activities tab.
- `monitoring_evaluation:programme_me` and `monitoring_evaluation:indicator_detail` keep working as standalone URLs (not deleted) — the Programme Workspace's M&E tab embeds the same template content, so a direct link to `programme_me` from anywhere else in the app (or a bookmark) still resolves correctly; it just also becomes reachable via the tab.
- `expenses:project_expenses` similarly stays a live URL; the Project Workspace's Finance/Expenses tab embeds it rather than replacing it.
- No existing URL is removed in this phase. Everything becomes reachable two ways (direct URL + workspace tab) rather than one way — the safer cutover, since it can't break an existing bookmark or an existing test that hits the old URL directly.

---

## 13. Test Strategy

Unchanged in shape from v1 §11 (this app surface has near-zero coverage today, so this rebuild is also the first real safety net), updated for the new relationships:

1. **Migration correctness** — `manage.py check` clean; an existing `Budget`/`Activity`/`ProjectTask` row created before migration still round-trips with new fields blank/null.
2. **Model-level tests**: `Budget` exactly-one-of-{programme,project} constraint (both set → error, neither set → error, exactly one → valid); an `Activity` with both `programme` and `project` set is queryable and consistent from both directions.
3. **Chain-of-connection tests** (new this round): an `Activity` linked to an `Output` correctly surfaces on that Output's "contributing activities"; an `Activity.budget_line` total is included in its parent Budget's rollup; an `Activity.responsible_person` who isn't an organisation member is rejected by form validation (mirrors the existing `ProjectTask.assignee` queryset restriction).
4. **Wizard tests**: create a programme through every step, assert `wizard_step` advances and resumes correctly, assert the final review step is idempotent.
5. **Workspace tests** (Programme and Project): each tab 200s for a permitted user / 403s for an unpermitted one (reusing existing capability names — `programmes.manage`, `me.view`, `projects.manage`, `attendance.view`, `documents.view`, etc.); Overview tab's "budget vs actual" and "people reached" figures match real database aggregates.
6. **Evidence/Document GFK tests**: evidence uploaded against a Programme/Project/Activity sets `content_type`/`object_id` correctly; existing visibility rules still apply unchanged.
7. **Reporting tests**: programme-scoped and project-scoped exports return only rows belonging to that programme/project (tenant-isolation-style, matching `apps.organisations.tests.TenantIsolationTests`).
8. **Regression run**: full existing suite (currently 102 tests) stays green throughout, since every change is additive.

Build order, matching your stated priority: Programme (model extension) → Project (objective/location) → Activity (project/outputs/responsible_person/budget_line links + task link) → People/Evidence → M&E (tab embedding) → Finance (Budget generalisation) → Reporting. Each stage fully tested before the next starts.

---

## Confirmed out of scope this round

Person/Beneficiary migration, Case Management, Android, Kiosk mode, Constitution/Learning modules, and any rebuild of already-working engines (M&E scoring, Finance approval workflow, Attendance capture, Document versioning) — all untouched. This is IA/connection work over the existing engines, not a rebuild of them.

Nothing will be built until you review this and say go.
