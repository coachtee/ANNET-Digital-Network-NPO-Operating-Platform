from django import forms

from apps.beneficiaries.models import Beneficiary


class BeneficiaryForm(forms.ModelForm):
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
