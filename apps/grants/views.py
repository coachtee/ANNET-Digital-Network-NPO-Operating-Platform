from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from apps.audit.services import log_action
from apps.core.permissions import has_org_capability
from apps.grants.forms import GrantForm
from apps.grants.models import Grant
from apps.organisations.services import get_organisation_or_404_for_user


@login_required
def grant_list(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    return render(request, "grants/list.html", {
        "organisation": organisation, "grants": organisation.grants.all(),
        "can_manage": has_org_capability(request.user, organisation, "grants.manage"),
    })


@login_required
def create_grant(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    if not has_org_capability(request.user, organisation, "grants.manage"):
        raise PermissionDenied
    form = GrantForm(request.POST or None, organisation=organisation)
    if request.method == "POST" and form.is_valid():
        grant = form.save(commit=False)
        grant.organisation = organisation
        grant.save()
        log_action("grant.created", organisation=organisation, obj=grant, actor=request.user)
        messages.success(request, "Grant created.")
        return redirect("grants:detail", slug=slug, grant_id=grant.id)
    return render(request, "grants/grant_form.html", {"organisation": organisation, "form": form})


@login_required
def grant_detail(request, slug, grant_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    grant = get_object_or_404(Grant, id=grant_id, organisation=organisation)
    return render(request, "grants/grant_detail.html", {
        "organisation": organisation, "grant": grant,
        "projects": grant.projects.all(), "programmes": grant.programmes.all(),
    })
