from django.contrib import admin

from apps.memberships.models import MembershipApplication, MembershipStatusEvent


class MembershipStatusEventInline(admin.TabularInline):
    model = MembershipStatusEvent
    extra = 0
    readonly_fields = ["status", "note", "actor", "created_at"]


@admin.register(MembershipApplication)
class MembershipApplicationAdmin(admin.ModelAdmin):
    list_display = ["organisation", "status", "submitted_at", "decided_at", "decided_by"]
    list_filter = ["status"]
    search_fields = ["organisation__legal_name"]
    inlines = [MembershipStatusEventInline]
