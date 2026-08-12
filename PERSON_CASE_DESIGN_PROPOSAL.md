# Person / Case Management — Design Proposal

**Status: proposal only. Nothing in this document has been implemented.**
Per instruction, no model, migration, view, or template changes have been made
alongside this document — it exists purely for review before any
implementation begins.

This proposes the target data model for `Person`, `Programme Participation`,
`Case`, `Referral`, `Activity`, `Monitoring`, `Outcome` and `Evidence`, and how
the existing `Beneficiary`/`AttendanceRecord` data and every call site that
touches them today migrates onto it without breaking current functionality.

---

## 0. Terminology collision (read this first)

The codebase already uses "Programme" for something unrelated to what the
Bohlale Impact brief calls "Programme/Network":

| Term in this doc | Existing code | Meaning |
|---|---|---|
| **Network** (aka "programme" in the Black Sash sense) | `apps.networks.Network` | A platform deployment / partner initiative with its own staff, membership applications, and authorization scope — e.g. Bohlale Impact itself, or a partner like Black Sash. |
| **Programme** | `apps.programmes.Programme` | An organisation's *internal* service-delivery unit (spec section 23) — e.g. "Youth Skills Programme" run by one NPO. Unrelated to Network. |

Both words appear below. Every use of **Network** means `apps.networks.Network`
(the Black Sash-style entity); every use of **Programme** means
`apps.programmes.Programme` (an org's own internal programme). This
distinction is the crux of the placement question raised in the brief, so §5
below answers it explicitly for each new model.

---

## 1. Current state (from inspection)

- `Beneficiary` (`apps.beneficiaries.models.Beneficiary`): org-scoped, with a
  **required, single** `programme` FK. Carries `mode`
  (`named`/`attendance_participant`) but `mode` is write-only — grepped across
  the whole codebase, it drives no branching logic anywhere except its own
  definition and `seed_demo_data.py`. True anonymity is represented today by
  *not* creating a `Beneficiary` row at all and using `AttendanceRecord.headcount`
  instead.
- `AttendanceRecord.beneficiary` is a nullable FK to `Beneficiary`;
  `effective_count` is `1` if `beneficiary_id` else `headcount`.
- Only two views exist for beneficiaries: `beneficiary_list`, `create_beneficiary`
  (no update/delete/detail view). `BeneficiaryForm` scopes the programme
  queryset to the org.
- `Beneficiary.is_sensitive` exists on the model, form, admin list display and
  template badge, but **is not enforced by any permission check** — grepped
  `apps/core/permissions.py` and every view; only the coarse
  `beneficiaries.view` / `beneficiaries.manage` org capabilities gate access
  today (held by Admin, Executive Director, Project Manager, M&E Officer;
  Staff gets view-only).
- `programme.beneficiaries.count()` is used on the programme detail page.
- `apps/impact/views.py` computes `named_reached` as
  `attendance.filter(beneficiary__isnull=False).values("beneficiary").distinct().count()`.
  Because `Beneficiary` rows are programme-scoped, **a real person recorded
  under two programmes is counted twice today**, with no way to detect it —
  this is a real bug the new model fixes as a side effect (§5).
- `apps.monitoring_evaluation` (`Outcome`, `Output`, `Indicator`,
  `IndicatorPeriodValue`) is entirely `Programme`-scoped and never touches
  `Beneficiary` directly; `Indicator.auto_from_attendance` aggregates from
  `AttendanceRecord`, not from beneficiaries.
- `apps.reporting`'s CSV export includes the beneficiary name or blank per
  attendance row.
- `apps.documents.Document` already has a working generic evidence-attachment
  mechanism (`content_type`/`object_id`/`GenericForeignKey`), usable by any
  model without a bespoke join table. Separately, `apps.compliance` has its
  own dedicated `ComplianceEvidence` join model (`obligation` FK + `document`
  FK). These are two different patterns for the same problem — an existing
  inconsistency, not something to replicate a third time.
- `apps.compliance` also has the pattern this proposal reuses for `Case`:
  status field + append-only `*StatusEvent` model (`ComplianceObligation` /
  `ComplianceStatusEvent`), already used twice more (`MembershipApplication` /
  `MembershipStatusEvent`).
- **No test file references `Beneficiary` anywhere** — there is no existing
  test coverage to preserve compatibility with, only real call sites (listed
  above) to keep working.

---

## 2. Design principles carried over from the rest of the codebase

1. **Additive, not destructive migration.** Same pattern already used twice
   in this session (Network generalisation, uniqueness constraint): expand
   first, cut over reads/writes one call site at a time, contract only once
   nothing references the old path.
2. **Status + append-only event log** for anything with a review/decision
   workflow (`Case`), matching `ComplianceObligation`/`MembershipApplication`.
3. **Capability checks stay in `apps.core.permissions`**, org-scoped by
   default with a network-scoped variant (`has_network_capability`) only
   where a Network administrator legitimately needs visibility.
4. **No new generic evidence join table.** Reuse `Document`'s existing
   `GenericForeignKey` for `Case`/`MonitoringSubmission` evidence rather than
   inventing a `CaseEvidence` model — this also avoids deepening the
   Document-vs-ComplianceEvidence inconsistency already present.

---

## 3. Target models

### 3.1 `Person` (new app: `apps.people`)

Replaces `Beneficiary` as the org's record of an individual, but **without**
a required single programme — that relationship moves to
`ProgrammeParticipation` (§3.2).

```python
class Person(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey("organisations.Organisation", on_delete=models.CASCADE, related_name="people")

    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=30, blank=True)
    contact_number = models.CharField(max_length=32, blank=True)

    is_sensitive = models.BooleanField(default=False)
    consent_recorded = models.BooleanField(default=False)
    reference_code = models.CharField(max_length=40, blank=True)

    # Set only by the migration (§6), for provenance/rollback verification.
    # Removed in the contract phase once Beneficiary is retired.
    legacy_beneficiary = models.OneToOneField(
        "beneficiaries.Beneficiary", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
```

`mode` is dropped: a `Person` row's existence already means "named". Anonymous
headcounts continue exactly as today — no `Person` row, `AttendanceRecord.headcount`
only. This is an unconditional simplification, not a behaviour change.

### 3.2 `ProgrammeParticipation` (new, in `apps.people`)

Generalises `Beneficiary.programme` from a required single FK to
many-with-metadata, so one person can be enrolled in more than one of an
org's programmes at once — which real people already are, but the current
schema can't represent.

```python
class ProgrammeParticipation(TimeStampedModel):
    STATUS_ACTIVE = "active"
    STATUS_EXITED = "exited"
    STATUS_CHOICES = [(STATUS_ACTIVE, "Active"), (STATUS_EXITED, "Exited")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="participations")
    programme = models.ForeignKey("programmes.Programme", on_delete=models.CASCADE, related_name="participations")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    enrolled_at = models.DateField(null=True, blank=True)
    exited_at = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["person", "programme"], name="unique_participation_per_person_programme")
        ]
```

### 3.3 `Case` (new app: `apps.cases`)

The core Case Management entity. **Network-aware from day one** — this is
what actually needs `network` on it (§5).

```python
class Case(TimeStampedModel):
    STATUS_OPEN = "open"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_PENDING = "pending"
    STATUS_REFERRED = "referred"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"), (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_PENDING, "Pending"), (STATUS_REFERRED, "Referred"), (STATUS_CLOSED, "Closed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey("organisations.Organisation", on_delete=models.CASCADE, related_name="cases")
    person = models.ForeignKey("people.Person", on_delete=models.CASCADE, related_name="cases")
    network = models.ForeignKey("networks.Network", on_delete=models.SET_NULL, null=True, blank=True, related_name="cases")
    programme = models.ForeignKey("programmes.Programme", on_delete=models.SET_NULL, null=True, blank=True, related_name="cases")

    reference_code = models.CharField(max_length=40, blank=True)
    category = models.CharField(max_length=100, blank=True)
    summary = models.TextField(blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_OPEN)
    is_sensitive = models.BooleanField(default=False)

    opened_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_cases")
    closed_at = models.DateTimeField(null=True, blank=True)
    outcome_category = models.CharField(max_length=100, blank=True)
    outcome_notes = models.TextField(blank=True)


class CaseStatusEvent(models.Model):
    """Same append-only pattern as ComplianceStatusEvent / MembershipStatusEvent."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="status_events")
    status = models.CharField(max_length=15, choices=Case.STATUS_CHOICES)
    note = models.TextField(blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
```

`outcome_category`/`outcome_notes` live directly on `Case` rather than as a
separate `Outcome` model — see §3.6 on why "Outcome" in this list maps to the
*existing* M&E `Outcome`, not a new case-outcome model.

### 3.4 `Referral` (in `apps.cases`)

```python
class Referral(TimeStampedModel):
    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_DECLINED = "declined"
    STATUS_COMPLETED = "completed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"), (STATUS_ACCEPTED, "Accepted"),
        (STATUS_DECLINED, "Declined"), (STATUS_COMPLETED, "Completed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="referrals")
    # One of these two is set, never both — enforced in the form layer,
    # same convention as AttendanceRecord.beneficiary vs .headcount.
    referred_to_organisation = models.ForeignKey(
        "organisations.Organisation", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    referred_to_text = models.CharField(max_length=255, blank=True, help_text="Off-platform destination, e.g. a government department")
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    resolved_at = models.DateTimeField(null=True, blank=True)
```

### 3.5 `Activity` — reinterpreted as **case activity**, not `apps.programmes.Activity`

The brief lists `Activity` alongside `Case`/`Referral`/`Monitoring` — in a
case-management domain model that's almost always the interaction/action log
against a case (calls, meetings, notes, tasks), not the existing
`apps.programmes.Activity` (a scheduled programme session that attendance is
recorded against). **Flagging this explicitly for confirmation** rather than
guessing silently, since the two are easy to conflate by name alone.
`apps.programmes.Activity` is left completely untouched either way — nothing
here proposes changing it.

```python
class CaseActivity(TimeStampedModel):
    TYPE_CALL = "call"
    TYPE_MEETING = "meeting"
    TYPE_NOTE = "note"
    TYPE_TASK = "task"
    TYPE_CHOICES = [(TYPE_CALL, "Call"), (TYPE_MEETING, "Meeting"), (TYPE_NOTE, "Note"), (TYPE_TASK, "Task")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="activities")
    activity_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TYPE_NOTE)
    description = models.TextField(blank=True)
    occurred_at = models.DateTimeField()
    logged_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
```

### 3.6 `Monitoring` — new `MonitoringSubmission` (new app: `apps.community_monitoring`)

This is the brief's "Community Monitoring" module (a Black-Sash-style
programme's field monitors submitting structured reports), not a generic
M&E concept.

```python
class MonitoringSubmission(TimeStampedModel):
    STATUS_DRAFT = "draft"
    STATUS_SUBMITTED = "submitted"
    STATUS_REVIEWED = "reviewed"
    STATUS_CHOICES = [(STATUS_DRAFT, "Draft"), (STATUS_SUBMITTED, "Submitted"), (STATUS_REVIEWED, "Reviewed")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    network = models.ForeignKey("networks.Network", on_delete=models.CASCADE, related_name="monitoring_submissions")
    organisation = models.ForeignKey("organisations.Organisation", on_delete=models.CASCADE, related_name="monitoring_submissions")
    case = models.ForeignKey("cases.Case", on_delete=models.SET_NULL, null=True, blank=True, related_name="monitoring_submissions")
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")

    title = models.CharField(max_length=255)
    category = models.CharField(max_length=100, blank=True)
    content = models.JSONField(default=dict, blank=True, help_text="Structured form responses")
    location = models.CharField(max_length=255, blank=True)
    occurred_at = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_DRAFT)
```

`network` is **required** here (unlike `Case.network`, which is nullable) —
a monitoring submission only exists in service of a specific programme's
monitoring framework; there's no "internal, no-network" monitoring submission
the way there's an org-internal case. When a submission is tied to a `case`,
`network` is copied from `case.network` at creation time rather than derived
dynamically, so the FK stays a simple required field and authorization checks
never need to join through `Case` to find it.

A `MonitoringForm` (template/schema for `content`) is deliberately **not**
proposed yet — `content` as a plain `JSONField` is enough to ship a first
working version; a form-builder is a natural but separate follow-on and would
be premature to design now.

### 3.7 `Outcome` — reuse `apps.monitoring_evaluation.Outcome` unchanged

No new model. `apps.monitoring_evaluation.Outcome`/`Output`/`Indicator`
already exist, are `Programme`-scoped, and are exactly what "Outcome" means
in an M&E sense. `Case.outcome_category`/`outcome_notes` (§3.3) cover the
case-level "what happened to this specific person's case" need, which is a
different concept from a programme-level M&E outcome and shouldn't be
forced into the same model.

### 3.8 `Evidence` — reuse `Document`'s existing generic relation

No new model. `Document.content_type`/`object_id` already lets any model
attach evidence without a bespoke join table — `Case`, `Referral`, and
`MonitoringSubmission` all use this as-is
(`Document.objects.filter(content_type=..., object_id=case.id)`). This also
means the design does **not** replicate `ComplianceEvidence`'s separate
dedicated-join-table pattern; that inconsistency is left as-is (out of scope
to retrofit `apps.compliance` here) but is not compounded further.

---

## 4. Summary table

| Brief's term | Proposal | New/reused |
|---|---|---|
| Person | `apps.people.Person` | New (replaces `Beneficiary`) |
| Programme Participation | `apps.people.ProgrammeParticipation` | New |
| Case | `apps.cases.Case` + `CaseStatusEvent` | New |
| Referral | `apps.cases.Referral` | New |
| Activity | `apps.cases.CaseActivity` | New — **confirm this interpretation**, see §3.5 |
| Monitoring | `apps.community_monitoring.MonitoringSubmission` | New |
| Outcome | `apps.monitoring_evaluation.Outcome` | Reused unchanged |
| Evidence | `apps.documents.Document` (generic FK) | Reused unchanged |

---

## 5. The network/programme placement question, answered directly

**Network belongs on `Case` (nullable) and `MonitoringSubmission` (required),
never on `Person` or `ProgrammeParticipation`.**

**`apps.programmes.Programme` belongs on `ProgrammeParticipation` (required)
and optionally `Case` (nullable), never required on `Person`.**

Reasoning:

- A `Person` is a human the organisation has on file. That fact is permanent
  and org-scoped — it doesn't depend on which programme or which partner
  network is currently engaging with them. Today's schema gets this wrong by
  forcing `Beneficiary.programme` to be a single required FK; that's exactly
  the bug in the impact dashboard's dedup logic (§1) and exactly what
  `ProgrammeParticipation` fixes by making it a proper many-relationship.
- **Network is an authorization/reporting boundary over an *engagement*, not
  a property of a person.** The same person can simultaneously be an active
  participant in the org's own internal Youth Skills `Programme` (no network
  involved at all) *and* have an open advice `Case` under the Black Sash
  `Network`'s remit. If `network` lived on `Person`, that person could only
  ever "belong" to one network at a time — which is both factually wrong and
  would make the Black Sash validation scenario's requirement #7 ("the org
  retains its own Bohlale Impact workspace" while also being a Black Sash
  partner) impossible to model correctly at the person level.
