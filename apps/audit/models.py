import uuid

from django.conf import settings
from django.db import models


class AuditLogEntry(models.Model):
    """Append-only record of security/business-significant actions
    (spec section 37): board changes, compliance status changes, document
    replacement, expense approval, org profile changes, membership
    decisions, permission changes.

    Never store secrets (passwords, tokens, raw file contents) in
    ``changes`` — only field-level before/after values for auditable data.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_entries"
    )
    organisation = models.ForeignKey(
        "organisations.Organisation", on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_entries"
    )
    action = models.CharField(max_length=100)
    object_type = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=64, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organisation", "-created_at"]),
            models.Index(fields=["action"]),
        ]
        verbose_name_plural = "Audit log entries"

    def __str__(self):
        return f"{self.action} by {self.actor} at {self.created_at}"
