# Data Model

All models use `TimeStampedModel` (`created_at`/`updated_at`) and most use UUID primary keys (`UUIDPrimaryKeyModel` or an explicit `UUIDField(primary_key=True)`) so externally-referenced IDs aren't enumerable. Full field-level detail is always authoritative in `apps/*/models.py` and the generated migrations — this document is the map, not a replacement for reading the code.

## accounts
- **User** (custom, `AUTH_USER_MODEL`) — email login (no username), `is_platform_admin` (platform-wide RBAC escape hatch, distinct from `is_superuser`), `is_kiosk_only`, `email_verified` + `email_verification_token`.

## organisations
- **Organisation** — the single master record (spec section 13). Identity fields (legal/trading name, type, founding date, financial year end, contact, address, province/municipality), legal structure, five **independent** nullable registration-status booleans (`dsd_registered`, `cipc_registered`, `sars_pbo_approved`, `section18a_approved`, `masters_office_registered`) each with a companion reference-number field, activity JSON fields (`sectors`, `programme_areas`, `beneficiary_groups`, `sensitive_service_areas`), `onboarding_step`, and public-profile visibility fields (`is_publicly_listed`, `public_verification_status`, `public_about`, `public_logo`, `public_show_impact`, `public_show_contact`).
- **OrganisationMembership** — `(organisation, user, role, is_active)`, unique per `(organisation, user)`. This is the tenant-isolation boundary.

## networks
- **Network** — a network/umbrella deployment (ANNET is the seeded anchor row).
- **NetworkStaffRole** — `(network, user, role)`, network-level RBAC.

## memberships
- **MembershipApplication** — `(organisation, status, submitted_at, decided_at, decided_by, motivation, internal_notes)`. `status="approved"` is the terminal Active Member state (`Organisation.is_annet_member` reads this).
- **MembershipStatusEvent** — append-only decision/status history.

## compliance
- **ComplianceRule** — configurable rule content: `authority`, `applicable_entity_types`, `required_registration_statuses` (JSON), `trigger_type`, `frequency`, `deadline_rule` (JSON), `evidence_requirements`, `responsible_role`, `official_source`, `last_verified_at`, `active`, `version`.
- **ComplianceObligation** — `(organisation, rule, status, due_date, responsible_user, submitted_at, submission_reference, notes)`. Status choices deliberately exclude "Compliant" (see spec section 14): Not Started / In Progress / Ready for Submission / Submitted / Evidence Recorded / Overdue / Not Applicable.
- **ComplianceEvidence** — links an `ComplianceObligation` to a `documents.Document`.
- **ComplianceStatusEvent** — append-only submission history.

## governance
- **GovernanceOfficial** — `(organisation, full_name, position, term_start, term_end, status)`. Resignation sets `status=resigned` — the row is never deleted (history preservation, spec section 18/20).
- **GovernanceMeeting**, **MeetingAttendance**, **Resolution**, **ConflictOfInterestDeclaration**.

## policies
- **Policy** — `(organisation, name, category, owner, approval_authority, status, approval_date, next_review_date)`.
- **PolicyVersion** — `(policy, version_number, document, approved_date)`. Old versions are never deleted.

## documents
- **Document** — `(organisation, title, file [private_storage], visibility, uploaded_by, content_type/object_id generic FK)`. The generic FK lets a document attach to any other record (compliance obligation, meeting, policy, grant, project, expense) without every app needing its own file field.

## grants
- **Grant** — `(organisation, funder_name, name, amount, currency, funding_start/end, reporting_requirements, restrictions, responsible_manager, status)`. Status lifecycle: opportunity → application → awarded → agreement → active → reporting → closeout → closed.

## programmes
- **Programme** — `(organisation, name, programme_area, locations/services/target_beneficiary_groups [JSON], theory_of_change_summary, status, grants [M2M])`.
- **Activity** — `(programme, name, scheduled_date, location, status)` — the unit attendance is captured against.

## projects
- **Project** — `(organisation, grant [nullable FK], programme [nullable FK], name, manager, start/end, budget, status)`.
- **ProjectTask** — `(project, title, assignee, due_date, is_milestone, status)`.

## beneficiaries
- **Beneficiary** — `(organisation, programme, mode)`. `mode` is `named` or `attendance_participant`; anonymous headcounts are **not** a `Beneficiary` row at all (see `attendance.AttendanceRecord.headcount`) — data minimisation is structural, not just a UI convention. No mandatory ID-number/address fields. `is_sensitive` flags enhanced access needs.

## attendance
- **AttendanceRecord** — `(organisation, programme, activity, beneficiary [nullable], headcount, attendance_date, check_in_method)`. `effective_count` property: 1 for a named beneficiary row, else `headcount`.
- **KioskSession** — `(organisation, programme, token [UUID], expires_at, is_active)`. The public, unauthenticated kiosk check-in flow (`attendance:kiosk_entry`) resolves entirely off this token and never exposes anything beyond the linked programme's name.

## monitoring_evaluation
- **Outcome**, **Output** — `(programme, title, description)`, `Output.outcome` optional link.
- **Indicator** — `(programme, outcome, output, indicator_type, unit, baseline_value, target_value, auto_from_attendance)`. When `auto_from_attendance=True`, recording a period value computes `actual_value` from `AttendanceRecord` totals for that programme/period instead of manual entry (`apps.monitoring_evaluation.services.attendance_count_for_period`).
- **IndicatorPeriodValue** — `(indicator, period_start, period_end, actual_value, means_of_verification, notes)`.

## expenses ("Finance Lite" — explicitly not a general ledger)
- **Budget** — one-to-one with `Project`, `total_amount`.
- **BudgetLine** — `(budget, category, allocated_amount)`.
- **Expense** — `(organisation, project, budget_line, submitted_by, amount, description, receipt [private_storage], status, reviewed_by, reviewed_at, review_note)`. `Expense.clean()` raises `ValidationError` if `reviewed_by == submitted_by` — self-approval is blocked at the model layer, not just the view (belt-and-braces; see `apps/expenses/tests.py`).

## reporting / impact
No dedicated models — both apps compute directly from the models above at request time (PDF via `reportlab`, CSV via the stdlib `csv` module, impact metrics via aggregate queries). This is intentional: spec section 32/52 forbids hard-coded dashboard numbers.

## opportunities
- **Opportunity** — `(network, title, opportunity_type, description, eligibility, opening_date, closing_date, location, external_url, status, target_sectors/target_provinces [JSON, unused matching hints for a future phase])`.

## audit
- **AuditLogEntry** — `(actor, organisation, action, object_type, object_id, changes [JSON], ip_address, created_at)`. Append-only; never stores secrets.

## Entity relationship summary

```
Organisation ──< OrganisationMembership >── User
Organisation ──< MembershipApplication ──< MembershipStatusEvent
Organisation ──< ComplianceObligation >── ComplianceRule
Organisation ──< GovernanceOfficial / GovernanceMeeting
Organisation ──< Policy ──< PolicyVersion ──> Document
Organisation ──< Grant
Organisation ──< Programme ──< Activity
                       │  \__M2M__ Grant
                       ├──< Outcome / Output ──< Indicator ──< IndicatorPeriodValue
                       ├──< Beneficiary
                       └──< AttendanceRecord (Beneficiary optional)
Organisation ──< Project (Grant optional, Programme optional) ──< ProjectTask
                       └── Budget ──< BudgetLine ──< Expense
Network ──< NetworkStaffRole >── User
Network ──< Opportunity
```
