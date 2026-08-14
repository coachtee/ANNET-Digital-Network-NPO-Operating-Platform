import uuid

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Programme(TimeStampedModel):
    """Ongoing mission delivery (spec section 23) — may span multiple
    grants over time; a grant may in turn fund multiple programmes."""

    STATUS_PLANNED = "planned"
    STATUS_ACTIVE = "active"
    STATUS_PAUSED = "paused"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [
        (STATUS_PLANNED, "Planned"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_PAUSED, "Paused"),
        (STATUS_CLOSED, "Closed"),
    ]

    # Guided-creation wizard, mirroring apps.organisations' proven
    # onboarding_step mechanism: the Programme row is created after step 1
    # and each later step edits that same instance until WIZARD_COMPLETE.
    WIZARD_PROGRAMME = "programme"
    WIZARD_WHY = "why"
    WIZARD_WHO_AND_WHERE = "who_and_where"
    WIZARD_SUCCESS = "success"
    WIZARD_PROJECTS_AND_ACTIVITIES = "projects_and_activities"
    WIZARD_PEOPLE_AND_RESOURCES = "people_and_resources"
    WIZARD_BUDGET_AND_FUNDING = "budget_and_funding"
    WIZARD_REVIEW = "review"
    WIZARD_COMPLETE = "complete"
    WIZARD_STEP_CHOICES = [
        (WIZARD_PROGRAMME, "Programme"),
        (WIZARD_WHY, "Why"),
        (WIZARD_WHO_AND_WHERE, "Who & Where"),
        (WIZARD_SUCCESS, "What Success Looks Like"),
        (WIZARD_PROJECTS_AND_ACTIVITIES, "Projects & Activities"),
        (WIZARD_PEOPLE_AND_RESOURCES, "People & Resources"),
        (WIZARD_BUDGET_AND_FUNDING, "Budget & Funding"),
        (WIZARD_REVIEW, "Review & Create"),
        (WIZARD_COMPLETE, "Complete"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey("organisations.Organisation", on_delete=models.CASCADE, related_name="programmes")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    programme_area = models.CharField(max_length=150, blank=True)
    locations = models.JSONField(default=list, blank=True)
    services = models.JSONField(default=list, blank=True)
    target_beneficiary_groups = models.JSONField(default=list, blank=True)
    theory_of_change_summary = models.TextField(blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_PLANNED)
    grants = models.ManyToManyField("grants.Grant", blank=True, related_name="programmes")

    # Plan tab (DSD Part C-aligned, but generic -- see
    # PROGRAMME_WORKSPACE_ARCHITECTURE_PROPOSAL.md). start_date/end_date
    # answer "Programme period" (C2.4); need_and_background answers "why
    # does this programme exist" (C2.1); staffing_plan is a narrative
    # summary, not a structured staff roster (C4 wants the latter, out of
    # scope -- see the proposal's flagged gaps).
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    need_and_background = models.TextField(blank=True)
    staffing_plan = models.TextField(blank=True)

    wizard_step = models.CharField(max_length=25, choices=WIZARD_STEP_CHOICES, default=WIZARD_PROGRAMME)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Activity(TimeStampedModel):
    """A discrete, schedulable programme activity — the unit that
    attendance and headcount capture against (spec section 25).

    Always belongs to a Programme (attendance/M&E auto-calculation depend
    on that). Optionally sits inside one Project, and optionally connects
    to the Output(s) it produces, who is responsible for delivering it,
    and which BudgetLine it costs against -- the DSD "chain of connection"
    (why/what/who/resources/cost/measurement), see
    PROGRAMME_WORKSPACE_ARCHITECTURE_PROPOSAL.md. All four are nullable:
    an activity with none of them set is still a complete, valid record.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    programme = models.ForeignKey(Programme, on_delete=models.CASCADE, related_name="activities")
    project = models.ForeignKey(
        "projects.Project", on_delete=models.SET_NULL, null=True, blank=True, related_name="activities"
    )
    name = models.CharField(max_length=255)
    scheduled_date = models.DateField(null=True, blank=True)
    location = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=15,
        choices=[("planned", "Planned"), ("delivered", "Delivered"), ("cancelled", "Cancelled")],
        default="planned",
    )
    outputs = models.ManyToManyField(
        "monitoring_evaluation.Output", blank=True, related_name="activities",
        help_text="What this activity produces -- indicators are then reached via the Output's own Outcome.",
    )
    responsible_person = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        help_text="Who delivers this activity.",
    )
    budget_line = models.ForeignKey(
        "expenses.BudgetLine", on_delete=models.SET_NULL, null=True, blank=True, related_name="activities",
        help_text="What this activity costs against the project's budget, if tracked at this level.",
    )

    class Meta:
        ordering = ["-scheduled_date"]
        verbose_name_plural = "Activities"

    def __str__(self):
        return f"{self.programme.name} — {self.name}"
