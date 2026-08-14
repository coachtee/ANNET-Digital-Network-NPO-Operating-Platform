from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.audit.services import log_action
from apps.core.permissions import has_org_capability
from apps.documents.forms import DocumentUploadForm
from apps.documents.models import Document
from apps.impact.services import people_reached_for_programme
from apps.monitoring_evaluation.forms import IndicatorForm, OutcomeForm, OutputForm
from apps.organisations.services import get_organisation_or_404_for_user
from apps.programmes.forms import (
    ActivityForm,
    ProgrammeMembershipForm,
    ProgrammePlanForm,
    ProgrammeWizardDetailsForm,
    ProgrammeWizardFundingForm,
    ProgrammeWizardPeopleResourcesForm,
    ProgrammeWizardWhyForm,
    ProgrammeWizardWhoWhereForm,
)
from apps.programmes.models import Activity, Programme, ProgrammeMembership
from apps.programmes.services import (
    compute_programme_attention,
    compute_programme_progress,
    compute_programme_readiness,
    programme_budget_summary,
)
from apps.projects.forms import ProjectForm

WIZARD_ORDER = [step for step, _ in Programme.WIZARD_STEP_CHOICES]


def _advance_wizard(programme, current_step):
    idx = WIZARD_ORDER.index(current_step)
    if idx + 1 < len(WIZARD_ORDER):
        programme.wizard_step = WIZARD_ORDER[idx + 1]
        programme.save(update_fields=["wizard_step"])


def _require_manage(request, organisation):
    if not has_org_capability(request.user, organisation, "programmes.manage"):
        raise PermissionDenied


def _is_mid_wizard(programme):
    """WIZARD_PROGRAMME is the field's default -- a programme genuinely
    mid-wizard is never sitting at that value (create_programme always
    advances to WIZARD_WHY in the same save that creates the row), so
    excluding it here is what keeps pre-existing programmes (backfilled
    with the default when this field was added) from being mistaken for
    an abandoned wizard."""
    return programme.wizard_step not in (Programme.WIZARD_PROGRAMME, Programme.WIZARD_COMPLETE)


