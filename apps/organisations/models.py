import uuid

from django.conf import settings
from django.db import models
from django.utils.text import slugify

from apps.core.models import TimeStampedModel, UUIDPrimaryKeyModel
from apps.core.permissions import ORG_ROLE_CHOICES

PROVINCE_CHOICES = [
    ("EC", "Eastern Cape"), ("FS", "Free State"), ("GP", "Gauteng"),
    ("KZN", "KwaZulu-Natal"), ("LP", "Limpopo"), ("MP", "Mpumalanga"),
    ("NC", "Northern Cape"), ("NW", "North West"), ("WC", "Western Cape"),
]

LEGAL_STRUCTURE_CHOICES = [
    ("npc", "Non-Profit Company (NPC)"),
    ("trust", "Trust"),
    ("voluntary_association", "Voluntary Association"),
    ("other", "Other"),
]

ORGANISATION_TYPE_CHOICES = [
    ("npo", "NPO"),
    ("network", "NPO Network / Umbrella Body"),
    ("association", "Association"),
    ("foundation", "Foundation"),
    ("funder", "Funder"),
]


class Organisation(UUIDPrimaryKeyModel, TimeStampedModel):
    """The single master organisation record (spec section 13, Org 360).

    One record powers network membership, the public directory, compliance,
    governance, projects/programmes and reporting — never duplicated per
    module. Everything elsewhere in the platform that is organisation-scoped
    holds a FK back to this model.
    """

    ONBOARDING_IDENTITY = "identity"
    ONBOARDING_LEGAL = "legal"
    ONBOARDING_REGISTRATION = "registration"
    ONBOARDING_GOVERNANCE = "governance"
    ONBOARDING_ACTIVITIES = "activities"
    ONBOARDING_COMPLIANCE = "compliance"
    ONBOARDING_HEALTH_CHECK = "health_check"
    ONBOARDING_COMPLETE = "complete"
    ONBOARDING_STEP_CHOICES = [
        (ONBOARDING_IDENTITY, "Organisation Identity"),
        (ONBOARDING_LEGAL, "Legal Structure"),
        (ONBOARDING_REGISTRATION, "Registration Status"),
        (ONBOARDING_GOVERNANCE, "Governance"),
        (ONBOARDING_ACTIVITIES, "Activities"),
        (ONBOARDING_COMPLIANCE, "Compliance Profile"),
        (ONBOARDING_HEALTH_CHECK, "Health Check"),
        (ONBOARDING_COMPLETE, "Onboarding Complete"),
    ]

    # --- Identity ---
    legal_name = models.CharField(max_length=255)
    trading_name = models.CharField(max_length=255, blank=True)
    slug = models.SlugField(max_length=255, unique=True)
    organisation_type = models.CharField(max_length=20, choices=ORGANISATION_TYPE_CHOICES, default="npo")
    founding_date = models.DateField(null=True, blank=True)
    financial_year_end = models.CharField(max_length=5, blank=True, help_text="MM-DD, e.g. 02-28")

    email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=32, blank=True)
    website = models.URLField(blank=True)

    physical_address = models.TextField(blank=True)
    province = models.CharField(max_length=3, choices=PROVINCE_CHOICES, blank=True)
    municipality = models.CharField(max_length=150, blank=True)
    areas_of_operation = models.JSONField(default=list, blank=True, help_text="List of provinces/municipalities served")

    # --- Legal structure ---
    legal_structure = models.CharField(max_length=30, choices=LEGAL_STRUCTURE_CHOICES, blank=True)

    # --- Registration status (each captured independently — never assumed) ---
    dsd_registered = models.BooleanField(null=True, blank=True)
    dsd_npo_number = models.CharField(max_length=50, blank=True)
    cipc_registered = models.BooleanField(null=True, blank=True)
    cipc_registration_number = models.CharField(max_length=50, blank=True)
    sars_pbo_approved = models.BooleanField(null=True, blank=True)
    sars_pbo_number = models.CharField(max_length=50, blank=True)
    section18a_approved = models.BooleanField(null=True, blank=True)
    section18a_number = models.CharField(max_length=50, blank=True)
    masters_office_registered = models.BooleanField(null=True, blank=True)
    masters_office_number = models.CharField(max_length=50, blank=True)

    # --- Activities ---
    sectors = models.JSONField(default=list, blank=True)
    programme_areas = models.JSONField(default=list, blank=True)
    beneficiary_groups = models.JSONField(default=list, blank=True)
    sensitive_service_areas = models.JSONField(default=list, blank=True)

    # --- Onboarding / membership state ---
    onboarding_step = models.CharField(max_length=20, choices=ONBOARDING_STEP_CHOICES, default=ONBOARDING_IDENTITY)
    onboarding_completed_at = models.DateTimeField(null=True, blank=True)

    # --- Public directory / profile visibility (spec section 9) ---
    is_publicly_listed = models.BooleanField(default=False)
    public_verification_status = models.CharField(
        max_length=20,
        choices=[("unverified", "Unverified"), ("verified", "Verified")],
        default="unverified",
    )
    public_about = models.TextField(blank=True)
    public_logo = models.ImageField(upload_to="organisation_logos/", blank=True, null=True)
    public_show_impact = models.BooleanField(default=True)
    public_show_contact = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="organisations_created",
    )

    class Meta:
        ordering = ["legal_name"]
        indexes = [
            models.Index(fields=["province"]),
            models.Index(fields=["organisation_type"]),
            models.Index(fields=["is_publicly_listed"]),
        ]

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        return self.trading_name or self.legal_name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.trading_name or self.legal_name) or "organisation"
            slug = base_slug
            i = 1
            while Organisation.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                i += 1
                slug = f"{base_slug}-{i}"
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def is_network_member(self):
        return self.network_memberships.filter(status="approved").exists()


class OrganisationMembership(TimeStampedModel):
    """Links a user to an organisation with a specific role.

    This is the tenant-isolation boundary: every organisation-scoped query
    in the platform must go through a membership check like this, never
    trust a client-supplied organisation id alone (spec section 6/38).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="organisation_memberships")
    role = models.CharField(max_length=30, choices=ORG_ROLE_CHOICES, default="staff")
    is_active = models.BooleanField(default=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="memberships_invited",
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organisation", "user"], name="unique_org_membership"),
        ]
        indexes = [models.Index(fields=["user", "is_active"])]

    def __str__(self):
        return f"{self.user} @ {self.organisation} ({self.get_role_display()})"
