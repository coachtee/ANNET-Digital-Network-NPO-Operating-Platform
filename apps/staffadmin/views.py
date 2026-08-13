from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from apps.accounts.models import User
from apps.core.permissions import has_platform_capability
from apps.memberships.models import MembershipApplication
from apps.networks.models import Network
from apps.opportunities.models import Opportunity
from apps.organisations.models import ORGANISATION_TYPE_CHOICES, PROVINCE_CHOICES, Organisation
from apps.resources.models import Resource


def _require_platform_capability(request, capability):
    if not has_platform_capability(request.user, capability):
        raise PermissionDenied


@login_required
def overview(request):
    _require_platform_capability(request, "platform.organisations.view")

    organisations = Organisation.objects.all()
    province_counts = [
        {"label": label, "count": organisations.filter(province=code).count()}
        for code, label in PROVINCE_CHOICES
    ]
    province_counts = [row for row in province_counts if row["count"]]
    province_counts.sort(key=lambda r: -r["count"])

    category_counts = [
        {"label": label, "count": organisations.filter(organisation_type=code).count()}
        for code, label in ORGANISATION_TYPE_CHOICES
    ]
    category_counts = [row for row in category_counts if row["count"]]
    category_counts.sort(key=lambda r: -r["count"])

    context = {
        "total_organisations": organisations.count(),
        "verified_organisations": organisations.filter(public_verification_status="verified").count(),
        "awaiting_verification": organisations.filter(is_publicly_listed=True, public_verification_status="unverified").count(),
        "network_count": Network.objects.count(),
        "pending_network_applications": MembershipApplication.objects.filter(
            status__in=[MembershipApplication.STATUS_SUBMITTED, MembershipApplication.STATUS_INFORMATION_REQUESTED]
        ).count(),
        "published_opportunities": Opportunity.objects.filter(status=Opportunity.STATUS_PUBLISHED).count(),
        "published_resources": Resource.objects.filter(status=Resource.STATUS_PUBLISHED).count(),
        "province_counts": province_counts,
        "category_counts": category_counts,
    }
    return render(request, "staffadmin/overview.html", context)


@login_required
def organisation_list(request):
    _require_platform_capability(request, "platform.organisations.view")

    organisations = Organisation.objects.all()
    query = request.GET.get("q", "").strip()
    if query:
        organisations = organisations.filter(legal_name__icontains=query)
    province = request.GET.get("province", "")
    if province:
        organisations = organisations.filter(province=province)
    category = request.GET.get("category", "")
    if category:
        organisations = organisations.filter(organisation_type=category)

    paginator = Paginator(organisations, 25)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "staffadmin/organisation_list.html", {
        "page_obj": page, "query": query, "province": province, "category": category,
        "province_choices": PROVINCE_CHOICES, "category_choices": ORGANISATION_TYPE_CHOICES,
    })


@login_required
def organisation_detail(request, slug):
    _require_platform_capability(request, "platform.organisations.view")
    # Staff-safe view only: legal identity, registration category, contact,
    # public profile and network membership status -- deliberately excludes
    # governance officials, documents, finance/expenses, compliance evidence
    # and beneficiary/people data. Being platform staff does not grant
    # unrestricted access to an organisation's private records; staff who
    # genuinely need those go through the same org-scoped capability checks
    # as anyone else (e.g. by being added as an organisation member).
    organisation = get_object_or_404(Organisation, slug=slug)
    return render(request, "staffadmin/organisation_detail.html", {
        "organisation": organisation,
        "network_memberships": organisation.network_memberships.select_related("network").order_by("-created_at"),
    })


@login_required
def people_list(request):
    _require_platform_capability(request, "platform.organisations.view")
    # Registered platform users and which organisation(s)/networks they
    # belong to -- distinct from Staff & Permissions (that's specifically
    # about who holds platform-staff access) and from the not-yet-built
    # organisation-level People/Beneficiary work (explicitly out of scope
    # this round).
    users = User.objects.exclude(is_kiosk_only=True).prefetch_related(
        "organisation_memberships__organisation", "network_staff_roles__network"
    ).order_by("-date_joined")
    paginator = Paginator(users, 25)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "staffadmin/people_list.html", {"page_obj": page})


@login_required
def network_list(request):
    _require_platform_capability(request, "platform.networks.view")
    networks = Network.objects.all()
    rows = [
        {
            "network": network,
            "approved_members": network.membership_applications.filter(status=MembershipApplication.STATUS_APPROVED).count(),
            "pending_applications": network.membership_applications.filter(
                status__in=[MembershipApplication.STATUS_SUBMITTED, MembershipApplication.STATUS_INFORMATION_REQUESTED]
            ).count(),
            "staff_count": network.staff_roles.filter(is_active=True).count(),
        }
        for network in networks
    ]
    return render(request, "staffadmin/network_list.html", {"rows": rows})


@login_required
def membership_overview(request):
    _require_platform_capability(request, "platform.memberships.review")
    networks = Network.objects.all()
    rows = [
        {
            "network": network,
            "pending": network.membership_applications.filter(
                status__in=[MembershipApplication.STATUS_SUBMITTED, MembershipApplication.STATUS_INFORMATION_REQUESTED]
            ).count(),
            "approved": network.membership_applications.filter(status=MembershipApplication.STATUS_APPROVED).count(),
        }
        for network in networks
    ]
    return render(request, "staffadmin/membership_overview.html", {"rows": rows})


@login_required
def opportunity_list(request):
    _require_platform_capability(request, "platform.opportunities.manage")
    opportunities = Opportunity.objects.select_related("network").all()
    status = request.GET.get("status", "")
    if status:
        opportunities = opportunities.filter(status=status)
    return render(request, "staffadmin/opportunity_list.html", {
        "opportunities": opportunities, "status": status, "status_choices": Opportunity.STATUS_CHOICES,
    })


@login_required
def coming_soon(request, title):
    _require_platform_capability(request, "platform.organisations.view")
    return render(request, "staffadmin/coming_soon.html", {"title": title})
