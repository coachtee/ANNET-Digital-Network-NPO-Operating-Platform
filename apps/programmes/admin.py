from django.contrib import admin

from apps.programmes.models import Activity, Programme


class ActivityInline(admin.TabularInline):
    model = Activity
    extra = 0


@admin.register(Programme)
class ProgrammeAdmin(admin.ModelAdmin):
    list_display = ["name", "organisation", "programme_area", "status"]
    list_filter = ["status"]
    search_fields = ["name", "organisation__legal_name"]
    inlines = [ActivityInline]
