from django.contrib import admin

from apps.resources.models import Resource


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ["title", "resource_type", "category", "status", "is_featured", "published_at"]
    list_filter = ["resource_type", "status", "is_featured"]
    search_fields = ["title", "category"]
