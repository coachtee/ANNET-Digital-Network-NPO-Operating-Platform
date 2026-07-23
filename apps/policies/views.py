from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from apps.audit.services import log_action
from apps.core.permissions import has_org_capability
from apps.documents.models import Document
from apps.organisations.services import get_organisation_or_404_for_user
from apps.policies.forms import PolicyForm, PolicyVersionUploadForm
from apps.policies.models import Policy


@login_required
def policy_list(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    return render(request, "policies/list.html", {
        "organisation": organisation, "policies": organisation.policies.all(),
        "can_manage": has_org_capability(request.user, organisation, "policies.manage"),
    })


@login_required
def create_policy(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    if not has_org_capability(request.user, organisation, "policies.manage"):
        raise PermissionDenied
    form = PolicyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        policy = form.save(commit=False)
        policy.organisation = organisation
        policy.save()
        log_action("policy.created", organisation=organisation, obj=policy, actor=request.user)
        messages.success(request, "Policy created. Upload the first version below.")
        return redirect("policies:detail", slug=slug, policy_id=policy.id)
    return render(request, "policies/policy_form.html", {"organisation": organisation, "form": form})


@login_required
def policy_detail(request, slug, policy_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    policy = get_object_or_404(Policy, id=policy_id, organisation=organisation)
    can_manage = has_org_capability(request.user, organisation, "policies.manage")
    upload_form = PolicyVersionUploadForm()

    if request.method == "POST" and can_manage:
        upload_form = PolicyVersionUploadForm(request.POST, request.FILES)
        if upload_form.is_valid():
            document = Document.objects.create(
                organisation=organisation,
                title=upload_form.cleaned_data["document_title"],
                file=upload_form.cleaned_data["file"],
                visibility="organisation",
                uploaded_by=request.user,
            )
            next_version_number = (policy.current_version.version_number + 1) if policy.current_version else 1
            policy.versions.create(
                version_number=next_version_number, document=document,
                approved_date=upload_form.cleaned_data["approved_date"], notes=upload_form.cleaned_data["notes"],
            )
            log_action("policy.version_uploaded", organisation=organisation, obj=policy, actor=request.user)
            messages.success(request, f"Version {next_version_number} uploaded.")
            return redirect("policies:detail", slug=slug, policy_id=policy.id)

    context = {
        "organisation": organisation, "policy": policy, "can_manage": can_manage,
        "upload_form": upload_form, "versions": policy.versions.select_related("document"),
    }
    return render(request, "policies/policy_detail.html", context)
