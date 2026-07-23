from django.conf import settings
from django.core.files.storage import FileSystemStorage

# Private uploads (compliance evidence, board documents, financial records,
# beneficiary data) are stored OUTSIDE MEDIA_ROOT so they are never
# reachable through the public /media/ URL or default webserver static
# file handling. They are only ever served through an authenticated,
# permission-checked view (see apps.documents.views.download_document).
private_storage = FileSystemStorage(
    location=str(settings.PRIVATE_MEDIA_ROOT),
    base_url=None,
)
