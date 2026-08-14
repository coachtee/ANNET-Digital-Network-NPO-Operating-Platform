from django.db.models import Sum
from django.urls import reverse

from apps.expenses.models import Expense


def programme_budget_summary(programme):
    """Programme-level budget vs actual, rolled up from each of the
    programme's Projects -- reuses Project.budget and Expense as they
    already exist today. No Programme-level Budget model yet (that's the
    later Finance-phase generalisation); this is a live aggregate, not a
    stored figure.
    """
    projects = programme.projects.all()
    budget_total = projects.aggregate(total=Sum("budget"))["total"] or 0
    spent_total = Expense.objects.filter(
        project__in=projects, status=Expense.STATUS_APPROVED
    ).aggregate(total=Sum("amount"))["total"] or 0
    return {"budget": budget_total, "spent": spent_total, "remaining": budget_total - spent_total}


def compute_programme_progress(programme):
    """Delivery progress, not setup completeness -- the average achievement
    of the programme's own indicators (already-existing
    Indicator.achievement_percent property). Returns None (render as "no
    data yet") rather than a fabricated 0% when nothing has been measured.
    """
    values = [i.achievement_percent for i in programme.indicators.all() if i.achievement_percent is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def compute_programme_readiness(programme):
    """Minimum planning a Programme needs before Projects can be created
    under it -- a checklist, not a percentage. Funding is deliberately
    excluded: it's tracked separately and shouldn't block an otherwise
    well-planned Programme (see PROGRAMME_WORKSPACE_ARCHITECTURE_PROPOSAL.md
    and the UAT follow-up that added this gate)."""
    checks = [
        ("Programme defined", bool(programme.name)),
        ("Need identified", bool(programme.need_and_background)),
        ("Purpose defined", bool(programme.theory_of_change_summary)),
        ("Beneficiaries defined", bool(programme.target_beneficiary_groups)),
        ("Geography defined", bool(programme.locations) or bool(programme.province)),
        ("Outcome defined", programme.outcomes.exists()),
        ("Output defined", programme.outputs.filter(outcome__isnull=False).exists()),
        ("Indicator defined", programme.indicators.filter(output__isnull=False).exists()),
        ("Target defined", programme.indicators.exclude(target_value__isnull=True).exists()),
    ]
    missing = [label for label, met in checks if not met]

    # Recommended, not required -- shown alongside the gate but never
    # part of is_ready, so an unassigned team never blocks Project
    # creation the way a missing Outcome/Output/Indicator/Target does.
    has_manager = programme.team_memberships.filter(role="programme_manager", status="active").exists()
    recommended = [("Programme Manager assigned", has_manager)]

    return {
        "checks": checks, "missing": missing, "is_ready": not missing,
        "recommended": recommended, "recommended_missing": [label for label, met in recommended if not met],
    }


def compute_programme_attention(programme, organisation):
    """Actionable gaps, in priority order, capped at 6 -- combines setup
    completeness (no outcome/indicator/project/activity/funding yet) with
    live operational gaps (delivered activities with no attendance
    recorded). Every item links to the real existing page that fixes it.
    """
    slug = organisation.slug
    items = []

    def add(condition, text, url):
        if condition:
            items.append({"text": text, "url": url})

    add(
        not programme.description and not programme.need_and_background,
        "Describe why this programme exists.",
        reverse("programmes:plan", kwargs={"slug": slug, "programme_id": programme.id}),
    )
    add(
        not programme.outcomes.exists(),
        "Add a programme outcome.",
        reverse("monitoring_evaluation:programme_me", kwargs={"slug": slug, "programme_id": programme.id}),
    )
    add(
        not programme.indicators.exists(),
        "Define at least one measurable indicator.",
        reverse("monitoring_evaluation:programme_me", kwargs={"slug": slug, "programme_id": programme.id}),
    )
    add(
        not programme.projects.exists(),
        "Add a project.",
        reverse("programmes:detail", kwargs={"slug": slug, "programme_id": programme.id}) + "?tab=projects",
    )
    add(
        not programme.activities.exists(),
        "Add an activity.",
        reverse("programmes:activities", kwargs={"slug": slug, "programme_id": programme.id}),
    )
    add(
        not programme.grants.exists(),
        "Link a funding source.",
        reverse("programmes:plan", kwargs={"slug": slug, "programme_id": programme.id}),
    )

    activities_missing_attendance = programme.activities.filter(
        status="delivered", attendance_records__isnull=True
    ).count()
    if activities_missing_attendance:
        noun = "activity has" if activities_missing_attendance == 1 else "activities have"
        add(
            True,
            f"{activities_missing_attendance} delivered {noun} no attendance recorded.",
            reverse("programmes:activities", kwargs={"slug": slug, "programme_id": programme.id}),
        )

    return items[:6]
