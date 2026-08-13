from django import forms
from django.utils import timezone

from apps.core.validators import validate_upload_file
from apps.resources.models import Resource


class ResourceForm(forms.ModelForm):
    class Meta:
        model = Resource
        fields = [
            "title", "resource_type", "category", "description",
            "file", "external_url", "status", "is_featured",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def clean_file(self):
        file = self.cleaned_data.get("file")
        if file and hasattr(file, "size"):
            validate_upload_file(file)
        return file

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("file") and not cleaned.get("external_url") and not (self.instance and self.instance.file):
            raise forms.ValidationError("Add a file or an external URL: a resource needs somewhere for members to actually reach it.")
        return cleaned

    def save(self, commit=True):
        resource = super().save(commit=False)
        if resource.status == Resource.STATUS_PUBLISHED and not resource.published_at:
            resource.published_at = timezone.now()
        if commit:
            resource.save()
        return resource
