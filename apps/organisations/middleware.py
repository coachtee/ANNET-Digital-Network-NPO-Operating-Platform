from apps.organisations.models import Organisation

SESSION_KEY = "active_organisation_slug"


class OrganisationContextMiddleware:
    """Resolves ``request.organisation`` for the signed-in user's active
    workspace context.

    A user may belong to multiple organisations and must explicitly switch
    between them (spec section 10). The active organisation is stored in
    the session and re-validated against real, active memberships on every
    request — it is never trusted blindly, which is what keeps a stale or
    tampered session value from ever leaking cross-tenant access.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.organisation = None
        user = getattr(request, "user", None)

        if user is not None and user.is_authenticated and not getattr(user, "is_kiosk_only", False):
            slug = request.session.get(SESSION_KEY)
            membership_qs = user.active_memberships
            organisation = None
            if slug:
                organisation = Organisation.objects.filter(
                    slug=slug, memberships__user=user, memberships__is_active=True
                ).first()
            if organisation is None:
                first_membership = membership_qs.first()
                if first_membership:
                    organisation = first_membership.organisation
                    request.session[SESSION_KEY] = organisation.slug
            request.organisation = organisation

        return self.get_response(request)