- This is also just consistent with the architecture already built this
  session: `NetworkStaffRole` and `MembershipApplication` both put `network`
  on the *engagement/join* record (a staff role, an application), never on
  `User` or `Organisation` directly, because a user or org can have
  independent relationships with multiple networks at once. `Case` and
  `MonitoringSubmission` are the person-level equivalent of that same join
  pattern.
- `apps.programmes.Programme`, by contrast, is purely an org-internal
  categorisation with no cross-org authorization implications — so it
  belongs on the direct participation join (`ProgrammeParticipation`),
  mirroring exactly what `Beneficiary.programme` already does today, just
  correctly pluralised. It's also useful, but optional, on `Case` (an
  org may want to say "this case was opened under our internal Legal
  Advice programme" independent of which network it also relates to).

Net effect: **no model needs both `network` and `programme` as required
fields at once** — `ProgrammeParticipation` only ever needs `programme`;
`MonitoringSubmission` only ever needs `network`; `Case` may have either,
neither, or both, all nullable except the FKs that are always known
(`organisation`, `person`).

---

## 6. Migration strategy (expand → cutover → contract)

No existing tests reference `Beneficiary` (confirmed by grep), so
compatibility is judged purely against the real call sites found during
inspection, listed explicitly below.

### Phase A — Expand (additive, zero behaviour change)

