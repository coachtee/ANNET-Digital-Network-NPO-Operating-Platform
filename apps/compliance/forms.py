from django import forms

from apps.compliance.models import ComplianceObligation


class ObligationStatusForm(forms.ModelForm):
    class Meta:
        model = ComplianceObligation
        fields = ["status", "responsible_user", "submitted_at", "submission_reference", "notes"]
        widgets = {
            "submitted_at": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, organisation=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organisation is not None:
            self.fields["responsible_user"].queryset = self.fields["responsible_user"].queryset.filter(
                organisation_memberships__organisation=organisation, organisation_memberships__is_active=True
            ).distinct()
