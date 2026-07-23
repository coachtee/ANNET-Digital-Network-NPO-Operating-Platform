import uuid

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class AttendanceRecord(TimeStampedModel):
    """A single attendance/headcount entry (spec section 25/27).

    Either ``beneficiary`` is set (named/attendance-participant mode) OR
    ``headcount`` is used with no beneficiary (anonymous outreach mode) —
    never both, enforced in the form layer. This is what M&E count
    indicators aggregate from.
    """

    METHOD_MANUAL = "manual"
    METHOD_STAFF = "staff"
    METHOD_QR = "qr"
    METHOD_KIOSK = "kiosk"
    METHOD_CHOICES = [
        (METHOD_MANUAL, "Manual"),
        (METHOD_STAFF, "Staff Check-in"),
        (METHOD_QR, "QR Check-in"),
        (METHOD_KIOSK, "Kiosk"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey("organisations.Organisation", on_delete=models.CASCADE, related_name="attendance_records")
    programme = models.ForeignKey("programmes.Programme", on_delete=models.CASCADE, related_name="attendance_records")
    activity = models.ForeignKey("programmes.Activity", on_delete=models.SET_NULL, null=True, blank=True, related_name="attendance_records")
    beneficiary = models.ForeignKey("beneficiaries.Beneficiary", on_delete=models.SET_NULL, null=True, blank=True, related_name="attendance_records")
    headcount = models.PositiveIntegerField(default=1, help_text="Used for anonymous headcount entries")
    attendance_date = models.DateField()
    location = models.CharField(max_length=255, blank=True)
    check_in_method = models.CharField(max_length=10, choices=METHOD_CHOICES, default=METHOD_MANUAL)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta:
        ordering = ["-attendance_date"]
        indexes = [models.Index(fields=["programme", "attendance_date"])]
        constraints = [
            models.UniqueConstraint(
                fields=["activity", "beneficiary"],
                condition=models.Q(beneficiary__isnull=False),
                name="unique_named_attendance_per_activity",
            ),
        ]

    def __str__(self):
        who = str(self.beneficiary) if self.beneficiary else f"{self.headcount} people"
        return f"{who} — {self.programme.name} ({self.attendance_date})"

    @property
    def effective_count(self):
        return 1 if self.beneficiary_id else self.headcount


class KioskSession(TimeStampedModel):
    """A restricted, tokenised session for unattended kiosk devices
    (spec section 28). No standard user login is required or exposed —
    the token grants access only to the kiosk check-in flow for one
    programme, until it expires.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey("organisations.Organisation", on_delete=models.CASCADE, related_name="kiosk_sessions")
    programme = models.ForeignKey("programmes.Programme", on_delete=models.CASCADE, related_name="kiosk_sessions")
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Kiosk: {self.programme.name}"

    @property
    def is_valid(self):
        from django.utils import timezone
        return self.is_active and self.expires_at > timezone.now()
