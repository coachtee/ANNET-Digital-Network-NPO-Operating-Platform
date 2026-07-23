from django import forms

from apps.core.validators import validate_upload_file
from apps.documents.models import Document


class DocumentUploadForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ["title", "file", "visibility"]

    def clean_file(self):
        uploaded_file = self.cleaned_data["file"]
        validate_upload_file(uploaded_file)
        return uploaded_file
