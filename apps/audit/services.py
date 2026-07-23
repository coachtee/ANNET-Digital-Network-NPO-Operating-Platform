from apps.audit.middleware import get_current_ip, get_current_user
from apps.audit.models import AuditLogEntry


def log_action(action, organisation=None, obj=None, changes=None, actor=None):
    """Record an auditable action. Call this explicitly at the point of
    business significance (e.g. after a compliance status change or
    membership decision) rather than trying to infer intent generically
    from model signals.
    """
    user = actor or get_current_user()
    if user is not None and not getattr(user, "is_authenticated", False):
        user = None

    AuditLogEntry.objects.create(
        actor=user,
        organisation=organisation,
        action=action,
        object_type=obj.__class__.__name__ if obj is not None else "",
        object_id=str(getattr(obj, "pk", "")) if obj is not None else "",
        changes=changes or {},
        ip_address=get_current_ip(),
    )
