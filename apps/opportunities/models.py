import uuid

from django.db import models

from apps.core.models import TimeStampedModel


class Opportunity(TimeStampedModel):
    TYPE_FUNDING = "funding"
    TYPE_TRAINING = "training"
    TYPE_GRANT = "grant"
    TYPE_TENDER = "tender"
    TYPE_PARTNERSHIP = "partnership"
    TYPE_EVENT = "event"
    TYPE_CAPACITY = "capacity"
    TYPE_CHOICES = [
        (TYPE_FUNDING, "Funding"),
        (TYPE_TRAINING, "Training"),
        (TYPE_GRANT, "Grant"),
        (TYPE_TENDER, "Tender"),
        (TYPE_PARTNERSHIP, "Partnership"),
        (TYPE_EVENT, "Event"),
        (TYPE_CAPACITY, "Capacity Development"),
    ]

    STATUS_DRAFT = "draft"
    STATUS_PUBLISHED = "published"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_PUBLISHED, "Published"),
        (STATUS_CLOSED, "Closed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    network = models.ForeignKey("networks.Network", on_delete=models.CASCADE, related_name="opportunities")
    title = models.CharField(max_length=255)
    opportunity_type = models.CharField(max_length=15, choices=TYPE_CHOICES, default=TYPE_FUNDING)
    description = models.TextField(blank=True)
    eligibility = models.TextField(blank=True)
    opening_date = models.DateField(null=True, blank=True)
    closing_date = models.DateField(null=True, blank=True)
    location = models.CharField(max_length=255, blank=True)
    external_url = models.URLField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_DRAFT)

    # Lightweight future-matching hints (spec section 34) — filtered on,
    # not yet driving automated matching.
    target_sectors = models.JSONField(default=list, blank=True)
    target_provinces = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-opening_date"]

    def __str__(self):
        return self.title
