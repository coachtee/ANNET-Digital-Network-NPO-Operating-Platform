import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.core.models import TimeStampedModel
from apps.core.storage import private_storage


class Document(TimeStampedModel):
    """The evidence/document vault (spec section 22).

    Files are stored via ``private_storage``, outside MEDIA_ROOT and never
    served by a public URL. Every download goes through
    ``documents.views.download_document``, which re-checks the requesting
    user's organisation membership (and, for VISIBILITY_PRIVATE rows, that
    they hold documents.manage rather than just documents.view) before
    streaming the file. The optional generic relation lets a document
    attach to a compliance obligation, governance meeting, policy, grant,
    project, programme, M&E indicator or expense without each of those
    apps needing a bespoke file field.

    Basic versioning: replacing a document creates a new row with
    ``supersedes`` pointing at the old one and ``version`` incremented,
    and flips the old row's ``status`` to archived. This keeps the vault's
    default (status=active) listing showing only the current version of
    each document while the full chain stays queryable via ``supersedes``/
    ``superseded_by`` -- deliberately not a general-purpose revision
    system, just enough history for "which is current" and "what came
    before it".
    """

    VISIBILITY_PRIVATE = "private"
    VISIBILITY_ORGANISATION = "organisation"
    VISIBILITY_PUBLIC = "public"
    VISIBILITY_CHOICES = [
        (VISIBILITY_PRIVATE, "Private (restricted roles only)"),
        (VISIBILITY_ORGANISATION, "Organisation (all organisation members)"),
        (VISIBILITY_PUBLIC, "Public (visible on public profile)"),
    ]

    CATEGORY_ORGANISATION = "organisation"
    CATEGORY_GOVERNANCE = "governance"
    CATEGORY_COMPLIANCE = "compliance"
    CATEGORY_PROGRAMMES = "programmes"
    CATEGORY_FINANCE = "finance"
    CATEGORY_PARTNERSHIPS = "partnerships"
    CATEGORY_OTHER = "other"
    CATEGORY_CHOICES = [
        (CATEGORY_ORGANISATION, "Organisation"),
        (CATEGORY_GOVERNANCE, "Governance"),
        (CATEGORY_COMPLIANCE, "Compliance"),
        (CATEGORY_PROGRAMMES, "Programmes"),
        (CATEGORY_FINANCE, "Finance"),
        (CATEGORY_PARTNERSHIPS, "Partnerships"),
        (CATEGORY_OTHER, "Other"),
    ]

    STATUS_ACTIVE = "active"
    STATUS_ARCHIVED = "archived"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_ARCHIVED, "Archived"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey("organisations.Organisation", on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_OTHER)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to="documents/%Y/%m/", storage=private_storage)
    file_size = models.PositiveIntegerField(default=0)
    visibility = models.CharField(max_length=15, choices=VISIBILITY_CHOICES, default=VISIBILITY_PRIVATE)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="documents_uploaded")

    version = models.PositiveIntegerField(default=1)
    supersedes = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="superseded_by_set"
    )

    # Optional link to the record this evidences (grant, project, expense, ...)
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.CharField(max_length=64, null=True, blank=True)
    related_object = GenericForeignKey("content_type", "object_id")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organisation", "-created_at"]),
            models.Index(fields=["organisation", "status"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.file and not self.file_size:
            self.file_size = self.file.size
        super().save(*args, **kwargs)

    @property
    def superseded_by(self):
        return self.superseded_by_set.first()
