from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.permissions import has_network_capability
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


@login_required
def manage_list(request):
    network = get_primary_network()
    if not (request.user.is_platform_admin or has_network_capability(request.user, network, "network.opportunities.manage")):
        raise PermissionDenied
    return render(request, "opportunities/manage_list.html", {
        "network": network, "opportunities": Opportunity.objects.filter(network=network),
    })


@login_required
def create_opportunity(request):
    network = get_primary_network()
    if not (request.user.is_platform_admin or has_network_capability(request.user, network, "network.opportunities.manage")):
        raise PermissionDenied
    form = OpportunityForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        opportunity = form.save(commit=False)
        opportunity.network = network
        opportunity.save()
        messages.success(request, "Opportunity saved.")
        return redirect("opportunities:manage_list")
    return render(request, "opportunities/opportunity_form.html", {"form": form})
