from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.audit.services import log_action
from apps.core.permissions import has_org_capability
from apps.documents.forms import DocumentUploadForm
from apps.documents.models import Document
from apps.impact.services import people_reached_for_programme
from apps.organisations.services import get_organisation_or_404_for_user
from apps.programmes.forms import (
    ActivityForm,
    AssumptionForm,
    ContextNoteForm,
    LearningLogEntryForm,
    LearningQuestionForm,
    ProgrammeCreateForm,
    ProgrammeMembershipForm,
    ProgrammePlanForm,
    TheoryOfChangeForm,
)
from apps.programmes.models import (
    Activity,
    Assumption,
    ContextNote,
    LearningLogEntry,
    LearningQuestion,
    Programme,
    ProgrammeMembership,
)
from apps.programmes.services import (
    compute_programme_attention,
    compute_programme_progress,
    programme_budget_summary,
    programme_readiness_steps,
)

def _require_manage(request, organisation):
    if not has_org_capability(request.user, organisation, "programmes.manage"):
        raise PermissionDenied


@login_required
def programme_list(request, slug):
    """Programme list + "New Programme" -- a short create form in a
    modal, not a wizard. A Programme is created immediately and the user
    is sent straight into its (possibly still-incomplete) Workspace,
    where Plan/M&E/Team/Projects let them progressively fill it in.

    Every click of "New Programme" starts a genuinely new, empty
    Programme -- it can never resume or inherit data from another
    programme."""
    organisation = get_organisation_or_404_for_user(request.user, slug)
    can_manage = has_org_capability(request.user, organisation, "programmes.manage")
    programmes = organisation.programmes.all()
    rows = [{"programme": p, "progress": compute_programme_progress(p)} for p in programmes]

    form = None
    if can_manage:
        form = ProgrammeCreateForm(request.POST if request.method == "POST" else None)
        if request.method == "POST" and form.is_valid():
            programme = form.save(commit=False)
            programme.organisation = organisation
            programme.save()
            log_action("programme.created", organisation=organisation, obj=programme, actor=request.user)
            return redirect("programmes:detail", slug=slug, programme_id=programme.id)

    return render(request, "programmes/list.html", {
        "organisation": organisation, "rows": rows, "can_manage": can_manage, "form": form,
    })


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
        "readiness": programme_readiness_steps(programme),
    }
    return render(request, "programmes/programme_detail.html", context)


