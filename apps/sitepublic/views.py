from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from apps.networks.models import Network
from apps.networks.services import get_primary_network
from apps.opportunities.models import Opportunity
from apps.organisations.models import PROVINCE_CHOICES, Organisation
from apps.sitepublic.forms import DirectorySearchForm


def _public_organisations():
    return Organisation.objects.filter(is_publicly_listed=True)


def _sector_choices(public_orgs):
    sectors = set()
    for sector_list in public_orgs.values_list("sectors", flat=True):
        sectors.update(sector_list or [])
    return [(s, s) for s in sorted(sectors)]


def home(request):
    public_orgs = _public_organisations()
    provinces_represented = public_orgs.exclude(province="").values_list("province", flat=True).distinct().count()
    sector_choices = _sector_choices(public_orgs)

    province_counts = []
    for code, label in PROVINCE_CHOICES:
        count = public_orgs.filter(province=code).count()
        if count:
            province_counts.append({"code": code, "label": label, "count": count})
    province_counts.sort(key=lambda p: -p["count"])

    context = {
        # Live platform statistics — never hardcoded, always a direct count.
        "registered_organisations": Organisation.objects.count(),
        "verified_organisations": Organisation.objects.filter(public_verification_status="verified").count(),
        "funding_opportunities": Opportunity.objects.filter(status=Opportunity.STATUS_PUBLISHED).count(),
        "partnership_opportunities": Opportunity.objects.filter(
            status=Opportunity.STATUS_PUBLISHED, opportunity_type=Opportunity.TYPE_PARTNERSHIP
        ).count(),
        "national_networks": Network.objects.count(),
        # Secondary/contextual counts used further down the page.
        "provinces_represented": provinces_represented,
        "sector_count": len(sector_choices),
        "featured_organisations": public_orgs.order_by("-created_at")[:6],
        "province_counts": province_counts,
        "latest_opportunities": Opportunity.objects.filter(status=Opportunity.STATUS_PUBLISHED).order_by("-opening_date")[:4],
        "upcoming_events": Opportunity.objects.filter(
            status=Opportunity.STATUS_PUBLISHED, opportunity_type=Opportunity.TYPE_EVENT,
        ).order_by("opening_date")[:3],
        # No news/insights model exists yet (see sitepublic/insights.html) —
        # left empty rather than fabricated, matching the empty-state
        # pattern the rest of the platform already uses for unset content.
        "latest_news": [],
        "search_form": DirectorySearchForm(sector_choices=sector_choices),
    }
    return render(request, "sitepublic/home.html", context)


def about(request):
    return render(request, "sitepublic/about.html")


def our_network(request):
    public_orgs = _public_organisations()
    return render(request, "sitepublic/our_network.html", {
        "total_organisations": public_orgs.count(),
        # Scoped to the platform's own network — partner-programme
        # memberships (e.g. Black Sash) are a separate relationship, not
        # counted as a Bohlale Impact "member" here.
        "member_organisations": public_orgs.filter(
            network_memberships__network=get_primary_network(), network_memberships__status="approved"
        ).distinct().count(),
    })


def directory(request):
    public_orgs = _public_organisations()
    form = DirectorySearchForm(request.GET or None, sector_choices=_sector_choices(public_orgs))
    organisations = public_orgs.order_by("legal_name")

    if form.is_valid():
        data = form.cleaned_data
        if data.get("q"):
            organisations = organisations.filter(legal_name__icontains=data["q"])
        if data.get("province"):
            organisations = organisations.filter(province=data["province"])
        if data.get("organisation_type"):
            organisations = organisations.filter(organisation_type=data["organisation_type"])
        if data.get("verification_status"):
            organisations = organisations.filter(public_verification_status=data["verification_status"])
        if data.get("network_member"):
            organisations = organisations.filter(
                network_memberships__network=get_primary_network(), network_memberships__status="approved"
            ).distinct()
        if data.get("sector"):
            # JSONField list-containment (`sectors__contains`) isn't
            # supported on SQLite (only Postgres/MySQL), and this platform
            # runs on both — filter in Python instead. Directory sizes are
            # small enough (national NPO network, not millions of rows) that
            # this is fine; see apps/core/storage.py for a similar tradeoff.
            matching_ids = [org.pk for org in organisations if data["sector"] in (org.sectors or [])]
            organisations = organisations.filter(pk__in=matching_ids)

    paginator = Paginator(organisations, 12)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "sitepublic/directory.html", {"page_obj": page, "form": form})


def organisation_public_profile(request, slug):
    organisation = get_object_or_404(Organisation, slug=slug, is_publicly_listed=True)
    return render(request, "sitepublic/organisation_profile.html", {"organisation": organisation})


def join(request):
    return render(request, "sitepublic/join.html")


def resources(request):
    return render(request, "sitepublic/resources.html")


def insights(request):
    return render(request, "sitepublic/insights.html")


def privacy(request):
    return render(request, "sitepublic/privacy.html")


def terms(request):
    return render(request, "sitepublic/terms.html")
