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
from apps.expenses.forms import BudgetForm, BudgetLineForm, ExpenseForm
from apps.impact.services import beneficiaries_for_project
from apps.organisations.services import get_organisation_or_404_for_user
from apps.programmes.forms import ActivityForm
from apps.projects.forms import ProjectForm, ProjectTaskForm
from apps.projects.models import Project
from apps.projects.services import (
    compute_project_attention,
    compute_project_progress,
    project_finance_summary,
    project_workspace_summary,
)


@login_required
def project_list(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    projects = organisation.projects.select_related("programme", "manager")
    programme_id = request.GET.get("programme")
    if programme_id:
        projects = projects.filter(programme_id=programme_id)
    return render(request, "projects/list.html", {
        "organisation": organisation, "projects": projects,
        "can_manage": has_org_capability(request.user, organisation, "projects.manage"),
        "programme_id": programme_id,
    })


@login_required
def create_project(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    if not has_org_capability(request.user, organisation, "projects.manage"):
        raise PermissionDenied
    initial = {}
    programme_id = request.GET.get("programme")
    if programme_id:
        initial["programme"] = programme_id
    form = ProjectForm(request.POST if request.method == "POST" else None, organisation=organisation, initial=initial)
    if request.method == "POST" and form.is_valid():
        project = form.save(commit=False)
        project.organisation = organisation
        project.save()
        log_action("project.created", organisation=organisation, obj=project, actor=request.user)
        messages.success(request, "Project created.")
        if project.programme_id:
            return redirect("programmes:detail", slug=slug, programme_id=project.programme_id)
        return redirect("projects:detail", slug=slug, project_id=project.id)
    return render(request, "projects/project_form.html", {"organisation": organisation, "form": form})


@login_required
def project_edit(request, slug, project_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    project = get_object_or_404(Project, id=project_id, organisation=organisation)
    if not has_org_capability(request.user, organisation, "projects.manage"):
        raise PermissionDenied
    form = ProjectForm(request.POST if request.method == "POST" else None, instance=project, organisation=organisation)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Project updated.")
        return redirect("projects:detail", slug=slug, project_id=project.id)
    context = {"organisation": organisation, "project": project, "form": form, "active_tab": "overview"}
    context.update(project_workspace_summary(project, organisation))
    return render(request, "projects/project_edit.html", context)


@login_required
def project_detail(request, slug, project_id):
    """Project Workspace -- Overview tab (the default landing page).
    Every figure here is a real, live query; nothing is fabricated."""
    organisation = get_organisation_or_404_for_user(request.user, slug)
    project = get_object_or_404(Project, id=project_id, organisation=organisation)
    can_manage = has_org_capability(request.user, organisation, "projects.manage")

    today = timezone.localdate()
    context = {
        "organisation": organisation, "project": project, "can_manage": can_manage, "active_tab": "overview",
        "progress": compute_project_progress(project),
        "finance": project_finance_summary(project),
        "upcoming_activities": project.activities.filter(
            status="planned", scheduled_date__gte=today
        ).order_by("scheduled_date")[:5],
        "recent_evidence": Document.objects.filter(
            organisation=organisation, content_type=ContentType.objects.get_for_model(Project),
            object_id=str(project.id), status=Document.STATUS_ACTIVE,
        ).order_by("-created_at")[:5],
        "attention": compute_project_attention(project, organisation),
    }
    context.update(project_workspace_summary(project, organisation))
    return render(request, "projects/project_detail.html", context)


@login_required
def project_activities(request, slug, project_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    project = get_object_or_404(Project, id=project_id, organisation=organisation)
    can_manage = has_org_capability(request.user, organisation, "projects.manage")
    context = {
        "organisation": organisation, "project": project, "can_manage": can_manage,
        "active_tab": "activities",
        "activities": project.activities.select_related("responsible_person").prefetch_related("outputs").all(),
    }
    context.update(project_workspace_summary(project, organisation))
    return render(request, "projects/project_activities.html", context)


@login_required
def project_create_activity(request, slug, project_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    project = get_object_or_404(Project, id=project_id, organisation=organisation)
    if not has_org_capability(request.user, organisation, "projects.manage"):
        raise PermissionDenied

    if not project.programme_id:
        messages.error(request, "Link this project to a programme before adding activities.")
        return redirect("projects:detail", slug=slug, project_id=project.id)

    programme = project.programme
    form = ActivityForm(
        request.POST if request.method == "POST" else None,
        programme=programme, project=project, organisation=organisation,
    )
    if request.method == "POST" and form.is_valid():
        activity = form.save(commit=False)
        activity.programme = programme
        activity.project = project
        activity.save()
        form.save_m2m()
        log_action("activity.created", organisation=organisation, obj=activity, actor=request.user)
        messages.success(request, "Activity added.")
        return redirect("projects:activities", slug=slug, project_id=project.id)
    return render(request, "projects/project_activity_form.html", {
        "organisation": organisation, "project": project, "form": form, "active_tab": "activities",
    })


@login_required
def project_tasks(request, slug, project_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    project = get_object_or_404(Project, id=project_id, organisation=organisation)
    can_manage = has_org_capability(request.user, organisation, "projects.manage")

    form = ProjectTaskForm(organisation=organisation, project=project)
    if request.method == "POST" and can_manage:
        form = ProjectTaskForm(request.POST, organisation=organisation, project=project)
        if form.is_valid():
            task = form.save(commit=False)
            task.project = project
            task.save()
            messages.success(request, "Task added.")
            return redirect("projects:tasks", slug=slug, project_id=project.id)
    context = {
        "organisation": organisation, "project": project, "can_manage": can_manage,
        "active_tab": "tasks", "form": form, "tasks": project.tasks.select_related("assignee", "activity").all(),
    }
    context.update(project_workspace_summary(project, organisation))
    return render(request, "projects/project_tasks.html", context)


@login_required
def project_people(request, slug, project_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    project = get_object_or_404(Project, id=project_id, organisation=organisation)
    context = {
        "organisation": organisation, "project": project, "active_tab": "people",
        "beneficiaries": beneficiaries_for_project(project),
    }
    context.update(project_workspace_summary(project, organisation))
    return render(request, "projects/project_people.html", context)


@login_required
def project_budget(request, slug, project_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    project = get_object_or_404(Project, id=project_id, organisation=organisation)
    can_approve = has_org_capability(request.user, organisation, "expenses.approve")

    budget = getattr(project, "project_budget", None)
    budget_form = BudgetForm(instance=budget) if not budget else None
    line_form = BudgetLineForm()

    if request.method == "POST" and can_approve:
        if "create_budget" in request.POST and not budget:
            budget_form = BudgetForm(request.POST)
            if budget_form.is_valid():
                budget = budget_form.save(commit=False)
                budget.project = project
                budget.save()
                messages.success(request, "Budget set.")
                return redirect("projects:budget", slug=slug, project_id=project.id)
        elif "add_line" in request.POST and budget:
            line_form = BudgetLineForm(request.POST)
            if line_form.is_valid():
                line = line_form.save(commit=False)
                line.budget = budget
                line.save()
                messages.success(request, "Budget line added.")
                return redirect("projects:budget", slug=slug, project_id=project.id)

    context = {
        "organisation": organisation, "project": project, "active_tab": "budget",
        "can_approve": can_approve, "budget": budget, "budget_form": budget_form, "line_form": line_form,
        "finance": project_finance_summary(project),
        "lines": budget.lines.all() if budget else [],
    }
    context.update(project_workspace_summary(project, organisation))
    return render(request, "projects/project_budget.html", context)


@login_required
def project_expenses(request, slug, project_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    project = get_object_or_404(Project, id=project_id, organisation=organisation)
    can_submit = has_org_capability(request.user, organisation, "expenses.submit")
    can_approve = has_org_capability(request.user, organisation, "expenses.approve")

    form = ExpenseForm(project=project)
    if request.method == "POST" and can_submit:
        form = ExpenseForm(request.POST, request.FILES, project=project)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.organisation = organisation
            expense.project = project
            expense.submitted_by = request.user
            expense.save()
            log_action("expense.submitted", organisation=organisation, obj=expense, actor=request.user)
            messages.success(request, "Expense submitted for review.")
            return redirect("projects:expenses", slug=slug, project_id=project.id)

    context = {
        "organisation": organisation, "project": project, "active_tab": "expenses",
        "can_submit": can_submit, "can_approve": can_approve, "form": form,
        "expenses": project.expenses.select_related("submitted_by", "reviewed_by", "budget_line"),
    }
    context.update(project_workspace_summary(project, organisation))
    return render(request, "projects/project_expenses.html", context)


@login_required
def project_evidence(request, slug, project_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    project = get_object_or_404(Project, id=project_id, organisation=organisation)
    can_manage = has_org_capability(request.user, organisation, "documents.manage")
    content_type = ContentType.objects.get_for_model(Project)
    documents = Document.objects.filter(
        organisation=organisation, content_type=content_type, object_id=str(project.id), status=Document.STATUS_ACTIVE,
    ).select_related("uploaded_by")

    form = None
    if can_manage:
        form = DocumentUploadForm(
            request.POST if request.method == "POST" else None, request.FILES or None,
            initial={"category": Document.CATEGORY_PROGRAMMES},
        )
        if request.method == "POST" and form.is_valid():
            document = form.save(commit=False)
            document.organisation = organisation
            document.uploaded_by = request.user
            document.content_type = content_type
            document.object_id = str(project.id)
            document.save()
            log_action("document.uploaded", organisation=organisation, obj=document, actor=request.user)
            messages.success(request, "Evidence uploaded.")
            return redirect("projects:evidence", slug=slug, project_id=project.id)

    context = {
        "organisation": organisation, "project": project, "can_manage": can_manage,
        "active_tab": "evidence", "documents": documents, "form": form,
    }
    context.update(project_workspace_summary(project, organisation))
    return render(request, "projects/project_evidence.html", context)


@login_required
def project_reports(request, slug, project_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    project = get_object_or_404(Project, id=project_id, organisation=organisation)
    context = {"organisation": organisation, "project": project, "active_tab": "reports"}
    context.update(project_workspace_summary(project, organisation))
    return render(request, "projects/project_reports.html", context)
