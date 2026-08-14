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


def people_reached_for_project(project):
    """Same formula again, scoped to one project via its own activities --
    Beneficiary/AttendanceRecord have no direct project FK, so this reaches
    the project's reach through the activities it actually ran."""
    return _people_reached(AttendanceRecord.objects.filter(activity__project=project))


def beneficiaries_for_project(project):
    """The distinct named beneficiaries who attended one of this project's
    activities -- used by the Project Workspace's People tab. Anonymous
    headcount entries aren't individually listable, only counted (see
    people_reached_for_project)."""
    from apps.beneficiaries.models import Beneficiary

    return Beneficiary.objects.filter(
        attendance_records__activity__project=project
    ).distinct()
