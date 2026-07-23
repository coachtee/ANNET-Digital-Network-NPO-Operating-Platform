from django import forms

from apps.core.validators import validate_upload_file
from apps.policies.models import Policy


class PolicyForm(forms.ModelForm):
    class Meta:
        model = Policy
        fields = ["name", "category", "owner", "approval_authority", "status", "approval_date", "next_review_date"]
        widgets = {
            "approval_date": forms.DateInput(attrs={"type": "date"}),
            "next_review_date": forms.DateInput(attrs={"type": "date"}),
        }


class PolicyVersionUploadForm(forms.Form):
    document_title = forms.CharField(max_length=255, label="Document title")
    file = forms.FileField(label="Policy document")
    approved_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    notes = forms.CharField(required=False, max_length=255)

    def clean_file(self):
        uploaded_file = self.cleaned_data["file"]
        validate_upload_file(uploaded_file)
        return uploaded_file
