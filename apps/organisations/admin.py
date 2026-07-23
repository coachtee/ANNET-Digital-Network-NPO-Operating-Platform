from django.contrib import admin

from apps.organisations.models import Organisation, OrganisationMembership


class OrganisationMembershipInline(admin.TabularInline):
    model = OrganisationMembership
    extra = 0
    autocomplete_fields = ["user"]


@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    list_display = ["legal_name", "organisation_type", "province", "is_publicly_listed", "onboarding_step", "created_at"]
    list_filter = ["organisation_type", "province", "is_publicly_listed", "legal_structure"]
    search_fields = ["legal_name", "trading_name", "dsd_npo_number", "cipc_registration_number"]
    prepopulated_fields = {"slug": ["legal_name"]}
    inlines = [OrganisationMembershipInline]


@admin.register(OrganisationMembership)
class OrganisationMembershipAdmin(admin.ModelAdmin):
    list_display = ["organisation", "user", "role", "is_active", "joined_at"]
    list_filter = ["role", "is_active"]
    autocomplete_fields = ["organisation", "user"]
