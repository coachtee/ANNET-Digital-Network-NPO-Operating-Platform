from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from apps.audit.services import log_action
from apps.core.permissions import has_org_capability
from apps.organisations.services import get_organisation_or_404_for_user
from apps.projects.forms import ProjectForm, ProjectTaskForm
from apps.projects.models import Project


@login_required
def project_list(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    return render(request, "projects/list.html", {
        "organisation": organisation, "projects": organisation.projects.all(),
        "can_manage": has_org_capability(request.user, organisation, "projects.manage"),
    })


@login_required
def create_project(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    if not has_org_capability(request.user, organisation, "projects.manage"):
        raise PermissionDenied
    form = ProjectForm(request.POST or None, organisation=organisation)
    if request.method == "POST" and form.is_valid():
        project = form.save(commit=False)
        project.organisation = organisation
        project.save()
        log_action("project.created", organisation=organisation, obj=project, actor=request.user)
        messages.success(request, "Project created.")
        return redirect("projects:detail", slug=slug, project_id=project.id)
    return render(request, "projects/project_form.html", {"organisation": organisation, "form": form})


@login_required
def project_detail(request, slug, project_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    project = get_object_or_404(Project, id=project_id, organisation=organisation)
    can_manage = has_org_capability(request.user, organisation, "projects.manage")
    task_form = ProjectTaskForm(organisation=organisation)
    if request.method == "POST" and can_manage:
        task_form = ProjectTaskForm(request.POST, organisation=organisation)
        if task_form.is_valid():
            task = task_form.save(commit=False)
            task.project = project
            task.save()
            messages.success(request, "Task added.")
            return redirect("projects:detail", slug=slug, project_id=project.id)
    context = {
        "organisation": organisation, "project": project, "can_manage": can_manage,
        "task_form": task_form, "tasks": project.tasks.all(),
        "budget": getattr(project, "project_budget", None),
        "expenses": project.expenses.all()[:10],
    }
    return render(request, "projects/project_detail.html", context)
