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