@login_required
def programme_plan(request, slug, programme_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    programme = get_object_or_404(Programme, id=programme_id, organisation=organisation)
    can_manage = has_org_capability(request.user, organisation, "programmes.manage")
    editing = (request.GET.get("edit") == "1" or request.method == "POST") and "save_toc" not in request.POST and "add_assumption" not in request.POST

    form = None
    if editing and can_manage:
        form = ProgrammePlanForm(request.POST if request.method == "POST" else None, instance=programme, organisation=organisation)
        if request.method == "POST" and form.is_valid():
            form.save()
            messages.success(request, "Programme plan updated.")
            return redirect("programmes:plan", slug=slug, programme_id=programme.id)

    toc_form = TheoryOfChangeForm(instance=programme)
    assumption_form = AssumptionForm()
    if can_manage and request.method == "POST":
        if "save_toc" in request.POST:
            toc_form = TheoryOfChangeForm(request.POST, instance=programme)
            if toc_form.is_valid():
                toc_form.save()
                messages.success(request, "Theory of Change saved.")
                return redirect("programmes:plan", slug=slug, programme_id=programme.id)
        elif "add_assumption" in request.POST:
            assumption_form = AssumptionForm(request.POST)
            if assumption_form.is_valid():
                assumption = assumption_form.save(commit=False)
                assumption.programme = programme
                assumption.save()
                messages.success(request, "Assumption added.")
                return redirect("programmes:plan", slug=slug, programme_id=programme.id)

    return render(request, "programmes/programme_plan.html", {
        "organisation": organisation, "programme": programme, "can_manage": can_manage,
        "active_tab": "plan", "form": form, "editing": editing and can_manage,
        "outcomes": programme.outcomes.all(),
        "toc_form": toc_form, "assumption_form": assumption_form,
        "assumptions": programme.assumptions.all(),
    })


@login_required
def assumption_edit(request, slug, programme_id, assumption_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    programme = get_object_or_404(Programme, id=programme_id, organisation=organisation)
    assumption = get_object_or_404(Assumption, id=assumption_id, programme=programme)
    _require_manage(request, organisation)

    form = AssumptionForm(request.POST if request.method == "POST" else None, instance=assumption)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Assumption updated.")
        return redirect("programmes:plan", slug=slug, programme_id=programme.id)
    return render(request, "programmes/simple_record_form.html", {
        "organisation": organisation, "programme": programme, "active_tab": "plan",
        "form": form, "title": "Edit assumption",
        "cancel_url": reverse("programmes:plan", kwargs={"slug": slug, "programme_id": programme.id}),
    })


@login_required
def assumption_delete(request, slug, programme_id, assumption_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    programme = get_object_or_404(Programme, id=programme_id, organisation=organisation)
    assumption = get_object_or_404(Assumption, id=assumption_id, programme=programme)
    _require_manage(request, organisation)

    if request.method == "POST":
        assumption.delete()
        messages.success(request, "Assumption deleted.")
        return redirect("programmes:plan", slug=slug, programme_id=programme.id)
    return render(request, "programmes/simple_record_confirm_delete.html", {
        "organisation": organisation, "programme": programme, "active_tab": "plan",
        "title": "assumption", "message": assumption.statement,
        "cancel_url": reverse("programmes:plan", kwargs={"slug": slug, "programme_id": programme.id}),
    })


@login_required
def programme_learning(request, slug, programme_id):
    """A small, practical reflection space: what the team wants to learn
    (Learning Questions), what actually happened and was learned
    (Learning Log -- OBSERVE -> LEARN -> ADAPT), and changes in the
    operating environment (Context). Deliberately not a questionnaire
    builder or a risk-management module."""
    organisation = get_organisation_or_404_for_user(request.user, slug)
    programme = get_object_or_404(Programme, id=programme_id, organisation=organisation)
    can_manage = has_org_capability(request.user, organisation, "programmes.manage")

    question_form = LearningQuestionForm(auto_id="id_question_%s")
    log_form = LearningLogEntryForm(programme=programme, auto_id="id_log_%s")
    context_form = ContextNoteForm(auto_id="id_context_%s")

    if can_manage and request.method == "POST":
        if "add_learning_question" in request.POST:
            question_form = LearningQuestionForm(request.POST, auto_id="id_question_%s")
            if question_form.is_valid():
                question = question_form.save(commit=False)
                question.programme = programme
                question.save()
                messages.success(request, "Learning question added.")
                return redirect("programmes:learning", slug=slug, programme_id=programme.id)
        elif "add_learning_log" in request.POST:
            log_form = LearningLogEntryForm(request.POST, programme=programme, auto_id="id_log_%s")
            if log_form.is_valid():
                entry = log_form.save(commit=False)
                entry.programme = programme
                entry.recorded_by = request.user
                entry.save()
                messages.success(request, "Learning recorded.")
                return redirect("programmes:learning", slug=slug, programme_id=programme.id)
        elif "add_context_note" in request.POST:
            context_form = ContextNoteForm(request.POST, auto_id="id_context_%s")
            if context_form.is_valid():
                note = context_form.save(commit=False)
                note.programme = programme
                note.save()
                messages.success(request, "Context noted.")
                return redirect("programmes:learning", slug=slug, programme_id=programme.id)

    return render(request, "programmes/programme_learning.html", {
        "organisation": organisation, "programme": programme, "can_manage": can_manage, "active_tab": "learning",
        "question_form": question_form, "log_form": log_form, "context_form": context_form,
        "learning_questions": programme.learning_questions.all(),
        "learning_log_entries": programme.learning_log_entries.select_related("project", "activity", "evidence").all(),
        "context_notes": programme.context_notes.all(),
    })


@login_required
def learning_question_edit(request, slug, programme_id, question_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    programme = get_object_or_404(Programme, id=programme_id, organisation=organisation)
    question = get_object_or_404(LearningQuestion, id=question_id, programme=programme)
    _require_manage(request, organisation)

    form = LearningQuestionForm(request.POST if request.method == "POST" else None, instance=question)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Learning question updated.")
        return redirect("programmes:learning", slug=slug, programme_id=programme.id)
    return render(request, "programmes/simple_record_form.html", {
        "organisation": organisation, "programme": programme, "active_tab": "learning",
        "form": form, "title": "Edit learning question",
        "cancel_url": reverse("programmes:learning", kwargs={"slug": slug, "programme_id": programme.id}),
    })


@login_required
def learning_question_delete(request, slug, programme_id, question_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    programme = get_object_or_404(Programme, id=programme_id, organisation=organisation)
    question = get_object_or_404(LearningQuestion, id=question_id, programme=programme)
    _require_manage(request, organisation)

    if request.method == "POST":
        question.delete()
        messages.success(request, "Learning question deleted.")
        return redirect("programmes:learning", slug=slug, programme_id=programme.id)
    return render(request, "programmes/simple_record_confirm_delete.html", {
        "organisation": organisation, "programme": programme, "active_tab": "learning",
        "title": "learning question", "message": question.question,
        "cancel_url": reverse("programmes:learning", kwargs={"slug": slug, "programme_id": programme.id}),
    })


@login_required
def learning_log_edit(request, slug, programme_id, entry_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    programme = get_object_or_404(Programme, id=programme_id, organisation=organisation)
    entry = get_object_or_404(LearningLogEntry, id=entry_id, programme=programme)
    _require_manage(request, organisation)

    form = LearningLogEntryForm(request.POST if request.method == "POST" else None, instance=entry, programme=programme)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Learning entry updated.")
        return redirect("programmes:learning", slug=slug, programme_id=programme.id)
    return render(request, "programmes/simple_record_form.html", {
        "organisation": organisation, "programme": programme, "active_tab": "learning",
        "form": form, "title": "Edit learning entry",
        "cancel_url": reverse("programmes:learning", kwargs={"slug": slug, "programme_id": programme.id}),
    })


@login_required
def learning_log_delete(request, slug, programme_id, entry_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    programme = get_object_or_404(Programme, id=programme_id, organisation=organisation)
    entry = get_object_or_404(LearningLogEntry, id=entry_id, programme=programme)
    _require_manage(request, organisation)

    if request.method == "POST":
        entry.delete()
        messages.success(request, "Learning entry deleted.")
        return redirect("programmes:learning", slug=slug, programme_id=programme.id)
    return render(request, "programmes/simple_record_confirm_delete.html", {
        "organisation": organisation, "programme": programme, "active_tab": "learning",
        "title": "learning log entry", "message": entry.what_happened,
        "cancel_url": reverse("programmes:learning", kwargs={"slug": slug, "programme_id": programme.id}),
    })


@login_required
def context_note_edit(request, slug, programme_id, note_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    programme = get_object_or_404(Programme, id=programme_id, organisation=organisation)
    note = get_object_or_404(ContextNote, id=note_id, programme=programme)
    _require_manage(request, organisation)

    form = ContextNoteForm(request.POST if request.method == "POST" else None, instance=note)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Context note updated.")
        return redirect("programmes:learning", slug=slug, programme_id=programme.id)
    return render(request, "programmes/simple_record_form.html", {
        "organisation": organisation, "programme": programme, "active_tab": "learning",
        "form": form, "title": "Edit context note",
        "cancel_url": reverse("programmes:learning", kwargs={"slug": slug, "programme_id": programme.id}),
    })


@login_required
def context_note_delete(request, slug, programme_id, note_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    programme = get_object_or_404(Programme, id=programme_id, organisation=organisation)
    note = get_object_or_404(ContextNote, id=note_id, programme=programme)
    _require_manage(request, organisation)

    if request.method == "POST":
        note.delete()
        messages.success(request, "Context note deleted.")
        return redirect("programmes:learning", slug=slug, programme_id=programme.id)
    return render(request, "programmes/simple_record_confirm_delete.html", {
        "organisation": organisation, "programme": programme, "active_tab": "learning",
        "title": "context note", "message": note.description,
        "cancel_url": reverse("programmes:learning", kwargs={"slug": slug, "programme_id": programme.id}),
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