@login_required
def programme_list(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    programmes = organisation.programmes.all()
    rows = [
        {"programme": p, "progress": compute_programme_progress(p), "is_mid_wizard": _is_mid_wizard(p)}
        for p in programmes
    ]
    return render(request, "programmes/list.html", {
        "organisation": organisation, "rows": rows,
        "can_manage": has_org_capability(request.user, organisation, "programmes.manage"),
    })


@login_required
def create_programme(request, slug):
    """Step 1 of the guided wizard: creates the Programme immediately (so
    every later step edits a real instance, mirroring
    apps.organisations' onboarding_step mechanism) and sends the user
    straight into step 2.

    Every click of "New Programme" starts a genuinely new Programme --
    it must never silently resume a different, unrelated abandoned
    wizard the org happens to have lying around. Resuming an incomplete
    Programme is only possible by explicitly opening that specific
    Programme from the Programme list (see programme_list/is_mid_wizard),
    which routes straight back into wizard_step at its saved step."""
    organisation = get_organisation_or_404_for_user(request.user, slug)
    _require_manage(request, organisation)

    form = ProgrammeWizardDetailsForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        programme = form.save(commit=False)
        programme.organisation = organisation
        programme.wizard_step = Programme.WIZARD_WHY
        programme.save()
        log_action("programme.created", organisation=organisation, obj=programme, actor=request.user)
        return redirect("programmes:wizard_step", slug=slug, programme_id=programme.id, step=Programme.WIZARD_WHY)
    return render(request, "programmes/wizard_details.html", {
        "organisation": organisation, "form": form, "step_number": 1, "step_total": 8,
    })


@login_required
def wizard_step(request, slug, programme_id, step):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    programme = get_object_or_404(Programme, id=programme_id, organisation=organisation)
    _require_manage(request, organisation)

    step_idx = WIZARD_ORDER.index(step)
    # index 0 is WIZARD_PROGRAMME, handled by create_programme's own form,
    # not this dispatcher -- so step 2 (WHY) has no wizard-navigable "back".
    prev_step = WIZARD_ORDER[step_idx - 1] if step_idx > 1 else None
    context = {
        "organisation": organisation, "programme": programme, "step": step,
        "step_number": step_idx + 1, "step_total": 8, "prev_step": prev_step,
    }

    if step == Programme.WIZARD_WHY:
        form = ProgrammeWizardWhyForm(request.POST if request.method == "POST" else None, instance=programme)
        if request.method == "POST" and form.is_valid():
            form.save()
            _advance_wizard(programme, step)
            return redirect("programmes:wizard_step", slug=slug, programme_id=programme.id, step=Programme.WIZARD_WHO_AND_WHERE)
        context["form"] = form
        return render(request, "programmes/wizard_why.html", context)

    if step == Programme.WIZARD_WHO_AND_WHERE:
        initial = {
            "target_beneficiary_groups": ", ".join(programme.target_beneficiary_groups),
            "locations": ", ".join(programme.locations),
        }
        form = ProgrammeWizardWhoWhereForm(request.POST if request.method == "POST" else None, initial=initial)
        if request.method == "POST" and form.is_valid():
            form.save(programme)
            _advance_wizard(programme, step)
            return redirect("programmes:wizard_step", slug=slug, programme_id=programme.id, step=Programme.WIZARD_SUCCESS)
        context["form"] = form
        return render(request, "programmes/wizard_who_and_where.html", context)

    if step == Programme.WIZARD_SUCCESS:
        outcome_form, output_form, indicator_form = OutcomeForm(), OutputForm(programme=programme), IndicatorForm(programme=programme)
        if request.method == "POST":
            if "continue" in request.POST:
                _advance_wizard(programme, step)
                return redirect("programmes:wizard_step", slug=slug, programme_id=programme.id, step=Programme.WIZARD_PROJECTS_AND_ACTIVITIES)
            if "add_outcome" in request.POST:
                outcome_form = OutcomeForm(request.POST)
                if outcome_form.is_valid():
                    outcome = outcome_form.save(commit=False)
                    outcome.programme = programme
                    outcome.save()
                    outcome_form = OutcomeForm()
            elif "add_output" in request.POST:
                output_form = OutputForm(request.POST, programme=programme)
                if output_form.is_valid():
                    output = output_form.save(commit=False)
                    output.programme = programme
                    output.save()
                    output_form = OutputForm(programme=programme)
            elif "add_indicator" in request.POST:
                indicator_form = IndicatorForm(request.POST, programme=programme)
                if indicator_form.is_valid():
                    indicator = indicator_form.save(commit=False)
                    indicator.programme = programme
                    indicator.save()
                    indicator_form = IndicatorForm(programme=programme)
        context.update({
            "outcome_form": outcome_form, "output_form": output_form, "indicator_form": indicator_form,
            "outcomes": programme.outcomes.all(), "outputs": programme.outputs.all(), "indicators": programme.indicators.all(),
        })
        return render(request, "programmes/wizard_success.html", context)

    if step == Programme.WIZARD_PROJECTS_AND_ACTIVITIES:
        readiness = compute_programme_readiness(programme)
        project_form = ProjectForm(organisation=organisation, initial={"programme": programme.id}) if readiness["is_ready"] else None
        activity_form = ActivityForm(programme=programme, organisation=organisation)
        if request.method == "POST":
            if "continue" in request.POST:
                _advance_wizard(programme, step)
                return redirect("programmes:wizard_step", slug=slug, programme_id=programme.id, step=Programme.WIZARD_PEOPLE_AND_RESOURCES)
            if "add_project" in request.POST and readiness["is_ready"]:
                project_form = ProjectForm(request.POST, organisation=organisation)
                if project_form.is_valid():
                    project = project_form.save(commit=False)
                    project.organisation = organisation
                    project.programme = programme
                    project.save()
                    project_form = ProjectForm(organisation=organisation, initial={"programme": programme.id})
            elif "add_activity" in request.POST:
                activity_form = ActivityForm(request.POST, programme=programme, organisation=organisation)
                if activity_form.is_valid():
                    activity = activity_form.save(commit=False)
                    activity.programme = programme
                    activity.save()
                    activity_form.save_m2m()
                    activity_form = ActivityForm(programme=programme, organisation=organisation)
        context.update({
            "project_form": project_form, "activity_form": activity_form, "readiness": readiness,
            "projects": programme.projects.all(), "activities": programme.activities.all(),
        })
        return render(request, "programmes/wizard_projects_and_activities.html", context)

    if step == Programme.WIZARD_PEOPLE_AND_RESOURCES:
        form = ProgrammeWizardPeopleResourcesForm(request.POST if request.method == "POST" else None, instance=programme)
        if request.method == "POST" and form.is_valid():
            form.save()
            _advance_wizard(programme, step)
            return redirect("programmes:wizard_step", slug=slug, programme_id=programme.id, step=Programme.WIZARD_BUDGET_AND_FUNDING)
        context["form"] = form
        return render(request, "programmes/wizard_people_and_resources.html", context)

    if step == Programme.WIZARD_BUDGET_AND_FUNDING:
        form = ProgrammeWizardFundingForm(request.POST if request.method == "POST" else None, instance=programme, organisation=organisation)
        if request.method == "POST" and form.is_valid():
            form.save()
            _advance_wizard(programme, step)
            return redirect("programmes:wizard_step", slug=slug, programme_id=programme.id, step=Programme.WIZARD_REVIEW)
        context["form"] = form
        context["budget"] = programme_budget_summary(programme)
        return render(request, "programmes/wizard_budget_and_funding.html", context)

    if step == Programme.WIZARD_REVIEW:
        if request.method == "POST":
            programme.wizard_step = Programme.WIZARD_COMPLETE
            programme.save(update_fields=["wizard_step"])
            messages.success(request, f"{programme.name} is ready. Welcome to your Programme Workspace.")
            return redirect("programmes:detail", slug=slug, programme_id=programme.id)
        context.update({
            "outcomes": programme.outcomes.all(), "indicators": programme.indicators.all(),
            "projects": programme.projects.all(), "activities": programme.activities.all(),
            "budget": programme_budget_summary(programme),
        })
        return render(request, "programmes/wizard_review.html", context)

    # Not a real wizard page (e.g. a pre-existing programme whose
    # wizard_step is still the field's default) -- send the user to the
    # real workspace rather than looping back into this dispatcher.
    return redirect("programmes:detail", slug=slug, programme_id=programme.id)


@login_required
def programme_detail(request, slug, programme_id):
    """Programme Workspace — Overview tab (the default landing page).
    Every figure here is a real, live query; nothing is fabricated."""
    organisation = get_organisation_or_404_for_user(request.user, slug)
    programme = get_object_or_404(Programme, id=programme_id, organisation=organisation)
    can_manage = has_org_capability(request.user, organisation, "programmes.manage")

    today = timezone.localdate()
    context = {
        "organisation": organisation, "programme": programme, "can_manage": can_manage, "active_tab": "overview",
        "project_count": programme.projects.count(),
        "activity_count": programme.activities.count(),
        "outcome_count": programme.outcomes.count(),
        "beneficiary_count": programme.beneficiaries.count(),
        "people_reached": people_reached_for_programme(programme),
        "progress": compute_programme_progress(programme),
        "budget": programme_budget_summary(programme),
        "indicators": programme.indicators.select_related("outcome", "output")[:5],
        "team_memberships": programme.team_memberships.select_related("user").filter(status=ProgrammeMembership.STATUS_ACTIVE)[:4],
        "team_count": programme.team_memberships.filter(status=ProgrammeMembership.STATUS_ACTIVE).count(),
        "projects": programme.projects.all()[:5],
        "upcoming_activities": programme.activities.filter(
            status="planned", scheduled_date__gte=today
        ).order_by("scheduled_date")[:5],
        "attention": compute_programme_attention(programme, organisation),
        "readiness": compute_programme_readiness(programme),
    }
    return render(request, "programmes/programme_detail.html", context)


@login_required
def programme_plan(request, slug, programme_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    programme = get_object_or_404(Programme, id=programme_id, organisation=organisation)
    can_manage = has_org_capability(request.user, organisation, "programmes.manage")
    editing = request.GET.get("edit") == "1" or request.method == "POST"

    form = None
    if editing and can_manage:
        form = ProgrammePlanForm(request.POST if request.method == "POST" else None, instance=programme)
        if request.method == "POST" and form.is_valid():
            form.save()
            messages.success(request, "Programme plan updated.")
            return redirect("programmes:plan", slug=slug, programme_id=programme.id)

    return render(request, "programmes/programme_plan.html", {
        "organisation": organisation, "programme": programme, "can_manage": can_manage,
        "active_tab": "plan", "form": form, "editing": editing and can_manage,
        "outcomes": programme.outcomes.all(),
    })


@login_required
def programme_team(request, slug, programme_id):
    """Who is responsible for delivering this Programme -- distinct from
    People Reached (beneficiaries), which stays on the Overview tab."""
    organisation = get_organisation_or_404_for_user(request.user, slug)
    programme = get_object_or_404(Programme, id=programme_id, organisation=organisation)
    can_manage = has_org_capability(request.user, organisation, "programmes.manage")

    form = None
    if can_manage:
        form = ProgrammeMembershipForm(
            request.POST if request.method == "POST" else None, organisation=organisation, programme=programme,
        )
        if request.method == "POST" and form.is_valid():
            membership = form.save(commit=False)
            membership.programme = programme
            membership.save()
            messages.success(request, "Added to the programme team.")
            return redirect("programmes:team", slug=slug, programme_id=programme.id)

    return render(request, "programmes/programme_team.html", {
        "organisation": organisation, "programme": programme, "can_manage": can_manage,
        "active_tab": "people", "form": form,
        "memberships": programme.team_memberships.select_related("user").all(),
    })


@login_required
def remove_programme_member(request, slug, programme_id, membership_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    programme = get_object_or_404(Programme, id=programme_id, organisation=organisation)
    _require_manage(request, organisation)
    membership = get_object_or_404(ProgrammeMembership, id=membership_id, programme=programme)
    if request.method == "POST":
        membership.delete()
        messages.success(request, "Removed from the programme team.")
    return redirect("programmes:team", slug=slug, programme_id=programme.id)


def _save_activity_form(form, programme, organisation, request):
    """Shared by activity_list's modal and the standalone create_activity
    page so the save behaviour never drifts between the two entry points."""
    activity = form.save(commit=False)
    activity.programme = programme
    activity.save()
    form.save_m2m()
    log_action("activity.created", organisation=organisation, obj=activity, actor=request.user)
    return activity


@login_required
def activity_list(request, slug, programme_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    programme = get_object_or_404(Programme, id=programme_id, organisation=organisation)
    can_manage = has_org_capability(request.user, organisation, "programmes.manage")

    form = None
    if can_manage:
        form = ActivityForm(request.POST if request.method == "POST" else None, programme=programme, organisation=organisation)
        if request.method == "POST" and form.is_valid():
            _save_activity_form(form, programme, organisation, request)
            messages.success(request, "Activity added.")
            return redirect("programmes:activities", slug=slug, programme_id=programme.id)

    return render(request, "programmes/activity_list.html", {
        "organisation": organisation, "programme": programme, "can_manage": can_manage, "form": form,
        "active_tab": "activities", "activities": programme.activities.select_related("project", "responsible_person").all(),
    })


@login_required
def create_activity(request, slug, programme_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    programme = get_object_or_404(Programme, id=programme_id, organisation=organisation)
    _require_manage(request, organisation)

    project = None
    project_id = request.GET.get("project")
    if project_id:
        project = get_object_or_404(programme.projects, id=project_id)

    form = ActivityForm(request.POST if request.method == "POST" else None, programme=programme, project=project, organisation=organisation)
    if request.method == "POST" and form.is_valid():
        _save_activity_form(form, programme, organisation, request)
        messages.success(request, "Activity added.")
        return redirect("programmes:activities", slug=slug, programme_id=programme.id)
    return render(request, "programmes/activity_form.html", {
        "organisation": organisation, "programme": programme, "project": project, "form": form, "active_tab": "activities",
    })


def _activity_redirect(activity, slug):
    """Return the caller to whichever workspace the activity is naturally
    part of: its Project's Activities tab if it has one, otherwise its
    Programme's."""
    if activity.project_id:
        return redirect("projects:activities", slug=slug, project_id=activity.project_id)
    return redirect("programmes:activities", slug=slug, programme_id=activity.programme_id)


@login_required
def edit_activity(request, slug, programme_id, activity_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    programme = get_object_or_404(Programme, id=programme_id, organisation=organisation)
    activity = get_object_or_404(Activity, id=activity_id, programme=programme)
    _require_manage(request, organisation)

    form = ActivityForm(
        request.POST if request.method == "POST" else None, instance=activity,
        programme=programme, project=activity.project, organisation=organisation,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        log_action("activity.updated", organisation=organisation, obj=activity, actor=request.user)
        messages.success(request, "Activity updated.")
        return _activity_redirect(activity, slug)
    return render(request, "programmes/activity_form.html", {
        "organisation": organisation, "programme": programme, "project": activity.project,
        "form": form, "active_tab": "activities", "activity": activity,
    })


@login_required
def delete_activity(request, slug, programme_id, activity_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    programme = get_object_or_404(Programme, id=programme_id, organisation=organisation)
    activity = get_object_or_404(Activity, id=activity_id, programme=programme)
    _require_manage(request, organisation)

    if request.method == "POST":
        redirect_response = _activity_redirect(activity, slug)
        log_action("activity.deleted", organisation=organisation, obj=activity, actor=request.user)
        activity.delete()
        messages.success(request, "Activity deleted.")
        return redirect_response
    return render(request, "programmes/activity_confirm_delete.html", {
        "organisation": organisation, "programme": programme, "activity": activity, "active_tab": "activities",
    })


@login_required
def programme_finance(request, slug, programme_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    programme = get_object_or_404(Programme, id=programme_id, organisation=organisation)
    can_manage = has_org_capability(request.user, organisation, "programmes.manage")
    projects = programme.projects.select_related("project_budget").all()
    return render(request, "programmes/programme_finance.html", {
        "organisation": organisation, "programme": programme, "can_manage": can_manage,
        "active_tab": "finance", "budget": programme_budget_summary(programme), "projects": projects,
    })


@login_required
def programme_evidence(request, slug, programme_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    programme = get_object_or_404(Programme, id=programme_id, organisation=organisation)
    can_manage = has_org_capability(request.user, organisation, "documents.manage")
    content_type = ContentType.objects.get_for_model(Programme)
    documents = Document.objects.filter(
        organisation=organisation, content_type=content_type, object_id=str(programme.id), status=Document.STATUS_ACTIVE,
    ).select_related("uploaded_by")

    form = None
    if can_manage:
        form = DocumentUploadForm(request.POST if request.method == "POST" else None, request.FILES or None, initial={"category": Document.CATEGORY_PROGRAMMES})
        if request.method == "POST" and form.is_valid():
            document = form.save(commit=False)
            document.organisation = organisation
            document.uploaded_by = request.user
            document.content_type = content_type
            document.object_id = str(programme.id)
            document.save()
            log_action("document.uploaded", organisation=organisation, obj=document, actor=request.user)
            messages.success(request, "Evidence uploaded.")
            return redirect("programmes:evidence", slug=slug, programme_id=programme.id)

    return render(request, "programmes/programme_evidence.html", {
        "organisation": organisation, "programme": programme, "can_manage": can_manage,
        "active_tab": "evidence", "documents": documents, "form": form,
    })


@login_required
def programme_reports(request, slug, programme_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    programme = get_object_or_404(Programme, id=programme_id, organisation=organisation)
    return render(request, "programmes/programme_reports.html", {
        "organisation": organisation, "programme": programme, "active_tab": "reports",
    })
