import uuid

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

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Activity(TimeStampedModel):
    """A discrete, schedulable programme activity — the unit that
    attendance and headcount capture against (spec section 25)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    programme = models.ForeignKey(Programme, on_delete=models.CASCADE, related_name="activities")
    name = models.CharField(max_length=255)
    scheduled_date = models.DateField(null=True, blank=True)
    location = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=15,
        choices=[("planned", "Planned"), ("delivered", "Delivered"), ("cancelled", "Cancelled")],
        default="planned",
    )

    class Meta:
        ordering = ["-scheduled_date"]
        verbose_name_plural = "Activities"

    def __str__(self):
        return f"{self.programme.name} — {self.name}"
