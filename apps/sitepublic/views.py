from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from apps.opportunities.models import Opportunity
from apps.organisations.models import PROVINCE_CHOICES, Organisation
from apps.sitepublic.forms import DirectorySearchForm


def _public_organisations():
    return Organisation.objects.filter(is_publicly_listed=True)


def home(request):
    public_orgs = _public_organisations()
    provinces_represented = public_orgs.exclude(province="").values_list("province", flat=True).distinct().count()
    sectors = set()
    for sector_list in public_orgs.values_list("sectors", flat=True):
        sectors.update(sector_list or [])

    province_counts = []
    for code, label in PROVINCE_CHOICES:
        count = public_orgs.filter(province=code).count()
        if count:
            province_counts.append({"code": code, "label": label, "count": count})
    province_counts.sort(key=lambda p: -p["count"])

    context = {
        "total_organisations": public_orgs.count(),
        "provinces_represented": provinces_represented,
        "sector_count": len(sectors),
        "network_count": 1,
        "featured_organisations": public_orgs.filter(public_verification_status="verified")[:3],
        "province_counts": province_counts,
        "latest_opportunities": Opportunity.objects.filter(status=Opportunity.STATUS_PUBLISHED).order_by("-opening_date")[:4],
        "search_form": DirectorySearchForm(),
    }
    return render(request, "sitepublic/home.html", context)


def about(request):
    return render(request, "sitepublic/about.html")


def our_network(request):
    public_orgs = _public_organisations()
    return render(request, "sitepublic/our_network.html", {
        "total_organisations": public_orgs.count(),
        "member_organisations": public_orgs.filter(network_memberships__status="approved").distinct().count(),
    })


def directory(request):
    form = DirectorySearchForm(request.GET or None)
    organisations = _public_organisations().order_by("legal_name")

    if form.is_valid():
        data = form.cleaned_data
        if data.get("q"):
            organisations = organisations.filter(legal_name__icontains=data["q"])
        if data.get("province"):
            organisations = organisations.filter(province=data["province"])
        if data.get("organisation_type"):
            organisations = organisations.filter(organisation_type=data["organisation_type"])
        if data.get("annet_member"):
            organisations = organisations.filter(network_memberships__status="approved").distinct()

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
