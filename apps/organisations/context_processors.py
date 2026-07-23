def active_organisation(request):
    organisation = getattr(request, "organisation", None)
    memberships = []
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        memberships = list(user.active_memberships)
    return {
        "active_organisation": organisation,
        "user_organisation_memberships": memberships,
    }
