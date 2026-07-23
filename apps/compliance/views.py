from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.audit.services import log_action
from apps.compliance.forms import ObligationStatusForm
from apps.compliance.models import ComplianceEvidence, ComplianceObligation, ComplianceStatusEvent
from apps.compliance.services import sync_obligations_for_organisation
from apps.core.permissions import has_org_capability
from apps.documents.forms import DocumentUploadForm
from apps.organisations.services import get_organisation_or_404_for_user


@login_required
def passport(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    sync_obligations_for_organisation(organisation)
    obligations = organisation.compliance_obligations.select_related("rule").order_by("rule__authority", "due_date")

    authority_filter = request.GET.get("authority")
    if authority_filter:
        obligations = obligations.filter(rule__authority=authority_filter)

    authorities = organisation.compliance_obligations.values_list("rule__authority", flat=True).distinct()
    context = {
        "organisation": organisation, "obligations": obligations, "authorities": authorities,
        "authority_filter": authority_filter,
    }
    return render(request, "compliance/passport.html", context)


@login_required
def calendar(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    today = timezone.now().date()
    obligations = organisation.compliance_obligations.select_related("rule")
    context = {
        "organisation": organisation,
        "overdue": obligations.filter(due_date__lt=today).exclude(
            status__in=ComplianceObligation.READINESS_STATUSES
        ).order_by("due_date"),
        "upcoming": obligations.filter(due_date__gte=today).exclude(
            status__in=ComplianceObligation.READINESS_STATUSES
        ).order_by("due_date"),
        "completed": obligations.filter(status__in=ComplianceObligation.READINESS_STATUSES).order_by("-due_date"),
    }
    return render(request, "compliance/calendar.html", context)


@login_required
def obligation_detail(request, slug, obligation_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    obligation = get_object_or_404(ComplianceObligation, id=obligation_id, organisation=organisation)
    if not has_org_capability(request.user, organisation, "compliance.view"):
        raise PermissionDenied

    can_manage = has_org_capability(request.user, organisation, "compliance.manage")
    status_form = ObligationStatusForm(instance=obligation, organisation=organisation)
    evidence_form = DocumentUploadForm(initial={"visibility": "private"})

    if request.method == "POST" and can_manage:
        if "update_status" in request.POST:
            status_form = ObligationStatusForm(request.POST, instance=obligation, organisation=organisation)
            if status_form.is_valid():
                old_status = obligation.status
                obligation = status_form.save()
                if obligation.status != old_status:
                    ComplianceStatusEvent.objects.create(
                        obligation=obligation, status=obligation.status, actor=request.user,
                        note=f"Changed from {old_status} to {obligation.status}",
                    )
                    log_action("compliance.status_changed", organisation=organisation, obj=obligation, actor=request.user,
                               changes={"from": old_status, "to": obligation.status})
                messages.success(request, "Obligation updated.")
                return redirect("compliance:obligation_detail", slug=slug, obligation_id=obligation.id)
        elif "upload_evidence" in request.POST:
            evidence_form = DocumentUploadForm(request.POST, request.FILES)
            if evidence_form.is_valid():
                document = evidence_form.save(commit=False)
                document.organisation = organisation
                document.uploaded_by = request.user
                document.visibility = "private"
                document.save()
                ComplianceEvidence.objects.create(obligation=obligation, document=document, uploaded_by=request.user)
                if obligation.status not in ComplianceObligation.READINESS_STATUSES:
                    obligation.status = ComplianceObligation.STATUS_EVIDENCE_RECORDED
                    obligation.save(update_fields=["status"])
                    ComplianceStatusEvent.objects.create(obligation=obligation, status=obligation.status, actor=request.user, note="Evidence uploaded")
                log_action("compliance.evidence_uploaded", organisation=organisation, obj=obligation, actor=request.user)
                messages.success(request, "Evidence uploaded.")
                return redirect("compliance:obligation_detail", slug=slug, obligation_id=obligation.id)

    context = {
        "organisation": organisation, "obligation": obligation, "status_form": status_form,
        "evidence_form": evidence_form, "can_manage": can_manage,
        "evidence_items": obligation.evidence_items.select_related("document"),
        "status_events": obligation.status_events.select_related("actor"),
    }
    return render(request, "compliance/obligation_detail.html", context)
