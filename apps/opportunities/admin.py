from django.contrib import admin

from apps.opportunities.models import Opportunity


@admin.register(Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    list_display = ["title", "opportunity_type", "status", "opening_date", "closing_date"]
    list_filter = ["opportunity_type", "status"]
    search_fields = ["title"]
