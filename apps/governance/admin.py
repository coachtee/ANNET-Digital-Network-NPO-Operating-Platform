from django.contrib import admin

from apps.governance.models import (
    ConflictOfInterestDeclaration, GovernanceMeeting, GovernanceOfficial, MeetingAttendance, Resolution,
)


@admin.register(GovernanceOfficial)
class GovernanceOfficialAdmin(admin.ModelAdmin):
    list_display = ["full_name", "organisation", "position", "status", "term_start", "term_end"]
    list_filter = ["position", "status"]
    search_fields = ["full_name", "organisation__legal_name"]


@admin.register(GovernanceMeeting)
class GovernanceMeetingAdmin(admin.ModelAdmin):
    list_display = ["organisation", "meeting_type", "scheduled_date", "is_held"]
    list_filter = ["meeting_type", "is_held"]


admin.site.register(MeetingAttendance)
admin.site.register(Resolution)
admin.site.register(ConflictOfInterestDeclaration)
