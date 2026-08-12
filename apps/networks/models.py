import uuid

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel
from apps.core.permissions import NETWORK_ROLE_CHOICES


class Network(TimeStampedModel):
    """A network/programme deployment on the platform (spec section 2).
    Bohlale Impact is the anchor/initial Network record; the architecture
    supports further networks/programmes (e.g. a partner programme like
    Black Sash) without code changes — see BOHLALE_IMPACT_ASSESSMENT.md.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, unique=True)
    tagline = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to="network_logos/", blank=True, null=True)

    def __str__(self):
        return self.name


class NetworkStaffRole(TimeStampedModel):
    """Grants a user network-level (network/programme) capabilities — distinct
    from any organisation membership they may separately hold."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    network = models.ForeignKey(Network, on_delete=models.CASCADE, related_name="staff_roles")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="network_staff_roles")
    role = models.CharField(max_length=25, choices=NETWORK_ROLE_CHOICES, default="membership_officer")
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["network", "user"], name="unique_network_staff_role")]

    def __str__(self):
        return f"{self.user} — {self.get_role_display()} @ {self.network}"
