from django import forms

from apps.governance.models import GovernanceMeeting, GovernanceOfficial, Resolution


class GovernanceOfficialForm(forms.ModelForm):
    class Meta:
        model = GovernanceOfficial
        fields = ["full_name", "position", "email", "phone_number", "term_start", "term_end"]
        widgets = {
            "term_start": forms.DateInput(attrs={"type": "date"}),
            "term_end": forms.DateInput(attrs={"type": "date"}),
        }


class GovernanceOfficialResignForm(forms.ModelForm):
    class Meta:
        model = GovernanceOfficial
        fields = ["resignation_note", "term_end"]
        widgets = {"term_end": forms.DateInput(attrs={"type": "date"}), "resignation_note": forms.Textarea(attrs={"rows": 3})}


class GovernanceMeetingForm(forms.ModelForm):
    class Meta:
        model = GovernanceMeeting
        fields = ["meeting_type", "title", "scheduled_date", "location", "is_held"]
        widgets = {"scheduled_date": forms.DateTimeInput(attrs={"type": "datetime-local"})}


class ResolutionForm(forms.ModelForm):
    class Meta:
        model = Resolution
        fields = ["text", "decision"]
        widgets = {"text": forms.Textarea(attrs={"rows": 3})}