1. Add `apps.people` (`Person`, `ProgrammeParticipation`), `apps.cases`
   (`Case`, `CaseStatusEvent`, `Referral`, `CaseActivity`), and
   `apps.community_monitoring` (`MonitoringSubmission`) as new apps. Leave
   `apps.beneficiaries` and `apps.attendance` completely untouched at this
   stage.
2. Data migration: for every existing `Beneficiary` row, create one `Person`
   (copying `first_name`/`last_name`/`date_of_birth`/`gender`/`contact_number`/
   `is_sensitive`/`consent_recorded`/`reference_code`, dropping `mode`, setting
   `legacy_beneficiary`) and one `ProgrammeParticipation` linking it to that
   beneficiary's `programme` (`status=active`).
3. Nothing yet reads from `Person`. All current views/forms/templates keep
   using `Beneficiary` exactly as today. Fully backward compatible — this
   phase can ship and be verified (row-count parity: `Person.objects.count()
   == Beneficiary.objects.count()`, every `ProgrammeParticipation` traces back
   to a real `Beneficiary.programme`) before any call site changes.

### Phase B — Cut over call sites, one at a time

Each row below is one of the real usages found during inspection (§1) and its
replacement:

| Call site | Today | After |
|---|---|---|
| `apps.beneficiaries.views.beneficiary_list`/`create_beneficiary` | reads/writes `Beneficiary` | repointed to `Person` + `ProgrammeParticipation`, filtered by programme via the participation join |
| `BeneficiaryForm` | `ModelForm(Beneficiary)` | `PersonForm` capturing person fields + a programme select that creates/updates a `ProgrammeParticipation` |
| `AttendanceRecord.beneficiary` | FK to `Beneficiary`, nullable | add `AttendanceRecord.person` FK to `Person` (`AddField(null=True)` → backfill via `legacy_beneficiary` → both FKs coexist through this phase); `effective_count` switches to check `person_id` |
| `apps.programmes.views.programme_detail`: `programme.beneficiaries.count()` | `Beneficiary.programme` reverse FK | `programme.participations.filter(status="active").count()` |
| `apps.impact.views`: `named_reached` dedup | `.values("beneficiary").distinct().count()` (double-counts a person active in 2 programmes) | `.values("person").distinct().count()` — this is also the fix for the double-counting bug identified in §1 |
| `apps.monitoring_evaluation.services.attendance_count_for_period` | `beneficiary__isnull=False` | `person__isnull=False` |
| `apps.reporting` CSV export | beneficiary name per row | person name per row |
| `apps.core.management.commands.seed_demo_data` | creates `Beneficiary` rows | creates `Person` + `ProgrammeParticipation` rows |
| `apps.core.permissions`: `beneficiaries.view`/`beneficiaries.manage` | gate `Beneficiary` views | kept as-is (same capability keys, same role grants) but now gate `Person`/`ProgrammeParticipation` views instead — renaming the keys to `people.*` is a pure-cosmetic follow-up, not required for correctness, and deliberately deferred to minimise blast radius |

