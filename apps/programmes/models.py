import uuid

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel
from apps.organisations.models import PROVINCE_CHOICES

# Extensible, not exhaustive -- "Other" always available so a real
# programme is never blocked by a missing category. A plain Python list
# (not a lookup table) deliberately: easy to extend later without
# inventing a full taxonomy-admin CRUD system for this session.
PROGRAMME_AREA_CHOICES = [
    ("education_skills", "Education & Skills Development"),
    ("youth_development", "Youth Development"),
    ("children_families", "Children & Families"),
    ("health", "Health"),
    ("disability", "Disability"),
    ("older_persons", "Older Persons"),
    ("community_development", "Community Development"),
    ("social_crime_prevention", "Social Crime Prevention"),
    ("gender_based_violence", "Gender-Based Violence"),
    ("food_security", "Food Security"),
    ("other", "Other"),
]

# Shared by ProgrammeMembership and projects.ProjectMembership -- what a
# person *does* within a Programme/Project. Deliberately distinct from
# apps.core.permissions system roles (what a user can do in Bohlale) --
# see ProgrammeMembership's docstring.
TEAM_ROLE_CHOICES = [
    ("programme_manager", "Programme Manager"),
    ("programme_coordinator", "Programme Coordinator"),
    ("project_manager", "Project Manager"),
    ("me_officer", "M&E Officer"),
    ("finance_administrator", "Finance / Administrator"),
    ("facilitator", "Facilitator"),
    ("volunteer", "Volunteer"),
    ("data_reporting_officer", "Data / Reporting Officer"),
    ("community_liaison", "Community Liaison"),
    ("other", "Other"),
]


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
    programme_area = models.CharField(max_length=150, choices=PROGRAMME_AREA_CHOICES, blank=True)
    province = models.CharField(
        max_length=3, choices=PROVINCE_CHOICES, blank=True,
        help_text="Primary province. Finer geography (district, municipality, locality, venue) goes in Locations below.",
    )
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

    # Lightweight, structured Theory of Change -- "if we do X, we expect Y
    # to happen because Z". Deliberately separate from
    # theory_of_change_summary above (which answers the Plan tab's
    # free-text "Purpose" question and feeds the Programme Readiness
    # gate) -- this is a distinct, optional planning-and-learning aid, not
    # a replacement for Purpose.
    toc_what = models.TextField(blank=True, help_text="What are we doing?")
    toc_change = models.TextField(blank=True, help_text="What change do we expect?")
    toc_why = models.TextField(blank=True, help_text="Why do we believe this will contribute to that change?")

    wizard_step = models.CharField(max_length=25, choices=WIZARD_STEP_CHOICES, default=WIZARD_PROGRAMME)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def evidence_documents(self):
        """Documents already uploaded to this programme's Evidence tab --
        reused (never re-uploaded) wherever else evidence needs to be
        referenced, e.g. a Learning Log entry."""
        from django.contrib.contenttypes.models import ContentType

        from apps.documents.models import Document

        content_type = ContentType.objects.get_for_model(Programme)
        return Document.objects.filter(
            organisation_id=self.organisation_id, content_type=content_type,
            object_id=str(self.id), status=Document.STATUS_ACTIVE,
        )


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
    expected_participants = models.PositiveIntegerField(
        null=True, blank=True, help_text="Planned headcount, for comparison against actual attendance."
    )
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


class ProgrammeMembership(TimeStampedModel):
    """Who is responsible for delivering this Programme -- distinct from
    the organisation's general membership (an org may have 20 people but
    only a handful working on any one Programme) and distinct from
    beneficiaries reached through its activities. Also distinct from
    apps.core.permissions system roles: a Programme role describes what
    someone does *on this Programme*, not what they're allowed to do in
    Bohlale generally."""

    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"
    STATUS_CHOICES = [(STATUS_ACTIVE, "Active"), (STATUS_INACTIVE, "Inactive")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    programme = models.ForeignKey(Programme, on_delete=models.CASCADE, related_name="team_memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="programme_memberships")
    role = models.CharField(max_length=30, choices=TEAM_ROLE_CHOICES)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    responsibilities = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE)

    class Meta:
        ordering = ["-status", "role"]

    def __str__(self):
        return f"{self.user} — {self.get_role_display()} ({self.programme.name})"


class Assumption(TimeStampedModel):
    """What needs to be true for the Theory of Change to work -- e.g.
    "Participants have access to devices." Lives under the Programme's
    Theory of Change on the Plan tab. Deliberately just four fields: this
    is a planning aid, not a formal risk register."""

    IMPORTANCE_LOW = "low"
    IMPORTANCE_MEDIUM = "medium"
    IMPORTANCE_HIGH = "high"
    IMPORTANCE_CHOICES = [
        (IMPORTANCE_LOW, "Low"),
        (IMPORTANCE_MEDIUM, "Medium"),
        (IMPORTANCE_HIGH, "High"),
    ]

    STATUS_ACTIVE = "active"
    STATUS_BEING_TESTED = "being_tested"
    STATUS_NO_LONGER_VALID = "no_longer_valid"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_BEING_TESTED, "Being tested"),
        (STATUS_NO_LONGER_VALID, "No longer valid"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    programme = models.ForeignKey(Programme, on_delete=models.CASCADE, related_name="assumptions")
    statement = models.TextField()
    importance = models.CharField(max_length=10, choices=IMPORTANCE_CHOICES, default=IMPORTANCE_MEDIUM)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.statement[:80]


class LearningQuestion(TimeStampedModel):
    """A practical question the programme team wants to answer while the
    programme is running -- e.g. "What prevents participants from
    completing the programme?" Deliberately capped at a handful per
    programme by convention (not enforced in code), not a questionnaire
    builder."""

    STATUS_OPEN = "open"
    STATUS_LEARNING = "learning"
    STATUS_ANSWERED = "answered"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_LEARNING, "Learning"),
        (STATUS_ANSWERED, "Answered"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    programme = models.ForeignKey(Programme, on_delete=models.CASCADE, related_name="learning_questions")
    question = models.TextField()
    why_it_matters = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN)
    answer_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.question[:80]


