# Stakeholder Readiness — Technical Assessment (Step 1)

Per the implementation prompt's own Step 1 ("Inspect... provide a short technical
assessment... do not modify anything yet"), this document is pure inspection —
no code has changed as part of writing it. It's the checkpoint before Step 2
(P0 fixes), which follows immediately after this document in the same pass
since it's a single, well-understood, low-risk bug. Everything from Step 3
onward (Governance + EDMS, dashboard/admin redesign, Opportunities/Tenders)
involves real schema and UX decisions and is intentionally **not** started
here — see §9.

---

## 1. P0 — Organisation/Network logo upload HTTP 500 (CONFIRMED, root cause found)

**Root cause:** `config/settings.py` defines `STORAGES` with only a
`"staticfiles"` key — there is no `"default"` entry, and Django does not merge
a project's `STORAGES` dict with its own built-in default (setting it replaces
the whole dict). Any `FileField`/`ImageField` that doesn't pass an explicit
`storage=` kwarg resolves through `django.core.files.storage.default_storage`,
which looks up the `"default"` alias in `STORAGES` the first time it's
actually used (i.e. the first time a file is saved). That lookup fails.

Reproduced directly (not just inferred) by forcing storage resolution in a
Django shell:

```
django.core.files.storage.handler.InvalidStorageError:
Could not find config for 'default' in settings.STORAGES.
```

This is why the bug matches exactly what was reported: saving an organisation
**without** a logo never touches storage (nothing to write) and works fine;
attaching a logo file triggers `ImageField.pre_save() → storage.save()` and
crashes with an uncaught `ImproperlyConfigured` subclass, which nothing in
the view/form stack catches, so it surfaces as a raw HTTP 500.

**Blast radius — every model field relying on implicit default storage:**

| Field | File | Affected? |
|---|---|---|
| `Organisation.public_logo` | `apps/organisations/models.py:110` | Yes — the reported bug |
| `Network.logo` | `apps/networks/models.py:22` | Yes — same bug, not yet reported but will 500 identically |
| `Document.file` | `apps/documents/models.py` | No — explicit `storage=private_storage` |
| `Expense.receipt` | `apps/expenses/models.py:65` | No — explicit `storage=private_storage` |

**Why untested:** grepped `apps/organisations/tests.py` and `apps/networks/tests.py`
— neither has any test that submits a file through `public_logo` or `Network.logo`.
No test in the suite exercises `default_storage` at all, which is exactly why this
has been latent.

**Fix direction (applying next, in this same pass):** add a `"default"` entry to
`STORAGES` pointing at `django.core.files.storage.FileSystemStorage` (matching the
existing `MEDIA_ROOT`), plus tests covering both `Organisation.public_logo` and
`Network.logo` upload end-to-end (valid PNG, oversized file, disallowed extension,
missing file).

---

## 2. Governance — current state vs. brief

**Models** (`apps/governance/models.py`): `GovernanceOfficial`, `GovernanceMeeting`,
`MeetingAttendance`, `Resolution`, `ConflictOfInterestDeclaration`.

| Brief wants (§11–15) | Current state |
|---|---|
| Officials keep history, never deleted | ✅ Already true — resignation flips `status`, row is preserved |
| Resignation captures date + note + **supporting document** | ⚠️ Partial — `GovernanceOfficialResignForm` captures `resignation_note` and `term_end` (reused as the resignation date) but has **no document upload field at all**. No resignation letter/evidence is ever attached. |
| Meetings have one clear minutes relationship, upload-or-select-from-vault | ⚠️ **Broken/unfinished** — `GovernanceMeeting.minutes_document` is a real FK to `documents.Document`, but `GovernanceMeetingForm` doesn't expose it and there is no view/endpoint that ever sets it. `meeting_detail.html` literally tells the user *"Upload minutes from the Document Vault and link them here"* — but that link-up action doesn't exist anywhere. This is a dead end today, not a working feature. |
| Resolutions: structured fields **and** an uploadable resolution document | ❌ `Resolution` has only `text` + `decision` (approved/rejected/deferred) + `meeting` FK. No document field, no reference number field, no `created_by`. |
| Compact meeting table with Minutes/Resolutions columns | Templates exist (`list.html`, `meeting_detail.html`) but weren't restyled for this pass — functionally present, not yet at the target information density. |

**Tests:** `apps/governance/tests.py` is a stub — zero coverage for resignation,
meetings, or resolutions today.

---

