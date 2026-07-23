from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.attendance.forms import AttendanceForm, KioskLaunchForm
from apps.attendance.models import AttendanceRecord, KioskSession
from apps.audit.services import log_action
from apps.core.permissions import has_org_capability
from apps.organisations.services import get_organisation_or_404_for_user


@login_required
def attendance_list(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    if not has_org_capability(request.user, organisation, "attendance.view"):
        raise PermissionDenied
    records = organisation.attendance_records.select_related("programme", "activity", "beneficiary").order_by("-attendance_date")[:200]
    return render(request, "attendance/list.html", {
        "organisation": organisation, "records": records,
        "can_manage": has_org_capability(request.user, organisation, "attendance.manage"),
    })


@login_required
def record_attendance(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    if not has_org_capability(request.user, organisation, "attendance.manage"):
        raise PermissionDenied
    form = AttendanceForm(request.POST or None, organisation=organisation)
    if request.method == "POST" and form.is_valid():
        record = form.save(commit=False)
        record.organisation = organisation
        record.recorded_by = request.user
        record.save()
        log_action("attendance.recorded", organisation=organisation, obj=record, actor=request.user)
        messages.success(request, "Attendance recorded.")
        return redirect("attendance:list", slug=slug)
    return render(request, "attendance/record_form.html", {"organisation": organisation, "form": form})


@login_required
def kiosk_launch(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    if not has_org_capability(request.user, organisation, "attendance.manage"):
        raise PermissionDenied
    form = KioskLaunchForm(request.POST or None, organisation=organisation)
    session = None
    if request.method == "POST" and form.is_valid():
        session = KioskSession.objects.create(
            organisation=organisation, programme=form.cleaned_data["programme"], created_by=request.user,
            expires_at=timezone.now() + timedelta(hours=form.cleaned_data["hours_valid"]),
        )
        log_action("attendance.kiosk_launched", organisation=organisation, obj=session, actor=request.user)
    return render(request, "attendance/kiosk_launch.html", {"organisation": organisation, "form": form, "session": session})


def kiosk_entry(request, token):
    """Public, unauthenticated, tokenised kiosk check-in — no admin
    navigation or organisation data beyond the single linked programme is
    ever exposed here (spec section 28)."""
    session = get_object_or_404(KioskSession, token=token)
    if not session.is_valid:
        return render(request, "attendance/kiosk_expired.html", {}, status=403)

    confirmation = None
    if request.method == "POST":
        AttendanceRecord.objects.create(
            organisation=session.organisation, programme=session.programme,
            headcount=1, attendance_date=timezone.now().date(), check_in_method=AttendanceRecord.METHOD_KIOSK,
        )
        confirmation = True

    return render(request, "attendance/kiosk_entry.html", {"session": session, "confirmation": confirmation})
