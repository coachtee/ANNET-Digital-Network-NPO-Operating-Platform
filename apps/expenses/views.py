from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.audit.services import log_action
from apps.core.permissions import has_org_capability
from apps.expenses.forms import BudgetForm, BudgetLineForm, ExpenseForm, ExpenseReviewForm
from apps.expenses.models import Budget, Expense
from apps.organisations.services import get_organisation_or_404_for_user
from apps.projects.models import Project


@login_required
def expense_list(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    if not has_org_capability(request.user, organisation, "expenses.view"):
        raise PermissionDenied
    return render(request, "expenses/list.html", {
        "organisation": organisation, "projects": organisation.projects.all(),
    })


@login_required
def project_expenses(request, slug, project_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    project = get_object_or_404(Project, id=project_id, organisation=organisation)
    can_submit = has_org_capability(request.user, organisation, "expenses.submit")
    can_approve = has_org_capability(request.user, organisation, "expenses.approve")

    budget = getattr(project, "project_budget", None)
    budget_form = BudgetForm(instance=budget) if not budget else None
    line_form = BudgetLineForm()
    expense_form = ExpenseForm(project=project)

    if request.method == "POST":
        if "create_budget" in request.POST and can_approve and not budget:
            budget_form = BudgetForm(request.POST)
            if budget_form.is_valid():
                budget = budget_form.save(commit=False)
                budget.project = project
                budget.save()
                return redirect("expenses:project_expenses", slug=slug, project_id=project.id)
        elif "add_line" in request.POST and can_approve and budget:
            line_form = BudgetLineForm(request.POST)
            if line_form.is_valid():
                line = line_form.save(commit=False)
                line.budget = budget
                line.save()
                return redirect("expenses:project_expenses", slug=slug, project_id=project.id)
        elif "submit_expense" in request.POST and can_submit:
            expense_form = ExpenseForm(request.POST, request.FILES, project=project)
            if expense_form.is_valid():
                expense = expense_form.save(commit=False)
                expense.organisation = organisation
                expense.project = project
                expense.submitted_by = request.user
                expense.save()
                log_action("expense.submitted", organisation=organisation, obj=expense, actor=request.user)
                messages.success(request, "Expense submitted for review.")
                return redirect("expenses:project_expenses", slug=slug, project_id=project.id)

    context = {
        "organisation": organisation, "project": project, "budget": budget,
        "budget_form": budget_form, "line_form": line_form, "expense_form": expense_form,
        "expenses": project.expenses.select_related("submitted_by", "reviewed_by"),
        "can_submit": can_submit, "can_approve": can_approve,
    }
    return render(request, "expenses/project_expenses.html", context)


@login_required
def review_expense(request, slug, expense_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    expense = get_object_or_404(Expense, id=expense_id, organisation=organisation)
    if not has_org_capability(request.user, organisation, "expenses.approve"):
        raise PermissionDenied
    if expense.submitted_by_id == request.user.id:
        messages.error(request, "You cannot review your own expense claim.")
        return redirect("expenses:project_expenses", slug=slug, project_id=expense.project_id)

    form = ExpenseReviewForm(request.POST or None, instance=expense)
    if request.method == "POST" and form.is_valid():
        expense = form.save(commit=False)
        expense.reviewed_by = request.user
        expense.reviewed_at = timezone.now()
        expense.full_clean()
        expense.save()
        log_action("expense.reviewed", organisation=organisation, obj=expense, actor=request.user,
                   changes={"status": expense.status})
        messages.success(request, "Expense reviewed.")
        return redirect("expenses:project_expenses", slug=slug, project_id=expense.project_id)
    return render(request, "expenses/review_form.html", {"organisation": organisation, "expense": expense, "form": form})


@login_required
def download_receipt(request, slug, expense_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    expense = get_object_or_404(Expense, id=expense_id, organisation=organisation)
    if not has_org_capability(request.user, organisation, "expenses.view"):
        raise PermissionDenied
    log_action("expense.receipt_downloaded", organisation=organisation, obj=expense, actor=request.user)
    return FileResponse(expense.receipt.open("rb"), as_attachment=True, filename=expense.receipt.name.split("/")[-1])
