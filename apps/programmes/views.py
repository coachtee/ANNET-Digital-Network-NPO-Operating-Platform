from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from apps.audit.services import log_action
from apps.core.permissions import has_org_capability
from apps.organisations.services import get_organisation_or_404_for_user
from apps.programmes.forms import ActivityForm, ProgrammeForm
from apps.programmes.models import Programme


@login_required
def programme_list(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    return render(request, "programmes/list.html", {
        "organisation": organisation, "programmes": organisation.programmes.all(),
        "can_manage": has_org_capability(request.user, organisation, "programmes.manage"),
    })


@login_required
def create_programme(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    if not has_org_capability(request.user, organisation, "programmes.manage"):
        raise PermissionDenied
    form = ProgrammeForm(request.POST or None, organisation=organisation)
    if request.method == "POST" and form.is_valid():
        programme = form.save(commit=False)
        programme.organisation = organisation
        programme.save()
        form.save_m2m()
        log_action("programme.created", organisation=organisation, obj=programme, actor=request.user)
        messages.success(request, "Programme created.")
        return redirect("programmes:detail", slug=slug, programme_id=programme.id)
    return render(request, "programmes/programme_form.html", {"organisation": organisation, "form": form})


@login_required
def programme_detail(request, slug, programme_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    programme = get_object_or_404(Programme, id=programme_id, organisation=organisation)
    can_manage = has_org_capability(request.user, organisation, "programmes.manage")
    activity_form = ActivityForm()
    if request.method == "POST" and can_manage:
        activity_form = ActivityForm(request.POST)
        if activity_form.is_valid():
            activity = activity_form.save(commit=False)
            activity.programme = programme
            activity.save()
            messages.success(request, "Activity added.")
            return redirect("programmes:detail", slug=slug, programme_id=programme.id)
    context = {
        "organisation": organisation, "programme": programme, "can_manage": can_manage,
        "activity_form": activity_form, "activities": programme.activities.all(),
        "indicators": programme.indicators.all(), "beneficiary_count": programme.beneficiaries.count(),
    }
    return render(request, "programmes/programme_detail.html", context)
