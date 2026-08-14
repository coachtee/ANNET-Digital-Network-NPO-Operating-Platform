from django.db.models import Sum

from apps.attendance.models import AttendanceRecord


def _people_reached(attendance):
    named_reached = attendance.filter(beneficiary__isnull=False).values("beneficiary").distinct().count()
    anonymous_reached = attendance.filter(beneficiary__isnull=True).aggregate(total=Sum("headcount"))["total"] or 0
    return named_reached + anonymous_reached


def people_reached_for_organisation(organisation):
    """Named + anonymous headcount reach, live from attendance records
    (spec section 32/52 release blocker: no hard-coded dashboard numbers).
    Shared by the Impact Dashboard and the organisation workspace home so
    the two never drift out of sync with different formulas."""
    return _people_reached(AttendanceRecord.objects.filter(organisation=organisation))


def people_reached_for_programme(programme):
    """Same formula, scoped to one programme -- used by the Programme
    Workspace Overview so it never drifts from the organisation-wide
    figure it's a subset of."""
    return _people_reached(AttendanceRecord.objects.filter(programme=programme))