## 3. Documents / EDMS — current state vs. brief

**Model** (`apps/documents/models.py::Document`): `organisation`, `title`, `file`
(private storage), `file_size`, `visibility` (private/organisation/public),
`uploaded_by`, plus a `GenericForeignKey` (`content_type`/`object_id`).

| Brief wants (§16–21) | Current state |
|---|---|
| Central repository other apps link into, not per-app document silos | ⚠️ Half true. The GFK exists on `Document` but **nothing in the codebase actually uses it** — grepped every `Document.objects.create(...)` call and every `content_type=`/`ContentType.objects.get_for_model` usage; `apps.policies` and `apps.governance` (`ConflictOfInterestDeclaration.document`) both link to `Document` via a **dedicated FK on the other model** instead, bypassing the GFK entirely. The GFK is dormant, unused scaffolding today, not a proven pattern. |
| Document categories (Organisation/Governance/Compliance/Programmes/Finance/Partnerships/Other) | ❌ No `category` field at all — the model is completely flat. |
| Basic versioning | ❌ Not on `Document` itself. The only versioning that exists is `apps.policies.PolicyVersion` (its own `version_number` + a plain FK to one `Document` row per version) — `Document` has no idea it's "version 2 of X"; that concept lives entirely inside the Policies app, not centrally. |
| Visibility enforced everywhere a document is served | ⚠️ Partial — `download_document` correctly checks org membership + `documents.view` capability + confirms the document belongs to the requesting org (verified by an existing IDOR regression test), which prevents cross-*organisation* leaks. It does **not** additionally gate on the `visibility` field itself — a `private`-visibility document and an `organisation`-visibility document are downloadable by the same org members today; `visibility` appears to only be read by the public-facing profile/directory layer, not enforced in the download view. |
| Archive rather than hard-delete | Not yet implemented — no `is_archived`/status field on `Document`. |

---

## 4. Admin / staff portal — current state vs. brief

**There is no platform-wide admin workspace beyond Django's built-in `/admin/`.**
Confirmed by directory search (no `*staff*`/`*platform*`/`*admin*` templates
anywhere) and by reading `apps/core/views.py` (health-check endpoint only).

What exists instead:
- **Network-scoped** dashboards (`apps/networks/views.py` — `dashboard`,
  `capacity`, and their `_for_network` variants) — one network at a time, no
  aggregate "all organisations"/"all networks" view.
- `User.is_platform_admin` (boolean) is the **only** platform-level role —
  confirmed by reading `apps/accounts/models.py` in full. There is no
  "Platform Staff" (limited, assigned-content) tier the brief asks for in §26–27
  — today it's binary: full platform admin, or nothing.
- No "organisations awaiting verification" queue, no "submissions queue" —
  neither concept exists in code (grepped for both).

This is the largest gap between the brief and the current app: §26–38
(staff dashboard, admin nav, opportunities/tenders/submissions management,
platform document area, five-tier permissions) describes a workspace that
doesn't exist yet in any form, not one that needs restyling.

---

## 5. Opportunities / Tenders / Submissions — current state vs. brief

**Model** (`apps/opportunities/models.py::Opportunity`): one model, network-scoped
(not organisation-scoped), `opportunity_type` choices already include
`funding/training/grant/tender/partnership/event/capacity`, `status`
(draft/published/closed).

| Brief wants (§29–32) | Current state |
|---|---|
| Staff can create/edit/preview/publish/unpublish/archive | ⚠️ Partial — **create** exists (`create_opportunity`/`_for_network`, capability-gated), but there is **no edit view/URL at all**, no publish/unpublish toggle, no archive. `status` is only ever set at creation time. |
| Dedicated Tender model/workflow | ❌ Doesn't exist — `tender` is just one value of `opportunity_type` on the shared `Opportunity` model; the brief explicitly asks these stay distinct content types even if they share infrastructure. |
| Community-submitted opportunities, staff-reviewed before publish | ❌ No `submitted_by` field, no distinct review status, no submission entry point anywhere in the app. Opportunities can only be created by staff already holding `network.opportunities.manage`. |
| Admin table with filters (type/status/closing/province/sector) | `manage_list`/`manage_list_for_network` exist and list all statuses for a network, but without the filter UI the brief describes. |

**Tests:** `apps/opportunities/tests.py` is a stub.

---

## 6. Resources / Events / Insights — current state vs. brief

**None of these exist as Django apps.** Confirmed against the full `apps/`
listing and `INSTALLED_APPS` — there is no `apps.resources`, `apps.events`, or
`apps.insights`. What exists today:

