import uuid

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class ComplianceRule(TimeStampedModel):
    """A single configurable regulatory/administrative obligation
    (spec section 15). Rules are content, managed through administration —
    never hard-coded into templates — because requirements change over
    time and must carry provenance (official_source, last_verified_at).
    """

    TRIGGER_FIXED_DATE = "fixed_date"
    TRIGGER_FINANCIAL_YEAR_RELATIVE = "financial_year_relative"
    TRIGGER_ANNIVERSARY = "anniversary"
    TRIGGER_EVENT = "event_triggered"
    TRIGGER_CHOICES = [
        (TRIGGER_FIXED_DATE, "Fixed date each period"),
        (TRIGGER_FINANCIAL_YEAR_RELATIVE, "Relative to financial year end"),
        (TRIGGER_ANNIVERSARY, "Anniversary of registration/founding"),
        (TRIGGER_EVENT, "Event-triggered"),
    ]

    FREQUENCY_ONCE = "once"
    FREQUENCY_MONTHLY = "monthly"
    FREQUENCY_QUARTERLY = "quarterly"
    FREQUENCY_ANNUAL = "annual"
    FREQUENCY_BIENNIAL = "biennial"
    FREQUENCY_EVENT = "event"
    FREQUENCY_CHOICES = [
        (FREQUENCY_ONCE, "Once-off"),
        (FREQUENCY_MONTHLY, "Monthly"),
        (FREQUENCY_QUARTERLY, "Quarterly"),
        (FREQUENCY_ANNUAL, "Annual"),
        (FREQUENCY_BIENNIAL, "Every two years"),
        (FREQUENCY_EVENT, "As triggered by an event"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    authority = models.CharField(max_length=100, help_text="e.g. DSD, CIPC, SARS, POPIA, Master's Office")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    applicable_entity_types = models.JSONField(
        default=list, blank=True,
        help_text="Organisation.organisation_type / legal_structure values this rule applies to, e.g. ['npc']",
    )
    required_registration_statuses = models.JSONField(
        default=dict, blank=True,
        help_text='Organisation boolean fields that must be true, e.g. {"dsd_registered": true}',
    )

    trigger_type = models.CharField(max_length=30, choices=TRIGGER_CHOICES, default=TRIGGER_FINANCIAL_YEAR_RELATIVE)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default=FREQUENCY_ANNUAL)
    deadline_rule = models.JSONField(
        default=dict, blank=True,
        help_text='e.g. {"months_after_fy_end": 6} or {"fixed_month_day": "08-31"} or {"days_after_anniversary": 30}',
    )

    evidence_requirements = models.JSONField(default=list, blank=True, help_text="List of evidence item descriptions")
    responsible_role = models.CharField(max_length=30, blank=True, help_text="Suggested org role, e.g. compliance_officer")
    official_source = models.CharField(max_length=500, blank=True, help_text="Reference/URL to the authoritative source")
    last_verified_at = models.DateField(null=True, blank=True, help_text="When this rule's content was last checked against the official source")

    active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["authority", "name"]

    def __str__(self):
        return f"{self.authority}: {self.name}"

    def applies_to(self, organisation):
        if self.applicable_entity_types:
            if (
                organisation.organisation_type not in self.applicable_entity_types
                and organisation.legal_structure not in self.applicable_entity_types
            ):
                return False
        for field, expected in self.required_registration_statuses.items():
            if getattr(organisation, field, None) != expected:
                return False
        return True


class ComplianceObligation(TimeStampedModel):
    """An organisation's instance of a rule — this is what the Compliance
    Passport actually displays. Never auto-labelled "Compliant": the
    closest positive status is Submitted / Evidence Recorded, per the
    "Compliance Readiness" terminology principle (spec section 1/14).
    """

    STATUS_NOT_STARTED = "not_started"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_READY_FOR_SUBMISSION = "ready_for_submission"
    STATUS_SUBMITTED = "submitted"
    STATUS_EVIDENCE_RECORDED = "evidence_recorded"
    STATUS_OVERDUE = "overdue"
    STATUS_NOT_APPLICABLE = "not_applicable"
    STATUS_CHOICES = [
        (STATUS_NOT_STARTED, "Not Started"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_READY_FOR_SUBMISSION, "Ready for Submission"),
        (STATUS_SUBMITTED, "Submitted"),
        (STATUS_EVIDENCE_RECORDED, "Evidence Recorded"),
        (STATUS_OVERDUE, "Overdue"),
        (STATUS_NOT_APPLICABLE, "Not Applicable"),
    ]
    READINESS_STATUSES = {STATUS_SUBMITTED, STATUS_EVIDENCE_RECORDED, STATUS_NOT_APPLICABLE}

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey("organisations.Organisation", on_delete=models.CASCADE, related_name="compliance_obligations")
    rule = models.ForeignKey(ComplianceRule, on_delete=models.PROTECT, related_name="obligations")
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default=STATUS_NOT_STARTED)
    due_date = models.DateField(null=True, blank=True)
    responsible_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    submitted_at = models.DateField(null=True, blank=True)
    submission_reference = models.CharField(max_length=150, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["due_date"]
        constraints = [
            models.UniqueConstraint(fields=["organisation", "rule", "due_date"], name="unique_obligation_instance"),
        ]
        indexes = [models.Index(fields=["organisation", "status"])]

    def __str__(self):
        return f"{self.organisation} — {self.rule.name} ({self.due_date})"

    @property
    def is_overdue(self):
        from django.utils import timezone
        return (
            self.due_date is not None
            and self.due_date < timezone.now().date()
            and self.status not in self.READINESS_STATUSES
        )


class ComplianceEvidence(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    obligation = models.ForeignKey(ComplianceObligation, on_delete=models.CASCADE, related_name="evidence_items")
    document = models.ForeignKey("documents.Document", on_delete=models.CASCADE, related_name="compliance_evidence")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")

    def __str__(self):
        return f"Evidence for {self.obligation}"


class ComplianceStatusEvent(models.Model):
    """History of status transitions for an obligation (submission history,
    spec section 14)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    obligation = models.ForeignKey(ComplianceObligation, on_delete=models.CASCADE, related_name="status_events")
    status = models.CharField(max_length=25, choices=ComplianceObligation.STATUS_CHOICES)
    note = models.TextField(blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
