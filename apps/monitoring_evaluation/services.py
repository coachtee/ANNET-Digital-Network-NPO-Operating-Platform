from django.db.models import Sum


def attendance_count_for_period(programme, period_start, period_end):
    """Sums AttendanceRecord.effective_count for a programme within a date
    range — used to pre-fill an actual value for indicators that opted in
    via ``auto_from_attendance`` (spec section 29). Named-beneficiary rows
    count as 1 each; anonymous rows use their captured headcount.
    """
    records = programme.attendance_records.filter(attendance_date__gte=period_start, attendance_date__lte=period_end)
    named = records.filter(beneficiary__isnull=False).count()
    anonymous = records.filter(beneficiary__isnull=True).aggregate(total=Sum("headcount"))["total"] or 0
    return named + anonymous
