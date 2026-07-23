from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect

from apps.audit.services import log_action
from apps.beneficiaries.forms import BeneficiaryForm
from apps.core.permissions import has_org_capability
from apps.organisations.services import get_organisation_or_404_for_user


@login_required
def beneficiary_list(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    if not has_org_capability(request.user, organisation, "beneficiaries.view"):
        raise PermissionDenied
    beneficiaries = organisation.beneficiaries.select_related("programme")
    programme_filter = request.GET.get("programme")
    if programme_filter:
        beneficiaries = beneficiaries.filter(programme_id=programme_filter)
    return render(request, "beneficiaries/list.html", {
        "organisation": organisation, "beneficiaries": beneficiaries,
        "can_manage": has_org_capability(request.user, organisation, "beneficiaries.manage"),
        "programmes": organisation.programmes.all(),
    })


@login_required
def create_beneficiary(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    if not has_org_capability(request.user, organisation, "beneficiaries.manage"):
        raise PermissionDenied
    form = BeneficiaryForm(request.POST or None, organisation=organisation)
    if request.method == "POST" and form.is_valid():
        beneficiary = form.save(commit=False)
        beneficiary.organisation = organisation
        beneficiary.save()
        log_action("beneficiary.created", organisation=organisation, obj=beneficiary, actor=request.user)
        messages.success(request, "Beneficiary added.")
        return redirect("beneficiaries:list", slug=slug)
    return render(request, "beneficiaries/beneficiary_form.html", {"organisation": organisation, "form": form})
