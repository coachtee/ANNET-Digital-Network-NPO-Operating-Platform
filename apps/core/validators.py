import os

from django.conf import settings
from django.core.exceptions import ValidationError


def validate_upload_file(uploaded_file):
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in settings.ALLOWED_UPLOAD_EXTENSIONS:
        raise ValidationError(f"File type '{ext}' is not allowed.")
    if uploaded_file.size > settings.MAX_UPLOAD_SIZE_BYTES:
        max_mb = settings.MAX_UPLOAD_SIZE_BYTES / (1024 * 1024)
        raise ValidationError(f"File exceeds the maximum allowed size of {max_mb:.0f}MB.")