Each row in this table is an independent, revertible change — none require
the others to land first, so they can be sequenced and tested individually.

### Phase C — Contract (remove scaffolding, once nothing references the old path)

- Drop `AttendanceRecord.beneficiary` (old FK) and `Person.legacy_beneficiary`.
- Retire `apps.beneficiaries` entirely (model, admin, views, urls,
  migrations squashed or left as history — no live code references it).

Phase C should only happen after a full deploy cycle has confirmed Phase B
needs no rollback — there is no correctness reason to rush it.

---

## 7. New RBAC surface

- `cases.view` / `cases.manage` / `cases.assign` — org capabilities, same
  role grants as `beneficiaries.*` today (Admin, Executive Director, Project
  Manager, M&E Officer manage; Staff view-only), following the existing
  table in `apps/core/permissions.py`.
- `cases.view` gated additionally by `Case.is_sensitive`: a `cases.view_sensitive`
  capability, checked only when the flag is set — this is new enforcement,
  not present for `Beneficiary.is_sensitive` today (confirmed unenforced by
  inspection, §1). Flagging as a deliberate improvement, not a
  behaviour-preserving requirement, since there's no existing enforcement to
  preserve.
- `monitoring.submit` / `monitoring.review` — org capability for submission,
  plus network-scoped `has_network_capability(user, network, "network.monitoring.review")`
  for the programme/network administrator's review queue, mirroring the
  existing `network.opportunities.manage` pattern used by
  `apps.opportunities`.
- Network-scoped visibility into `Case`/`MonitoringSubmission` is opt-in per
  row (only where `network` is actually set) — an org's purely-internal cases
  (`network=None`) are never visible to any network administrator, only to
  the owning organisation.

---

## 8. Open questions for confirmation before implementation

1. **§3.5**: confirm "Activity" in the brief means a case interaction log
   (`CaseActivity`) rather than the existing `apps.programmes.Activity`.
2. **App boundaries**: proposed as three new apps (`apps.people`,
   `apps.cases`, `apps.community_monitoring`) rather than one large app —
   confirm this granularity is wanted, versus folding all of it into a
   single `apps.cases` app.
3. **Capability key renaming**: `beneficiaries.*` → `people.*` is proposed as
   optional/deferred (§6 Phase B) — confirm whether to rename now for
   clarity or truly defer it.
4. **`MonitoringForm`**: deliberately not designed yet (§3.6) — confirm
   `content = JSONField()` is an acceptable first cut versus needing a
   schema/form-builder from the start.

No implementation will begin until this proposal (or a corrected version of
it) is confirmed.
