import uuid

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class MembershipApplication(TimeStampedModel):
    """An organisation's application to join a network/programme.

    ``network`` is what makes this generic rather than ANNET/Bohlale-Impact
    -specific: an organisation applies to *a* network (the platform itself,
    or a partner programme such as Black Sash — see
    BOHLALE_IMPACT_ASSESSMENT.md §2/§8), and the same review/decide workflow
    and capability checks (apps.core.permissions.has_network_capability)
    apply regardless of which one. One organisation can hold independent
    applications/memberships against multiple networks at once.

    ``approved`` is the terminal "Active Member" state for a given network —
    Organisation.is_network_member reads this status for the platform's
    primary network specifically. A re-application after a decline creates
    a new row so the decision history of the earlier attempt is preserved
    rather than overwritten.
    """

    STATUS_DRAFT = "draft"
    STATUS_SUBMITTED = "submitted"
    STATUS_INFORMATION_REQUESTED = "information_requested"
    STATUS_APPROVED = "approved"
    STATUS_DECLINED = "declined"
    STATUS_WITHDRAWN = "withdrawn"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_SUBMITTED, "Submitted"),
        (STATUS_INFORMATION_REQUESTED, "Information Requested"),
        (STATUS_APPROVED, "Active Member"),
        (STATUS_DECLINED, "Declined"),
        (STATUS_WITHDRAWN, "Withdrawn"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey(
        "organisations.Organisation", on_delete=models.CASCADE, related_name="network_memberships"
    )
    network = models.ForeignKey(
        "networks.Network", on_delete=models.CASCADE, related_name="membership_applications"
    )
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    submitted_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    motivation = models.TextField(blank=True, help_text="Why this organisation is applying to join.")
    internal_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["network", "status"])]

    def __str__(self):
        return f"{self.organisation} — {self.network} — {self.get_status_display()}"


class MembershipStatusEvent(models.Model):
    """Append-only decision/status history for a membership application —
    required so network/programme admins have a durable audit trail of who
    requested information, when, and why (spec section 31/37).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(MembershipApplication, on_delete=models.CASCADE, related_name="status_events")
    status = models.CharField(max_length=25, choices=MembershipApplication.STATUS_CHOICES)
    note = models.TextField(blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.application} -> {self.status}"
