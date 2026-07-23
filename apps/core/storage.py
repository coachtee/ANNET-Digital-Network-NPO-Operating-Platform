from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateFileSystemStorage(FileSystemStorage):
    """Storage for files that must never be reachable by a guessable public
    URL (compliance evidence, board documents, expense receipts, beneficiary
    evidence). Files live under PRIVATE_MEDIA_ROOT — a directory entirely
    separate from MEDIA_ROOT — and are only ever served through an
    authenticated, permission-checked view.

    Passing base_url=None to the base FileSystemStorage does NOT disable
    URL generation — Django silently falls back to MEDIA_URL, which would
    make `{{ document.file.url }}` render a plausible-looking (and
    misleading) public link. Overriding url() to always raise makes any
    accidental direct use of .url fail loudly instead of producing a
    dead or unsafe link (spec section 22/38/52).
    """

    def url(self, name):
        raise NotImplementedError(
            "Private files have no public URL. Serve them through an authenticated, "
            "permission-checked download view instead of .url."
        )


private_storage = PrivateFileSystemStorage(location=str(settings.PRIVATE_MEDIA_ROOT))