class LearningLogEntry(TimeStampedModel):
    """A recorded learning moment -- the OBSERVE -> LEARN -> ADAPT
    feedback loop. Optionally tied to the Project/Activity it relates to
    and to an already-uploaded evidence document (never a fresh upload
    field of its own -- capture once, reuse everywhere)."""

    TYPE_SUCCESS = "success"
    TYPE_CHALLENGE = "challenge"
    TYPE_UNEXPECTED_RESULT = "unexpected_result"
    TYPE_CONTEXT_CHANGE = "context_change"
    TYPE_STAKEHOLDER_CHANGE = "stakeholder_change"
    TYPE_OPPORTUNITY = "opportunity"
    TYPE_SETBACK = "setback"
    TYPE_CHOICES = [
        (TYPE_SUCCESS, "Success"),
        (TYPE_CHALLENGE, "Challenge"),
        (TYPE_UNEXPECTED_RESULT, "Unexpected result"),
        (TYPE_CONTEXT_CHANGE, "Context change"),
        (TYPE_STAKEHOLDER_CHANGE, "Stakeholder change"),
        (TYPE_OPPORTUNITY, "Opportunity"),
        (TYPE_SETBACK, "Setback"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    programme = models.ForeignKey(Programme, on_delete=models.CASCADE, related_name="learning_log_entries")
    project = models.ForeignKey(
        "projects.Project", on_delete=models.SET_NULL, null=True, blank=True, related_name="learning_log_entries",
    )
    activity = models.ForeignKey(
        Activity, on_delete=models.SET_NULL, null=True, blank=True, related_name="learning_log_entries",
    )
    date = models.DateField()
    entry_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    what_happened = models.TextField()
    what_changed = models.TextField(blank=True)
    what_we_learned = models.TextField(blank=True)
    action_we_will_take = models.TextField(blank=True)
    evidence = models.ForeignKey(
        "documents.Document", on_delete=models.SET_NULL, null=True, blank=True, related_name="learning_log_entries",
    )
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta:
        ordering = ["-date", "-created_at"]
        verbose_name_plural = "Learning log entries"

    def __str__(self):
        return f"{self.programme.name} — {self.get_entry_type_display()} ({self.date})"


class ContextNote(TimeStampedModel):
    """A change in the programme's operating environment that may affect
    delivery -- notes/events, not a risk-management module."""

    CATEGORY_FUNDING = "funding_environment"
    CATEGORY_SCHOOL_CALENDAR = "school_calendar"
    CATEGORY_COMMUNITY = "community_conditions"
    CATEGORY_POLICY = "policy"
    CATEGORY_STAKEHOLDER = "stakeholder"
    CATEGORY_EMPLOYMENT = "employment_environment"
    CATEGORY_VENUE = "venue"
    CATEGORY_OTHER = "other"
    CATEGORY_CHOICES = [
        (CATEGORY_FUNDING, "Funding environment changed"),
        (CATEGORY_SCHOOL_CALENDAR, "School calendar changed"),
        (CATEGORY_COMMUNITY, "Community conditions changed"),
        (CATEGORY_POLICY, "Policy changed"),
        (CATEGORY_STAKEHOLDER, "Stakeholder changed"),
        (CATEGORY_EMPLOYMENT, "Employment environment changed"),
        (CATEGORY_VENUE, "Venue became unavailable"),
        (CATEGORY_OTHER, "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    programme = models.ForeignKey(Programme, on_delete=models.CASCADE, related_name="context_notes")
    category = models.CharField(max_length=25, choices=CATEGORY_CHOICES, default=CATEGORY_OTHER)
    description = models.TextField()
    date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.get_category_display()} ({self.programme.name})"
