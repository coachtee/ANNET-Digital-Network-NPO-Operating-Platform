from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from apps.core.permissions import has_org_capability


class OrganisationCapabilityRequiredMixin(LoginRequiredMixin):
    """Class-based-view mixin enforcing server-side organisation-scoped RBAC.

    Views using this mixin MUST resolve ``self.organisation`` before the
    capability check runs (typically from a URL kwarg via
    ``apps.organisations.services.get_organisation_or_404_for_user``).
    This is the single choke point new views should use instead of ad-hoc
    ``if request.user.role == ...`` checks, so tenant isolation and RBAC
    stay centralised (spec sections 6 and 8).
    """

    required_capability = None  # e.g. "compliance.manage"

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        return response

    def get_organisation(self):
        raise NotImplementedError("Set self.organisation before calling check_capability().")

    def check_capability(self, organisation, capability=None):
        capability = capability or self.required_capability
        if capability is None:
            raise PermissionDenied("No capability configured for this view.")
        if not has_org_capability(self.request.user, organisation, capability):
            raise PermissionDenied("You do not have permission to perform this action for this organisation.")


def organisation_or_404(user, organisation_slug):
    """Fetch an organisation the given user is an active member of, or 404.

    Centralised so every detail/edit/download view enforces tenant
    isolation the same way instead of trusting a hidden form field.
    """
    from apps.organisations.models import Organisation

    qs = Organisation.objects.filter(slug=organisation_slug)
    if getattr(user, "is_platform_admin", False):
        return get_object_or_404(qs)
    return get_object_or_404(qs, memberships__user=user, memberships__is_active=True)
