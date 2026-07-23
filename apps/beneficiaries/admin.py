from django.contrib import admin

from apps.beneficiaries.models import Beneficiary


@admin.register(Beneficiary)
class BeneficiaryAdmin(admin.ModelAdmin):
    list_display = ["__str__", "organisation", "programme", "mode", "is_sensitive"]
    list_filter = ["mode", "is_sensitive"]
