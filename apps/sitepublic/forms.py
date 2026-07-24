from django import forms

from apps.organisations.models import ORGANISATION_TYPE_CHOICES, PROVINCE_CHOICES

VERIFICATION_STATUS_CHOICES = [
    ("", "Any Registration Status"),
    ("verified", "Verified"),
    ("unverified", "Unverified"),
]


class DirectorySearchForm(forms.Form):
    q = forms.CharField(required=False, label="Search", widget=forms.TextInput(
        attrs={"placeholder": "Organisation name…"}
    ))
    province = forms.ChoiceField(required=False, choices=[("", "All Provinces")] + PROVINCE_CHOICES)
    sector = forms.ChoiceField(required=False, choices=[("", "All Sectors")])
    organisation_type = forms.ChoiceField(required=False, choices=[("", "All Types")] + ORGANISATION_TYPE_CHOICES)
    verification_status = forms.ChoiceField(required=False, choices=VERIFICATION_STATUS_CHOICES)
    annet_member = forms.ChoiceField(required=False, choices=[("", "All"), ("1", "ANNET Members Only")])

    def __init__(self, *args, sector_choices=(), **kwargs):
        super().__init__(*args, **kwargs)
        if sector_choices:
            self.fields["sector"].choices = [("", "All Sectors")] + list(sector_choices)
