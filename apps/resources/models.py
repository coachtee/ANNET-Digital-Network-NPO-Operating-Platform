from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel, UUIDPrimaryKeyModel


class Resource(UUIDPrimaryKeyModel, TimeStampedModel):
    """A Bohlale Impact-published resource (guide, template, policy,
    checklist, toolkit, video, external link, report or training
    material) — staff-managed platform content, distinct from any one
    organisation's own private documents (see apps.documents.Document,
    which is org-scoped and private-by-default; this is the opposite
    case: public-by-design content one organisation's staff publish for
    every organisation on the platform to use).

    Deliberately not linked through Document/GenericForeignKey: Document
    requires an owning organisation and defaults to private storage,
    neither of which fits a platform-wide public resource. ``file`` uses
    plain public storage instead, the same pattern already used for
    Organisation.public_logo / Network.logo.

    Only ``status`` gates visibility (draft/published never show
    publicly; archived is a soft-delete that keeps the row instead of
    losing it) -- there's no separate visibility field, since a resource
    that isn't meant to be public simply isn't published yet.
    """

    TYPE_GUIDE = "guide"
    TYPE_TEMPLATE = "template"
    TYPE_POLICY = "policy"
    TYPE_CHECKLIST = "checklist"
    TYPE_TOOLKIT = "toolkit"
    TYPE_VIDEO = "video"
    TYPE_LINK = "link"
    TYPE_REPORT = "report"
    TYPE_TRAINING = "training_material"
    TYPE_CHOICES = [
        (TYPE_GUIDE, "Guide"),
        (TYPE_TEMPLATE, "Template"),
        (TYPE_POLICY, "Policy"),
        (TYPE_CHECKLIST, "Checklist"),
        (TYPE_TOOLKIT, "Toolkit"),
        (TYPE_VIDEO, "Video"),
        (TYPE_LINK, "Link"),
        (TYPE_REPORT, "Report"),
        (TYPE_TRAINING, "Training Material"),
    ]

    STATUS_DRAFT = "draft"
    STATUS_PUBLISHED = "published"
    STATUS_ARCHIVED = "archived"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_PUBLISHED, "Published"),
        (STATUS_ARCHIVED, "Archived"),
    ]

    title = models.CharField(max_length=255)
    resource_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_GUIDE)
    category = models.CharField(
        max_length=100, blank=True,
        help_text="Subject area, e.g. Governance, Compliance, M&E (free text -- kept light on purpose for V1).",
    )
    description = models.TextField(blank=True)
    file = models.FileField(upload_to="resources/%Y/%m/", blank=True)
    external_url = models.URLField(blank=True, help_text="Used for the Link type, or alongside a file as a source link.")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    is_featured = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-is_featured", "-published_at", "-created_at"]

    def __str__(self):
        return self.title

    @property
    def is_published(self):
        return self.status == self.STATUS_PUBLISHED