- `templates/sitepublic/resources.html` — a static page with a placeholder
  banner ("Placeholder: populate with real guides...") and three hand-written
  cards. No model, no admin management, no way to add a fourth resource
  without editing the template.
- `templates/sitepublic/insights.html` — an empty-state page, no model.
- **No Events page exists at all** — no template, no URL. The `event` value
  on `Opportunity.opportunity_type` is the closest thing, surfaced only
  through the general opportunities public list filtered by type.

Everything in §33–35 (staff-manageable Resources/Events/Insights with
draft/published/archived workflows) needs building from nothing, not editing.

---

## 7. Permissions — current state vs. brief

Two independent, already-working scopes exist in `apps/core/permissions.py`:
organisation-scoped (`OrganisationMembership.role` → 10 roles, e.g.
`org_admin`, `executive_director`, `board_member`, `treasurer`, `staff`) and
network-scoped (`NetworkStaffRole.role` → `network_admin`,
`membership_officer`), both capability-based (named capabilities like
`"documents.manage"`, never bare `if role ==` checks), with `is_platform_admin`
as the single documented escape hatch across both scopes.

The brief's five-tier model (§38: Platform Administrator / **Platform Staff**
/ Organisation Administrator / Organisation Staff / Public Visitor) maps
cleanly onto Organisation Admin/Staff (already exist) and Public (already
exists via anonymous access to `sitepublic`/public opportunity views), but
**"Platform Staff" — someone who can manage assigned platform content without
full platform-admin rights — doesn't exist as a concept anywhere.** This gap
is exactly what blocks §26–27 (a real staff/admin portal): there's currently
no way to grant someone "manage opportunities" without also handing them
every other `is_platform_admin` capability.

---

## 8. Organisation dashboard & navigation — current state vs. brief

**Dashboard** (`templates/organisations/workspace_home.html`): 4 metric cards
(Overall Readiness / Open Compliance Items / Active Programmes / Active
Projects) + 4 generic navigation cards (Organisation Health / Compliance
Passport / Impact Dashboard / Membership). No "Needs Your Attention", no
"Upcoming", no "Recent Activity" feed, no "Quick Actions". This confirms the
brief's diagnosis — it is a small wall of cards today, not the
task-oriented dashboard described in §5–10.

**Sidebar nav** (`templates/workspace_base.html`): a single flat list of 17
links across 6 section labels (Overview / Governance & Compliance /
Operations / Evidence / Impact / Administration) — confirms the brief's
"long list of features" diagnosis. The brief's 8-area IA (Dashboard /
Organisation / Governance / Compliance / Programmes & Impact / Documents /
Opportunities / Community) doesn't exist yet; today's nav has no grouping
above the section-label level and no sub-navigation/tabs within an area.

---

## 9. Recommended path forward

Proceeding in this same pass:

- **Step 2 (now):** Fix the `STORAGES` bug (one settings change), add
  regression tests for both affected fields, run the full suite, commit.
  Low-risk, unambiguous, no design decisions involved.

**Then stopping to check in before Step 3**, because — unlike Step 2 — it
involves real design decisions this session has consistently paused for
before implementing (matching how `PERSON_CASE_DESIGN_PROPOSAL.md` and the
Black Sash network work were handled earlier):

- Whether Document versioning becomes a first-class field on `Document`
  itself (so Governance/Compliance/Programmes can all reuse it) versus
  staying a Policies-only pattern.
- Whether to finally activate the dormant GenericForeignKey for
  cross-app document linking (resignation evidence, resolution documents,
  meeting minutes) or keep using dedicated FKs per relationship (the
  proven, currently-working pattern) — these have different tradeoffs
  worth a short proposal rather than a silent pick.
- The shape of the new "Platform Staff" permission tier, since it's a new
  concept with no existing precedent to extend.
- App boundaries for the net-new admin/staff portal and for
  Resources/Events/Insights/Tenders/Submissions (separate apps vs.
  extending existing ones) — mirrors the same question already raised
  and deferred in `PERSON_CASE_DESIGN_PROPOSAL.md`.

Steps 4 (Organisation UX/dashboard redesign) and 5 (Admin UX) depend on the
Step 3 decisions above (dashboard's "Needs Attention" section reads directly
from resignation/document/compliance state; the admin portal needs the
Platform Staff tier to exist first), so they naturally follow rather than
run in parallel.
