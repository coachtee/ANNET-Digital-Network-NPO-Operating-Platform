from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core.permissions import has_network_capability
from apps.networks.models import Network
from apps.networks.services import get_primary_network
from apps.opportunities.forms import OpportunityForm
from apps.opportunities.models import Opportunity


def public_list(request):
    opportunities = Opportunity.objects.filter(status=Opportunity.STATUS_PUBLISHED).order_by("-opening_date")
    type_filter = request.GET.get("type")
    if type_filter:
        opportunities = opportunities.filter(opportunity_type=type_filter)
    paginator = Paginator(opportunities, 12)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "opportunities/public_list.html", {
        "page_obj": page, "type_choices": Opportunity.TYPE_CHOICES, "type_filter": type_filter,
    })


def public_detail(request, opportunity_id):
    opportunity = get_object_or_404(Opportunity, id=opportunity_id, status=Opportunity.STATUS_PUBLISHED)
    return render(request, "opportunities/public_detail.html", {"opportunity": opportunity})


def _create_url_for(network):
    if network == get_primary_network():
        return reverse("opportunities:create")
    return reverse("opportunities:create_for_network", kwargs={"network_slug": network.slug})


def _manage_list(request, network):
    if not (request.user.is_platform_admin or has_network_capability(request.user, network, "network.opportunities.manage")):
        raise PermissionDenied
    return render(request, "opportunities/manage_list.html", {
        "network": network, "opportunities": Opportunity.objects.filter(network=network),
        "create_url": _create_url_for(network),
    })


@login_required
def manage_list(request):
    return _manage_list(request, get_primary_network())


@login_required
def manage_list_for_network(request, network_slug):
    network = get_object_or_404(Network, slug=network_slug)
    return _manage_list(request, network)


def _create_opportunity(request, network):
    if not (request.user.is_platform_admin or has_network_capability(request.user, network, "network.opportunities.manage")):
        raise PermissionDenied
    form = OpportunityForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        opportunity = form.save(commit=False)
        opportunity.network = network
        opportunity.save()
        messages.success(request, "Opportunity saved.")
        if network == get_primary_network():
            return redirect("opportunities:manage_list")
        return redirect("opportunities:manage_list_for_network", network_slug=network.slug)
    return render(request, "opportunities/opportunity_form.html", {"form": form, "network": network})


@login_required
def create_opportunity(request):
    return _create_opportunity(request, get_primary_network())


@login_required
def create_opportunity_for_network(request, network_slug):
    network = get_object_or_404(Network, slug=network_slug)
    return _create_opportunity(request, network)


@login_required
def edit_opportunity(request, opportunity_id):
    opportunity = get_object_or_404(Opportunity, id=opportunity_id)
    if not (request.user.is_platform_admin or has_network_capability(request.user, opportunity.network, "network.opportunities.manage")):
        raise PermissionDenied
    form = OpportunityForm(request.POST or None, instance=opportunity)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Opportunity saved.")
        if opportunity.network == get_primary_network():
            return redirect("opportunities:manage_list")
        return redirect("opportunities:manage_list_for_network", network_slug=opportunity.network.slug)
    return render(request, "opportunities/opportunity_form.html", {"form": form, "network": opportunity.network, "opportunity": opportunity})


@login_required
@require_POST
def archive_opportunity(request, opportunity_id):
    opportunity = get_object_or_404(Opportunity, id=opportunity_id)
    if not (request.user.is_platform_admin or has_network_capability(request.user, opportunity.network, "network.opportunities.manage")):
        raise PermissionDenied
    opportunity.status = Opportunity.STATUS_CLOSED
    opportunity.save(update_fields=["status"])
    messages.success(request, "Opportunity closed.")
    return redirect(request.POST.get("next") or "staffadmin:opportunity_list")
