from django import forms

from apps.core.validators import validate_upload_file
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
    supporting_document = forms.FileField(
        required=False,
        help_text="Resignation letter, board resolution or meeting minutes recording the resignation.",
    )

    class Meta:
        model = GovernanceOfficial
        fields = ["term_end", "resignation_note"]
        labels = {"term_end": "Resignation date"}
        widgets = {"term_end": forms.DateInput(attrs={"type": "date"}), "resignation_note": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["term_end"].required = True
        self.fields["resignation_note"].required = True
        self.fields["resignation_note"].label = "Resignation note / reason"

    def clean_supporting_document(self):
        uploaded_file = self.cleaned_data.get("supporting_document")
        if uploaded_file:
            validate_upload_file(uploaded_file)
        return uploaded_file


class GovernanceMeetingForm(forms.ModelForm):
    class Meta:
        model = GovernanceMeeting
        fields = ["meeting_type", "title", "scheduled_date", "location", "is_held"]
        widgets = {"scheduled_date": forms.DateTimeInput(attrs={"type": "datetime-local"})}


class ResolutionForm(forms.ModelForm):
    supporting_document = forms.FileField(required=False, help_text="The formal signed resolution document, if you have one.")

    class Meta:
        model = Resolution
        fields = ["reference_number", "text", "decision"]
        widgets = {"text": forms.Textarea(attrs={"rows": 3})}

    def clean_supporting_document(self):
        uploaded_file = self.cleaned_data.get("supporting_document")
        if uploaded_file:
            validate_upload_file(uploaded_file)
        return uploaded_file


class MinutesUploadForm(forms.Form):
    file = forms.FileField(label="Minutes document")

    def clean_file(self):
        uploaded_file = self.cleaned_data["file"]
        validate_upload_file(uploaded_file)
        return uploaded_file
