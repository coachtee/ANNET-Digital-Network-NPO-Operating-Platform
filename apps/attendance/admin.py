from django.contrib import admin

from apps.attendance.models import AttendanceRecord, KioskSession


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ["programme", "activity", "beneficiary", "headcount", "attendance_date", "check_in_method"]
    list_filter = ["check_in_method"]


@admin.register(KioskSession)
class KioskSessionAdmin(admin.ModelAdmin):
    list_display = ["programme", "organisation", "expires_at", "is_active"]
