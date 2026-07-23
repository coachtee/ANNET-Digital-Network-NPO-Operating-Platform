from django.contrib import admin

from apps.compliance.models import ComplianceEvidence, ComplianceObligation, ComplianceRule, ComplianceStatusEvent


@admin.register(ComplianceRule)
class ComplianceRuleAdmin(admin.ModelAdmin):
    list_display = ["name", "authority", "frequency", "active", "last_verified_at", "version"]
    list_filter = ["authority", "frequency", "active"]
    search_fields = ["name", "authority", "description"]


class ComplianceStatusEventInline(admin.TabularInline):
    model = ComplianceStatusEvent
    extra = 0
    readonly_fields = ["status", "note", "actor", "created_at"]


@admin.register(ComplianceObligation)
class ComplianceObligationAdmin(admin.ModelAdmin):
    list_display = ["organisation", "rule", "status", "due_date"]
    list_filter = ["status", "rule__authority"]
    search_fields = ["organisation__legal_name", "rule__name"]
    inlines = [ComplianceStatusEventInline]


admin.site.register(ComplianceEvidence)
