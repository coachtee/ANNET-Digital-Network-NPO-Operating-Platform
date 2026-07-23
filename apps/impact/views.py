from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render

from apps.attendance.models import AttendanceRecord
from apps.grants.models import Grant
from apps.monitoring_evaluation.models import Indicator
from apps.organisations.services import get_organisation_or_404_for_user
from apps.programmes.models import Activity


@login_required
def impact_dashboard(request, slug):
    """Every figure here is derived live from platform records — nothing
    is a hard-coded dashboard number (spec section 32/52 release blocker).
    """
    organisation = get_organisation_or_404_for_user(request.user, slug)

    programmes = organisation.programmes.all()
    active_programmes = programmes.filter(status="active").count()

    attendance = AttendanceRecord.objects.filter(organisation=organisation)
    named_reached = attendance.filter(beneficiary__isnull=False).values("beneficiary").distinct().count()
    anonymous_reached = attendance.filter(beneficiary__isnull=True).aggregate(total=Sum("headcount"))["total"] or 0
    people_reached = named_reached + anonymous_reached

    activities_delivered = Activity.objects.filter(programme__organisation=organisation, status="delivered").count()

    indicators = Indicator.objects.filter(programme__organisation=organisation)
    achievement_values = [i.achievement_percent for i in indicators if i.achievement_percent is not None]
    target_achievement = round(sum(achievement_values) / len(achievement_values), 1) if achievement_values else None

    funding_under_management = Grant.objects.filter(
        organisation=organisation, status__in=[Grant.STATUS_ACTIVE, Grant.STATUS_AGREEMENT, Grant.STATUS_REPORTING]
    ).aggregate(total=Sum("amount"))["total"] or 0

    obligations = organisation.compliance_obligations.all()
    total_obligations = obligations.count()
    from apps.compliance.models import ComplianceObligation
    ready_obligations = obligations.filter(status__in=ComplianceObligation.READINESS_STATUSES).count()
    reporting_readiness = round((ready_obligations / total_obligations) * 100) if total_obligations else None

    context = {
        "organisation": organisation,
        "active_programmes": active_programmes,
        "people_reached": people_reached,
        "activities_delivered": activities_delivered,
        "target_achievement": target_achievement,
        "funding_under_management": funding_under_management,
        "reporting_readiness": reporting_readiness,
        "indicators": indicators.select_related("programme")[:15],
    }
    return render(request, "impact/dashboard.html", context)
