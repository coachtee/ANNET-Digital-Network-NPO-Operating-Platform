from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from apps.organisations.models import Organisation


def get_organisation_or_404_for_user(user, slug):
    """The single tenant-scoping choke point for detail/edit/download views.

    Platform admins may reach any organisation (for support/audit); every
    other user must hold an active membership on that exact organisation.
    Never resolve an organisation from a URL/body parameter without going
    through this (or an equivalent membership check) — that is how IDOR /
    cross-tenant leaks happen.
    """
    qs = Organisation.objects.all()
    if getattr(user, "is_platform_admin", False):
        return get_object_or_404(qs, slug=slug)
    if not user.is_authenticated:
        raise PermissionDenied
    return get_object_or_404(qs, slug=slug, memberships__user=user, memberships__is_active=True)
