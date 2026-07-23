import uuid

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel

POSITION_CHOICES = [
    ("director", "Director"),
    ("trustee", "Trustee"),
    ("chairperson", "Chairperson"),
    ("deputy_chairperson", "Deputy Chairperson"),
    ("secretary", "Secretary"),
    ("treasurer", "Treasurer"),
    ("additional_member", "Additional Member / Office Bearer"),
]


class GovernanceOfficial(TimeStampedModel):
    """A board member / director / trustee / office bearer.

    Historical officials are never overwritten (spec section 18/20) — a
    resignation or term end sets ``status`` and ``term_end`` on the same
    row rather than deleting it, so the organisation's governance history
    stays intact for audit and health-check purposes.
    """

    STATUS_ACTIVE = "active"
    STATUS_RESIGNED = "resigned"
    STATUS_TERM_ENDED = "term_ended"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_RESIGNED, "Resigned"),
        (STATUS_TERM_ENDED, "Term Ended"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey("organisations.Organisation", on_delete=models.CASCADE, related_name="governance_officials")
    full_name = models.CharField(max_length=255)
    position = models.CharField(max_length=30, choices=POSITION_CHOICES)
    email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=32, blank=True)
    term_start = models.DateField()
    term_end = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    resignation_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-status", "full_name"]

    def __str__(self):
        return f"{self.full_name} — {self.get_position_display()}"


class GovernanceMeeting(TimeStampedModel):
    MEETING_BOARD = "board"
    MEETING_AGM = "agm"
    MEETING_SPECIAL = "special"
    MEETING_COMMITTEE = "committee"
    MEETING_TYPE_CHOICES = [
        (MEETING_BOARD, "Board Meeting"),
        (MEETING_AGM, "Annual General Meeting"),
        (MEETING_SPECIAL, "Special Meeting"),
        (MEETING_COMMITTEE, "Committee Meeting"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey("organisations.Organisation", on_delete=models.CASCADE, related_name="governance_meetings")
    meeting_type = models.CharField(max_length=15, choices=MEETING_TYPE_CHOICES, default=MEETING_BOARD)
    title = models.CharField(max_length=255, blank=True)
    scheduled_date = models.DateTimeField()
    location = models.CharField(max_length=255, blank=True)
    minutes_document = models.ForeignKey(
        "documents.Document", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    is_held = models.BooleanField(default=False)

    class Meta:
        ordering = ["-scheduled_date"]

    def __str__(self):
        return f"{self.get_meeting_type_display()} — {self.scheduled_date:%Y-%m-%d}"


class MeetingAttendance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(GovernanceMeeting, on_delete=models.CASCADE, related_name="attendance_records")
    official = models.ForeignKey(GovernanceOfficial, on_delete=models.CASCADE, related_name="meeting_attendance")
    attended = models.BooleanField(default=True)
    apologies = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["meeting", "official"], name="unique_meeting_attendance")]


class Resolution(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(GovernanceMeeting, on_delete=models.CASCADE, related_name="resolutions")
    text = models.TextField()
    decision = models.CharField(
        max_length=15,
        choices=[("approved", "Approved"), ("rejected", "Rejected"), ("deferred", "Deferred")],
        default="approved",
    )

    def __str__(self):
        return self.text[:80]


class ConflictOfInterestDeclaration(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    official = models.ForeignKey(GovernanceOfficial, on_delete=models.CASCADE, related_name="declarations")
    declaration_date = models.DateField()
    description = models.TextField(blank=True)
    document = models.ForeignKey("documents.Document", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta:
        ordering = ["-declaration_date"]
