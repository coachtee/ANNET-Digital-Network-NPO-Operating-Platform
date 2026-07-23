from django import forms

from apps.monitoring_evaluation.models import Indicator, IndicatorPeriodValue, Outcome, Output


class OutcomeForm(forms.ModelForm):
    class Meta:
        model = Outcome
        fields = ["title", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}


class OutputForm(forms.ModelForm):
    class Meta:
        model = Output
        fields = ["title", "description", "outcome"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, programme=None, **kwargs):
        super().__init__(*args, **kwargs)
        if programme is not None:
            self.fields["outcome"].queryset = programme.outcomes.all()


class IndicatorForm(forms.ModelForm):
    class Meta:
        model = Indicator
        fields = ["name", "indicator_type", "unit", "outcome", "output", "baseline_value", "target_value", "auto_from_attendance"]

    def __init__(self, *args, programme=None, **kwargs):
        super().__init__(*args, **kwargs)
        if programme is not None:
            self.fields["outcome"].queryset = programme.outcomes.all()
            self.fields["output"].queryset = programme.outputs.all()


class IndicatorPeriodValueForm(forms.ModelForm):
    class Meta:
        model = IndicatorPeriodValue
        fields = ["period_start", "period_end", "actual_value", "means_of_verification", "notes"]
        widgets = {
            "period_start": forms.DateInput(attrs={"type": "date"}),
            "period_end": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }
