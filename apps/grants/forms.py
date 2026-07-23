from django import forms

from apps.grants.models import Grant


class GrantForm(forms.ModelForm):
    class Meta:
        model = Grant
        fields = [
            "funder_name", "name", "description", "amount", "currency",
            "funding_start", "funding_end", "reporting_requirements", "restrictions",
            "responsible_manager", "status",
        ]
        widgets = {
            "funding_start": forms.DateInput(attrs={"type": "date"}),
            "funding_end": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3}),
            "reporting_requirements": forms.Textarea(attrs={"rows": 2}),
            "restrictions": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, organisation=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organisation is not None:
            self.fields["responsible_manager"].queryset = self.fields["responsible_manager"].queryset.filter(
                organisation_memberships__organisation=organisation, organisation_memberships__is_active=True
            ).distinct()
