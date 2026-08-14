from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.audit.services import log_action
from apps.core.permissions import has_org_capability
from apps.documents.forms import DocumentNewVersionForm, DocumentUploadForm
from apps.documents.models import Document
from apps.organisations.services import get_organisation_or_404_for_user


@login_required
def document_list(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    show_archived = request.GET.get("show") == "archived"
    status = Document.STATUS_ARCHIVED if show_archived else Document.STATUS_ACTIVE
    documents = organisation.documents.select_related("uploaded_by").filter(status=status)
    category = request.GET.get("category")
    if category:
        documents = documents.filter(category=category)
    return render(request, "documents/list.html", {
        "organisation": organisation, "documents": documents, "show_archived": show_archived, "category": category,
    })


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


def _can_view_document(user, organisation, document):
    if document.visibility == Document.VISIBILITY_PRIVATE:
        return has_org_capability(user, organisation, "documents.manage")
    return has_org_capability(user, organisation, "documents.view")


@login_required
def document_detail(request, slug, document_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    document = get_object_or_404(Document, id=document_id, organisation=organisation)
    if not _can_view_document(request.user, organisation, document):
        raise PermissionDenied
    history = []
    node = document
    while node.supersedes_id:
        node = node.supersedes
        history.append(node)
    return render(request, "documents/detail.html", {
        "organisation": organisation, "document": document,
        "can_manage": has_org_capability(request.user, organisation, "documents.manage"),
        "version_history": history, "related_object": document.related_object,
        "new_version_form": DocumentNewVersionForm(),
    })


@login_required
def download_document(request, slug, document_id):
    """Every private-file download re-checks organisation membership here —
    files are never reachable through a public /media/ URL (spec section
    22/38/52) -- plus, for VISIBILITY_PRIVATE documents specifically, that
    the requester holds documents.manage rather than just documents.view,
    since "Private (restricted roles only)" is meant to be narrower than
    "every org member with view access" (previously unenforced).
    """
    organisation = get_organisation_or_404_for_user(request.user, slug)
    document = get_object_or_404(Document, id=document_id, organisation=organisation)
    if not _can_view_document(request.user, organisation, document):
        raise PermissionDenied
    if not document.file:
        raise Http404
    log_action("document.downloaded", organisation=organisation, obj=document, actor=request.user)
    return FileResponse(document.file.open("rb"), as_attachment=True, filename=document.file.name.split("/")[-1])


@login_required
@require_POST
def archive_document(request, slug, document_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    if not has_org_capability(request.user, organisation, "documents.manage"):
        raise PermissionDenied
    document = get_object_or_404(Document, id=document_id, organisation=organisation)
    document.status = Document.STATUS_ARCHIVED
    document.save(update_fields=["status"])
    log_action("document.archived", organisation=organisation, obj=document, actor=request.user)
    messages.success(request, "Document archived.")
    return redirect("documents:list", slug=slug)


@login_required
def new_version(request, slug, document_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    if not has_org_capability(request.user, organisation, "documents.manage"):
        raise PermissionDenied
    current = get_object_or_404(Document, id=document_id, organisation=organisation)
    form = DocumentNewVersionForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        new_document = Document.objects.create(
            organisation=organisation, title=current.title, category=current.category,
            description=current.description, file=form.cleaned_data["file"], visibility=current.visibility,
            uploaded_by=request.user, version=current.version + 1, supersedes=current,
            content_type=current.content_type, object_id=current.object_id,
        )
        current.status = Document.STATUS_ARCHIVED
        current.save(update_fields=["status"])
        log_action("document.new_version", organisation=organisation, obj=new_document, actor=request.user)
        messages.success(request, f"Version {new_document.version} uploaded.")
        return redirect("documents:detail", slug=slug, document_id=new_document.id)
    return render(request, "documents/new_version.html", {"organisation": organisation, "document": current, "form": form})
