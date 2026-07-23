import uuid

from django.db import models


class UUIDPrimaryKeyModel(models.Model):
    """Base for models whose identifiers are exposed externally (URLs, APIs).

    Sequential integer PKs are fine for purely internal FK relationships,
    but anything referenced from a public-ish or cross-tenant URL uses a
    UUID so IDs can't be enumerated (spec section 41 / 38).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
