import uuid

from django.db import models

from apps.core.models import TimeStampedModel

POLICY_CATEGORY_CHOICES = [
    ("governance", "Governance"),
    ("finance", "Finance"),
    ("hr", "Human Resources"),
    ("safeguarding", "Safeguarding / Child Protection"),
    ("popia", "POPIA / Data Protection"),
    ("procurement", "Procurement"),
    ("health_safety", "Health & Safety"),
    ("other", "Other"),
]


class Policy(TimeStampedModel):
    STATUS_DRAFT = "draft"
    STATUS_APPROVED = "approved"
    STATUS_UNDER_REVIEW = "under_review"
    STATUS_EXPIRED = "expired"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_UNDER_REVIEW, "Under Review"),
        (STATUS_EXPIRED, "Expired"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey("organisations.Organisation", on_delete=models.CASCADE, related_name="policies")
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=30, choices=POLICY_CATEGORY_CHOICES, default="other")
    owner = models.CharField(max_length=255, blank=True, help_text="Role or person accountable for this policy")
    approval_authority = models.CharField(max_length=255, blank=True, help_text="e.g. Board of Directors")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    approval_date = models.DateField(null=True, blank=True)
    next_review_date = models.DateField(null=True, blank=True)
    applicable_programmes = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Policies"

    def __str__(self):
        return self.name

    @property
    def current_version(self):
        return self.versions.order_by("-version_number").first()


class PolicyVersion(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, related_name="versions")
    version_number = models.PositiveIntegerField()
    document = models.ForeignKey("documents.Document", on_delete=models.PROTECT, related_name="+")
    approved_date = models.DateField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-version_number"]
        constraints = [models.UniqueConstraint(fields=["policy", "version_number"], name="unique_policy_version")]

    def __str__(self):
        return f"{self.policy.name} v{self.version_number}"
