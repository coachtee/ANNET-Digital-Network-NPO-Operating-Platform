from django.contrib import admin

from apps.projects.models import Project, ProjectTask


class ProjectTaskInline(admin.TabularInline):
    model = ProjectTask
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["name", "organisation", "grant", "programme", "status", "manager"]
    list_filter = ["status"]
    search_fields = ["name", "organisation__legal_name"]
    inlines = [ProjectTaskInline]
