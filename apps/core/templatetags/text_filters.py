import re

from django import template

register = template.Library()


@register.filter
def humanize_action(value):
    """Turn an AuditLogEntry.action code like "governance.minutes_uploaded"
    into "Governance Minutes Uploaded" for a Recent Activity feed."""
    if not value:
        return value
    return re.sub(r"[._]+", " ", value).strip().title()


@register.filter
def split_names(value):
    """Split a comma-separated template argument into a list.

    Used by partials/_form_fields.html so a template can declare which
    fields span both columns of the two-column form grid without every
    view having to pass a Python list:

        {% include "partials/_form_fields.html" with wide_fields="description,notes" %}
    """
    if not value:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]
