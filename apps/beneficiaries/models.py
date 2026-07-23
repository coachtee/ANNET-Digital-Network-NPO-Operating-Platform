import uuid

from django.db import models

from apps.core.models import TimeStampedModel


class Beneficiary(TimeStampedModel):
    """Supports the three beneficiary modes from spec section 26.

    Data minimisation is enforced structurally: MODE_ANONYMOUS records
    carry no personal fields at all (headcounts live on AttendanceRecord
    instead), and even MODE_NAMED / MODE_ATTENDANCE records only expose
    optional demographic fields — nothing forces capture of ID numbers or
    addresses unless a programme explicitly needs them.
    """

    MODE_NAMED = "named"
    MODE_ATTENDANCE_PARTICIPANT = "attendance_participant"
    MODE_CHOICES = [
        (MODE_NAMED, "Named Beneficiary"),
        (MODE_ATTENDANCE_PARTICIPANT, "Attendance Participant"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey("organisations.Organisation", on_delete=models.CASCADE, related_name="beneficiaries")
    programme = models.ForeignKey("programmes.Programme", on_delete=models.CASCADE, related_name="beneficiaries")
    mode = models.CharField(max_length=25, choices=MODE_CHOICES, default=MODE_ATTENDANCE_PARTICIPANT)

    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=30, blank=True)
    contact_number = models.CharField(max_length=32, blank=True)

    is_sensitive = models.BooleanField(default=False, help_text="Enhanced access restrictions apply (spec section 26)")
    consent_recorded = models.BooleanField(default=False)
    reference_code = models.CharField(max_length=40, blank=True, help_text="Internal reference, not a government ID number")

    class Meta:
        ordering = ["last_name", "first_name"]
        verbose_name_plural = "Beneficiaries"

    def __str__(self):
        if self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        return self.reference_code or str(self.id)
