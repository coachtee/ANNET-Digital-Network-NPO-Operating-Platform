from django import forms

from apps.core.validators import validate_upload_file
from apps.organisations.models import Organisation


class OrganisationIdentityForm(forms.ModelForm):
    class Meta:
        model = Organisation
        fields = [
            "legal_name", "trading_name", "organisation_type", "founding_date", "financial_year_end",
            "email", "phone_number", "website", "physical_address", "province", "municipality",
        ]
        widgets = {
            "founding_date": forms.DateInput(attrs={"type": "date"}),
            "financial_year_end": forms.TextInput(attrs={"placeholder": "MM-DD, e.g. 02-28"}),
            "physical_address": forms.Textarea(attrs={"rows": 3}),
        }


class OrganisationLegalForm(forms.ModelForm):
    class Meta:
        model = Organisation
        fields = ["legal_structure"]
        widgets = {"legal_structure": forms.RadioSelect}


class OrganisationRegistrationForm(forms.ModelForm):
    class Meta:
        model = Organisation
        fields = [
            "dsd_registered", "dsd_npo_number",
            "cipc_registered", "cipc_registration_number",
            "sars_pbo_approved", "sars_pbo_number",
            "section18a_approved", "section18a_number",
            "masters_office_registered", "masters_office_number",
        ]
        widgets = {
            "dsd_registered": forms.Select(choices=[(None, "Not sure / not yet"), (True, "Yes"), (False, "No")]),
            "cipc_registered": forms.Select(choices=[(None, "Not sure / not yet"), (True, "Yes"), (False, "No")]),
            "sars_pbo_approved": forms.Select(choices=[(None, "Not sure / not yet"), (True, "Yes"), (False, "No")]),
            "section18a_approved": forms.Select(choices=[(None, "Not sure / not yet"), (True, "Yes"), (False, "No")]),
            "masters_office_registered": forms.Select(choices=[(None, "Not sure / not yet"), (True, "Yes"), (False, "No")]),
        }


class OrganisationActivitiesForm(forms.Form):
    sectors = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Comma-separated, e.g. Education, Youth Development",
    )
    programme_areas = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    beneficiary_groups = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    sensitive_service_areas = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2}),
        help_text="e.g. child protection, GBV support: flags enhanced access controls",
    )

    @staticmethod
    def _to_list(value):
        return [v.strip() for v in value.split(",") if v.strip()]

    def save(self, organisation):
        organisation.sectors = self._to_list(self.cleaned_data["sectors"])
        organisation.programme_areas = self._to_list(self.cleaned_data["programme_areas"])
        organisation.beneficiary_groups = self._to_list(self.cleaned_data["beneficiary_groups"])
        organisation.sensitive_service_areas = self._to_list(self.cleaned_data["sensitive_service_areas"])
        organisation.save()


class OrganisationPublicProfileForm(forms.ModelForm):
    class Meta:
        model = Organisation
        fields = ["is_publicly_listed", "public_about", "public_logo", "public_show_impact", "public_show_contact"]
        widgets = {"public_about": forms.Textarea(attrs={"rows": 5})}

    def clean_public_logo(self):
        logo = self.cleaned_data.get("public_logo")
        if logo and hasattr(logo, "size"):
            validate_upload_file(logo)
        return logo
