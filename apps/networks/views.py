from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from apps.core.permissions import has_network_capability
from apps.networks.services import get_primary_network
from apps.organisations.health import compute_health_check
from apps.organisations.models import Organisation, PROVINCE_CHOICES


def _require_network_viewer(request):
    network = get_primary_network()
    if not (request.user.is_platform_admin or has_network_capability(request.user, network, "network.dashboard.view")):
        raise PermissionDenied
    return network


@login_required
def dashboard(request):
    network = _require_network_viewer(request)
    member_organisations = Organisation.objects.filter(network_memberships__status="approved").distinct()

    province = request.GET.get("province")
    if province:
        member_organisations = member_organisations.filter(province=province)

    total_members = member_organisations.count()
    verified_profiles = member_organisations.filter(public_verification_status="verified").count()

    scores = [compute_health_check(org)["overall"] for org in member_organisations[:200]]
    average_readiness = round(sum(scores) / len(scores)) if scores else 0
    requiring_support = sum(1 for s in scores if s < 50)

    active_programmes = sum(org.programmes.filter(status="active").count() for org in member_organisations[:200])

    context = {
        "network": network, "total_members": total_members, "verified_profiles": verified_profiles,
        "average_readiness": average_readiness, "requiring_support": requiring_support,
        "active_programmes": active_programmes, "member_organisations": member_organisations[:100],
        "provinces": PROVINCE_CHOICES, "selected_province": province,
    }
    return render(request, "networks/dashboard.html", context)


@login_required
def capacity(request):
    network = _require_network_viewer(request)
    member_organisations = Organisation.objects.filter(network_memberships__status="approved").distinct()[:200]

    needs = {"governance": [], "policies": [], "me": [], "financial_accountability": [], "compliance": []}
    for org in member_organisations:
        health = compute_health_check(org)
        for dim in health["dimensions"]:
            if dim.key in needs and dim.score < 50:
                needs[dim.key].append(org)

    context = {
        "network": network,
        "governance_needs": needs["governance"], "policy_needs": needs["policies"],
        "me_needs": needs["me"], "financial_needs": needs["financial_accountability"],
        "compliance_needs": needs["compliance"],
    }
    return render(request, "networks/capacity.html", context)
