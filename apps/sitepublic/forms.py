from django import forms

from apps.organisations.models import ORGANISATION_TYPE_CHOICES, PROVINCE_CHOICES


class DirectorySearchForm(forms.Form):
    q = forms.CharField(required=False, label="Search")
    province = forms.ChoiceField(required=False, choices=[("", "All Provinces")] + PROVINCE_CHOICES)
    organisation_type = forms.ChoiceField(required=False, choices=[("", "All Types")] + ORGANISATION_TYPE_CHOICES)
    annet_member = forms.ChoiceField(required=False, choices=[("", "All"), ("1", "ANNET Members Only")])
