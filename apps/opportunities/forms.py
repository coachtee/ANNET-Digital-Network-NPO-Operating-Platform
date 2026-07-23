from django import forms

from apps.opportunities.models import Opportunity


class OpportunityForm(forms.ModelForm):
    class Meta:
        model = Opportunity
        fields = [
            "title", "opportunity_type", "description", "eligibility",
            "opening_date", "closing_date", "location", "external_url", "status",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "eligibility": forms.Textarea(attrs={"rows": 3}),
            "opening_date": forms.DateInput(attrs={"type": "date"}),
            "closing_date": forms.DateInput(attrs={"type": "date"}),
        }
