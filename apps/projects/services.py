from django.contrib.contenttypes.models import ContentType
from django.db.models import Sum
from django.urls import reverse

from apps.expenses.models import Expense


def project_finance_summary(project):
    """Budget vs Committed vs Actual vs Remaining vs Variance, live from the
    Project's own Budget/BudgetLine/Expense rows -- nothing stored, nothing
    fabricated. "Committed" is expenditure submitted but not yet reviewed;
    "Actual" is expenditure a reviewer has approved."""
    budget = getattr(project, "project_budget", None)
    planned = budget.total_amount if budget else 0
    expenses = project.expenses.all()
    committed = expenses.filter(status=Expense.STATUS_SUBMITTED).aggregate(total=Sum("amount"))["total"] or 0
    actual = expenses.filter(status=Expense.STATUS_APPROVED).aggregate(total=Sum("amount"))["total"] or 0
    remaining = planned - actual
    variance = planned - actual - committed
    return {
        "planned": planned, "committed": committed, "actual": actual,
        "remaining": remaining, "variance": variance, "has_budget": budget is not None,
    }


def project_workspace_summary(project, organisation):
    """Shared Project Workspace header figures (summary bar, every tab) --
    one place so Activities/Tasks/Budget/Spent/Evidence never drift
    between tabs. All real, live counts."""
    from apps.documents.models import Document
    from apps.impact.services import people_reached_for_project

    finance = project_finance_summary(project)
    evidence_count = Document.objects.filter(
        organisation=organisation, content_type=ContentType.objects.get_for_model(project.__class__),
        object_id=str(project.id), status=Document.STATUS_ACTIVE,
    ).count()
    return {
        "activity_count": project.activities.count(),
        "task_count": project.tasks.count(),
        "people_reached": people_reached_for_project(project),
        "budget_planned": finance["planned"],
        "budget_spent": finance["actual"],
        "evidence_count": evidence_count,
    }


def compute_project_progress(project):
    """Delivery progress, not setup completeness -- the share of this
    project's own activities that have actually been delivered. Indicators
    live at Programme level (they aren't scoped per-project), so this is
    the honest project-level equivalent rather than borrowing a Programme
    figure. Returns None ("no data yet") when the project has no
    activities at all, rather than a fabricated 0%."""
    total = project.activities.count()
    if not total:
        return None
    delivered = project.activities.filter(status="delivered").count()
    return round(delivered / total * 100, 1)


def compute_project_attention(project, organisation):
    """Actionable gaps, in priority order, capped at 6 -- mirrors
    apps.programmes.services.compute_programme_attention. Every item links
    to the real existing page that fixes it."""
    slug = organisation.slug
    items = []

    def add(condition, text, url):
        if condition:
            items.append({"text": text, "url": url})

    add(
        project.programme_id is None,
        "Link this project to a programme.",
        reverse("projects:edit", kwargs={"slug": slug, "project_id": project.id}),
    )
    add(
        not project.objective,
        "Describe what this project is trying to achieve.",
        reverse("projects:edit", kwargs={"slug": slug, "project_id": project.id}),
    )
    add(
        not project.manager_id,
        "Assign a project manager.",
        reverse("projects:edit", kwargs={"slug": slug, "project_id": project.id}),
    )
    add(
        not project.activities.exists(),
        "Add an activity.",
        reverse("projects:activities", kwargs={"slug": slug, "project_id": project.id}),
    )
    add(
        not getattr(project, "project_budget", None),
        "Set up this project's budget.",
        reverse("projects:budget", kwargs={"slug": slug, "project_id": project.id}),
    )

    activities_missing_attendance = project.activities.filter(
        status="delivered", attendance_records__isnull=True
    ).count()
    if activities_missing_attendance:
        noun = "activity has" if activities_missing_attendance == 1 else "activities have"
        add(
            True,
            f"{activities_missing_attendance} delivered {noun} no attendance recorded.",
            reverse("projects:activities", kwargs={"slug": slug, "project_id": project.id}),
        )

    return items[:6]
