from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.audit.services import log_action
from apps.core.permissions import has_network_capability
from apps.memberships.forms import ApplicationDecisionForm, ApplicationMotivationForm
from apps.memberships.models import MembershipApplication, MembershipStatusEvent
from apps.networks.models import Network
from apps.networks.services import get_primary_network
from apps.organisations.services import get_organisation_or_404_for_user


def _apply(request, organisation, network):
    """Shared by apply() (the platform's own network) and
    apply_to_network() (any other network/programme, e.g. Black Sash) — the
    workflow is identical regardless of which network is being applied to,
    which is the point: nothing here is Black-Sash- or Bohlale-Impact-
    specific."""
    application = organisation.network_memberships.filter(network=network).order_by("-created_at").first()

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
            new_application.network = network
            new_application.status = MembershipApplication.STATUS_SUBMITTED
            new_application.submitted_at = timezone.now()
            new_application.save()
            MembershipStatusEvent.objects.create(application=new_application, status=new_application.status, actor=request.user, note="Application submitted")
            log_action("membership.application_submitted", organisation=organisation, obj=new_application, actor=request.user)
            messages.success(request, f"Your application to {network.name} has been submitted.")
            if network == get_primary_network():
                return redirect("memberships:apply", slug=organisation.slug)
            return redirect("memberships:apply_to_network", slug=organisation.slug, network_slug=network.slug)

    context = {
        "organisation": organisation, "network": network, "application": application, "form": form,
        "status_events": application.status_events.select_related("actor") if application else [],
    }
    return render(request, "memberships/apply.html", context)


@login_required
def apply(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    return _apply(request, organisation, get_primary_network())


@login_required
def apply_to_network(request, slug, network_slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    network = get_object_or_404(Network, slug=network_slug)
    return _apply(request, organisation, network)


def _queue(request, network):
    if not (request.user.is_platform_admin or has_network_capability(request.user, network, "membership.review")):
        raise PermissionDenied
    applications = MembershipApplication.objects.select_related("organisation", "network").filter(
        network=network,
        status__in=[MembershipApplication.STATUS_SUBMITTED, MembershipApplication.STATUS_INFORMATION_REQUESTED],
    ).order_by("submitted_at")
    return render(request, "memberships/queue.html", {"network": network, "applications": applications})


@login_required
def queue(request):
    return _queue(request, get_primary_network())


@login_required
def queue_for_network(request, network_slug):
    network = get_object_or_404(Network, slug=network_slug)
    return _queue(request, network)


@login_required
def application_detail(request, application_id):
    application = get_object_or_404(
        MembershipApplication.objects.select_related("organisation", "network"), id=application_id
    )
    # Which network this decision is scoped to comes from the application
    # itself, never from "whichever network the current nav happens to be
    # on" — a Black Sash reviewer must only ever be able to decide on
    # Black Sash applications, never on the platform's own.
    network = application.network
    can_review = request.user.is_platform_admin or has_network_capability(request.user, network, "membership.review")
    if not can_review:
        raise PermissionDenied
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
            if network == get_primary_network():
                return redirect("memberships:queue")
            return redirect("memberships:queue_for_network", network_slug=network.slug)

    queue_url = (
        reverse("memberships:queue") if network == get_primary_network()
        else reverse("memberships:queue_for_network", kwargs={"network_slug": network.slug})
    )
    context = {
        "network": network, "application": application, "form": form, "can_decide": can_decide,
        "queue_url": queue_url,
        "status_events": application.status_events.select_related("actor"),
    }
    return render(request, "memberships/application_detail.html", context)
