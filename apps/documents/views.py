from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from apps.audit.services import log_action
from apps.core.permissions import has_org_capability
from apps.documents.forms import DocumentUploadForm
from apps.documents.models import Document
from apps.organisations.services import get_organisation_or_404_for_user


@login_required
def document_list(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    documents = organisation.documents.select_related("uploaded_by").all()
    return render(request, "documents/list.html", {"organisation": organisation, "documents": documents})


@login_required
def upload_document(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    if not has_org_capability(request.user, organisation, "documents.manage"):
        raise PermissionDenied
    form = DocumentUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        document = form.save(commit=False)
        document.organisation = organisation
        document.uploaded_by = request.user
        document.save()
        log_action("document.uploaded", organisation=organisation, obj=document, actor=request.user)
        messages.success(request, "Document uploaded.")
        return redirect("documents:list", slug=slug)
    return render(request, "documents/upload.html", {"organisation": organisation, "form": form})


@login_required
def download_document(request, slug, document_id):
    """Every private-file download re-checks organisation membership here —
    files are never reachable through a public /media/ URL (spec section 22/38/52).
    """
    organisation = get_organisation_or_404_for_user(request.user, slug)
    document = get_object_or_404(Document, id=document_id, organisation=organisation)
    if not has_org_capability(request.user, organisation, "documents.view"):
        raise PermissionDenied
    if not document.file:
        raise Http404
    log_action("document.downloaded", organisation=organisation, obj=document, actor=request.user)
    return FileResponse(document.file.open("rb"), as_attachment=True, filename=document.file.name.split("/")[-1])
