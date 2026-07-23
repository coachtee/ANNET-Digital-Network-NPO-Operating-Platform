import uuid

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models


class UserManager(BaseUserManager):
    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_platform_admin", True)
        extra_fields.setdefault("email_verified", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Custom user model, authenticated by email rather than username.

    Users may belong to multiple organisations (apps.organisations.models
    .OrganisationMembership) and must explicitly switch active organisation
    context (see apps.organisations.middleware).
    """

    username = None
    email = models.EmailField("email address", unique=True)
    phone_number = models.CharField(max_length=32, blank=True)

    email_verified = models.BooleanField(default=False)
    email_verification_token = models.UUIDField(default=uuid.uuid4, editable=False)

    # Platform Super Administrator (Naleli Innovations technical team).
    # Implicitly holds every capability in every organisation/network scope
    # — see apps.core.permissions. Distinct from Django's is_superuser,
    # which only governs the Django admin site.
    is_platform_admin = models.BooleanField(default=False)

    # Set on a user's session-scoped kiosk account to hard-block access to
    # any non-kiosk view regardless of any other role/membership they hold.
    is_kiosk_only = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        ordering = ["email"]

    def __str__(self):
        return self.get_full_name() or self.email

    @property
    def active_memberships(self):
        return self.organisation_memberships.filter(is_active=True).select_related("organisation")
