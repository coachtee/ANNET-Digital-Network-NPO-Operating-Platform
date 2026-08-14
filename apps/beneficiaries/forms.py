from django import forms

from apps.beneficiaries.models import Beneficiary


class BeneficiaryForm(forms.ModelForm):
    # Ordered for the two-column form grid: identity first, then contact
    # and record-keeping detail, then the consent/sensitivity flags.
    field_order = [
        "first_name", "last_name", "date_of_birth", "gender",
        "contact_number", "reference_code", "programme", "mode",
        "is_sensitive", "consent_recorded",
    ]

    class Meta:
        model = Beneficiary
        fields = [
            "programme", "mode", "first_name", "last_name", "date_of_birth", "gender",
            "contact_number", "is_sensitive", "consent_recorded", "reference_code",
        ]
        widgets = {"date_of_birth": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, organisation=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organisation is not None:
            self.fields["programme"].queryset = organisation.programmes.all()
