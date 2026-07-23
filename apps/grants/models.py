import uuid

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Grant(TimeStampedModel):
    STATUS_OPPORTUNITY = "opportunity"
    STATUS_APPLICATION = "application"
    STATUS_AWARDED = "awarded"
    STATUS_AGREEMENT = "agreement"
    STATUS_ACTIVE = "active"
    STATUS_REPORTING = "reporting"
    STATUS_CLOSEOUT = "closeout"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [
        (STATUS_OPPORTUNITY, "Opportunity"),
        (STATUS_APPLICATION, "Application"),
        (STATUS_AWARDED, "Awarded"),
        (STATUS_AGREEMENT, "Agreement"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_REPORTING, "Reporting"),
        (STATUS_CLOSEOUT, "Closeout"),
        (STATUS_CLOSED, "Closed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey("organisations.Organisation", on_delete=models.CASCADE, related_name="grants")
    funder_name = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="ZAR")
    funding_start = models.DateField(null=True, blank=True)
    funding_end = models.DateField(null=True, blank=True)
    reporting_requirements = models.TextField(blank=True)
    restrictions = models.TextField(blank=True)
    responsible_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_OPPORTUNITY)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.funder_name})"
