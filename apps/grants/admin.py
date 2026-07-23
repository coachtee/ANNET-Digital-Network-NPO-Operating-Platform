from django.contrib import admin

from apps.grants.models import Grant


@admin.register(Grant)
class GrantAdmin(admin.ModelAdmin):
    list_display = ["name", "organisation", "funder_name", "amount", "status"]
    list_filter = ["status"]
    search_fields = ["name", "funder_name", "organisation__legal_name"]
