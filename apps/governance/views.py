from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from apps.audit.services import log_action
from apps.core.permissions import has_org_capability
from apps.documents.models import Document
from apps.governance.forms import (
    GovernanceMeetingForm, GovernanceOfficialForm, GovernanceOfficialResignForm, MinutesUploadForm, ResolutionForm,
)
from apps.governance.models import GovernanceMeeting, GovernanceOfficial
from apps.organisations.services import get_organisation_or_404_for_user


@login_required
def governance_list(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    context = {
        "organisation": organisation,
        "active_officials": organisation.governance_officials.filter(status="active"),
        "past_officials": organisation.governance_officials.exclude(status="active"),
        "meetings": organisation.governance_meetings.all()[:20],
        "can_manage": has_org_capability(request.user, organisation, "governance.manage"),
    }
    return render(request, "governance/list.html", context)


@login_required
def add_official(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    if not has_org_capability(request.user, organisation, "governance.manage"):
        raise PermissionDenied
    form = GovernanceOfficialForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        official = form.save(commit=False)
        official.organisation = organisation
        official.save()
        log_action("governance.official_added", organisation=organisation, obj=official, actor=request.user)
        messages.success(request, f"{official.full_name} added.")
        return redirect("governance:list", slug=slug)
    return render(request, "governance/official_form.html", {"organisation": organisation, "form": form})


@login_required
def resign_official(request, slug, official_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    if not has_org_capability(request.user, organisation, "governance.manage"):
        raise PermissionDenied
    official = get_object_or_404(GovernanceOfficial, id=official_id, organisation=organisation)
    form = GovernanceOfficialResignForm(request.POST or None, request.FILES or None, instance=official)
    if request.method == "POST" and form.is_valid():
        official = form.save(commit=False)
        official.status = GovernanceOfficial.STATUS_RESIGNED
        uploaded_file = form.cleaned_data.get("supporting_document")
        if uploaded_file:
            official.resignation_document = Document.objects.create(
                organisation=organisation, title=f"Resignation evidence: {official.full_name}",
                category=Document.CATEGORY_GOVERNANCE, file=uploaded_file, visibility=Document.VISIBILITY_ORGANISATION,
                uploaded_by=request.user, content_type=ContentType.objects.get_for_model(GovernanceOfficial),
                object_id=str(official.id),
            )
        official.save()
        log_action("governance.official_resigned", organisation=organisation, obj=official, actor=request.user)
        messages.success(request, f"{official.full_name} marked as resigned. Their record is preserved for history.")
        return redirect("governance:list", slug=slug)
    return render(request, "governance/official_resign_form.html", {"organisation": organisation, "official": official, "form": form})


@login_required
def create_meeting(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    if not has_org_capability(request.user, organisation, "governance.manage"):
        raise PermissionDenied
    form = GovernanceMeetingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        meeting = form.save(commit=False)
        meeting.organisation = organisation
        meeting.save()
        log_action("governance.meeting_created", organisation=organisation, obj=meeting, actor=request.user)
        return redirect("governance:meeting_detail", slug=slug, meeting_id=meeting.id)
    return render(request, "governance/meeting_form.html", {"organisation": organisation, "form": form})


@login_required
def meeting_detail(request, slug, meeting_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    meeting = get_object_or_404(GovernanceMeeting, id=meeting_id, organisation=organisation)
    can_manage = has_org_capability(request.user, organisation, "governance.manage")
    resolution_form = ResolutionForm()
    if request.method == "POST" and can_manage:
        resolution_form = ResolutionForm(request.POST, request.FILES or None)
        if resolution_form.is_valid():
            resolution = resolution_form.save(commit=False)
            resolution.meeting = meeting
            resolution.created_by = request.user
            uploaded_file = resolution_form.cleaned_data.get("supporting_document")
            if uploaded_file:
                resolution_title = resolution_form.cleaned_data.get("reference_number") or "Resolution"
                resolution.document = Document.objects.create(
                    organisation=organisation, title=f"{resolution_title}: {meeting}",
                    category=Document.CATEGORY_GOVERNANCE, file=uploaded_file, visibility=Document.VISIBILITY_ORGANISATION,
                    uploaded_by=request.user, content_type=ContentType.objects.get_for_model(meeting.resolutions.model),
                )
            resolution.save()
            if uploaded_file:
                resolution.document.object_id = str(resolution.id)
                resolution.document.save(update_fields=["object_id"])
            messages.success(request, "Resolution recorded.")
            return redirect("governance:meeting_detail", slug=slug, meeting_id=meeting.id)
    context = {
        "organisation": organisation, "meeting": meeting, "can_manage": can_manage,
        "resolution_form": resolution_form, "resolutions": meeting.resolutions.all(),
        "minutes_form": MinutesUploadForm(),
    }
    return render(request, "governance/meeting_detail.html", context)


@login_required
def upload_minutes(request, slug, meeting_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    if not has_org_capability(request.user, organisation, "governance.manage"):
        raise PermissionDenied
    meeting = get_object_or_404(GovernanceMeeting, id=meeting_id, organisation=organisation)
    form = MinutesUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        document = Document.objects.create(
            organisation=organisation, title=f"Minutes: {meeting}",
            category=Document.CATEGORY_GOVERNANCE, file=form.cleaned_data["file"],
            visibility=Document.VISIBILITY_ORGANISATION, uploaded_by=request.user,
            content_type=ContentType.objects.get_for_model(GovernanceMeeting), object_id=str(meeting.id),
        )
        meeting.minutes_document = document
        meeting.save(update_fields=["minutes_document"])
        log_action("governance.minutes_uploaded", organisation=organisation, obj=meeting, actor=request.user)
        messages.success(request, "Minutes uploaded.")
    return redirect("governance:meeting_detail", slug=slug, meeting_id=meeting.id)
