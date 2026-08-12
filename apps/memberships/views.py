from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.audit.services import log_action
from apps.core.permissions import has_network_capability
from apps.memberships.forms import ApplicationDecisionForm, ApplicationMotivationForm
from apps.memberships.models import MembershipApplication, MembershipStatusEvent
from apps.networks.services import get_primary_network
from apps.organisations.services import get_organisation_or_404_for_user


@login_required
def apply(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    application = organisation.network_memberships.order_by("-created_at").first()

    can_submit = application is None or application.status in [
        MembershipApplication.STATUS_DRAFT, MembershipApplication.STATUS_DECLINED,
        MembershipApplication.STATUS_WITHDRAWN, MembershipApplication.STATUS_INFORMATION_REQUESTED,
    ]

    form = None
    if can_submit:
        instance = application if application and application.status not in [
            MembershipApplication.STATUS_DECLINED, MembershipApplication.STATUS_WITHDRAWN
        ] else None
        form = ApplicationMotivationForm(request.POST or None, instance=instance)
        if request.method == "POST" and form.is_valid():
            new_application = form.save(commit=False)
            new_application.organisation = organisation
            new_application.status = MembershipApplication.STATUS_SUBMITTED
            new_application.submitted_at = timezone.now()
            new_application.save()
            MembershipStatusEvent.objects.create(application=new_application, status=new_application.status, actor=request.user, note="Application submitted")
            log_action("membership.application_submitted", organisation=organisation, obj=new_application, actor=request.user)
            messages.success(request, "Your membership application has been submitted.")
            return redirect("memberships:apply", slug=slug)

    context = {
        "organisation": organisation, "application": application, "form": form,
        "status_events": application.status_events.select_related("actor") if application else [],
    }
    return render(request, "memberships/apply.html", context)


def _require_network_reviewer(request):
    network = get_primary_network()
    if not (request.user.is_platform_admin or has_network_capability(request.user, network, "membership.review")):
        raise PermissionDenied
    return network


@login_required
def queue(request):
    network = _require_network_reviewer(request)
    applications = MembershipApplication.objects.select_related("organisation").filter(
        status__in=[MembershipApplication.STATUS_SUBMITTED, MembershipApplication.STATUS_INFORMATION_REQUESTED]
    ).order_by("submitted_at")
    return render(request, "memberships/queue.html", {"network": network, "applications": applications})


@login_required
def application_detail(request, application_id):
    network = _require_network_reviewer(request)
    application = get_object_or_404(MembershipApplication, id=application_id)
    can_decide = request.user.is_platform_admin or has_network_capability(request.user, network, "membership.decide")

    form = ApplicationDecisionForm()
    if request.method == "POST" and can_decide:
        form = ApplicationDecisionForm(request.POST)
        if form.is_valid():
            application.status = form.cleaned_data["status"]
            application.internal_notes = (application.internal_notes + "\n" + form.cleaned_data["note"]).strip()
            if application.status in [MembershipApplication.STATUS_APPROVED, MembershipApplication.STATUS_DECLINED]:
                application.decided_at = timezone.now()
                application.decided_by = request.user
            application.save()
            MembershipStatusEvent.objects.create(
                application=application, status=application.status, actor=request.user, note=form.cleaned_data["note"]
            )
            log_action("membership.decision", organisation=application.organisation, obj=application, actor=request.user,
                       changes={"status": application.status})
            messages.success(request, "Decision recorded.")
            return redirect("memberships:queue")

    context = {
        "network": network, "application": application, "form": form, "can_decide": can_decide,
        "status_events": application.status_events.select_related("actor"),
    }
    return render(request, "memberships/application_detail.html", context)
