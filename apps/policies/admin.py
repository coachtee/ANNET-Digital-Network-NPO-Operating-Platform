from django.contrib import admin

from apps.policies.models import Policy, PolicyVersion


class PolicyVersionInline(admin.TabularInline):
    model = PolicyVersion
    extra = 0


@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
    list_display = ["name", "organisation", "category", "status", "next_review_date"]
    list_filter = ["category", "status"]
    search_fields = ["name", "organisation__legal_name"]
    inlines = [PolicyVersionInline]
