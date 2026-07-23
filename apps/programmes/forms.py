from django import forms

from apps.programmes.models import Activity, Programme


class ProgrammeForm(forms.ModelForm):
    sectors_help = "Comma-separated"

    class Meta:
        model = Programme
        fields = ["name", "description", "programme_area", "theory_of_change_summary", "status", "grants"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "theory_of_change_summary": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, organisation=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organisation is not None:
            self.fields["grants"].queryset = organisation.grants.all()


class ActivityForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = ["name", "scheduled_date", "location", "status"]
        widgets = {"scheduled_date": forms.DateInput(attrs={"type": "date"})}
