import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.core.models import TimeStampedModel
from apps.core.storage import private_storage


class Document(TimeStampedModel):
    """The evidence/document vault (spec section 22).

    Files are stored via ``private_storage`` — outside MEDIA_ROOT and never
    served by a public URL. Every download goes through
    ``documents.views.download_document``, which re-checks the requesting
    user's organisation membership before streaming the file. The optional
    generic relation lets a document attach to a compliance obligation,
    governance meeting, policy, grant, project, programme, M&E indicator or
    expense without each of those apps needing a bespoke file field.
    """

    VISIBILITY_PRIVATE = "private"
    VISIBILITY_ORGANISATION = "organisation"
    VISIBILITY_PUBLIC = "public"
    VISIBILITY_CHOICES = [
        (VISIBILITY_PRIVATE, "Private (restricted roles only)"),
        (VISIBILITY_ORGANISATION, "Organisation (all organisation members)"),
        (VISIBILITY_PUBLIC, "Public (visible on public profile)"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey("organisations.Organisation", on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to="documents/%Y/%m/", storage=private_storage)
    file_size = models.PositiveIntegerField(default=0)
    visibility = models.CharField(max_length=15, choices=VISIBILITY_CHOICES, default=VISIBILITY_PRIVATE)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="documents_uploaded")

    # Optional link to the record this evidences (grant, project, expense, ...)
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.CharField(max_length=64, null=True, blank=True)
    related_object = GenericForeignKey("content_type", "object_id")

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organisation", "-created_at"])]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.file and not self.file_size:
            self.file_size = self.file.size
        super().save(*args, **kwargs)
