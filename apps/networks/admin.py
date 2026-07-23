from django.contrib import admin

from apps.networks.models import Network, NetworkStaffRole


class NetworkStaffRoleInline(admin.TabularInline):
    model = NetworkStaffRole
    extra = 0
    autocomplete_fields = ["user"]


@admin.register(Network)
class NetworkAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    prepopulated_fields = {"slug": ["name"]}
    inlines = [NetworkStaffRoleInline]
