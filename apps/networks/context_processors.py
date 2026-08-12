from apps.networks.models import Network


def administered_networks(request):
    """Every network/programme the current user has staff access to, for
    the workspace sidebar's "Programme Administration" section. Without
    this, that section always linked to the platform's own (primary)
    network regardless of which network(s) the user actually administers
    — a Black-Sash-only admin, for example, had no way to reach their own
    dashboard/queue from the nav at all. Platform admins implicitly
    administer everything, matching the escape-hatch semantics of
    apps.core.permissions.has_network_capability elsewhere.
    """
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"administered_networks": []}
    if getattr(user, "is_platform_admin", False):
        networks = Network.objects.all().order_by("name")
    else:
        networks = Network.objects.filter(
            staff_roles__user=user, staff_roles__is_active=True
        ).distinct().order_by("name")
    return {"administered_networks": networks}
