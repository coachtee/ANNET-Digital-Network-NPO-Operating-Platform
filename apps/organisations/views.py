from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.audit.services import log_action
from apps.compliance.services import sync_obligations_for_organisation
from apps.core.permissions import ORG_ROLE_ADMIN
from apps.governance.forms import GovernanceOfficialForm
from apps.impact.services import people_reached_for_organisation
from apps.networks.services import get_primary_network
from apps.organisations import forms as org_forms
from apps.organisations.health import compute_health_check
from apps.organisations.middleware import SESSION_KEY
from apps.organisations.models import Organisation, OrganisationMembership
from apps.organisations.services import get_organisation_or_404_for_user

ONBOARDING_ORDER = [step for step, _ in Organisation.ONBOARDING_STEP_CHOICES]


def _advance(organisation, current_step):
    idx = ONBOARDING_ORDER.index(current_step)
    if idx + 1 < len(ONBOARDING_ORDER):
        organisation.onboarding_step = ONBOARDING_ORDER[idx + 1]
        organisation.save(update_fields=["onboarding_step"])


@login_required
def create(request):
    """Step 1 of onboarding: organisation identity. If the user already has
    an organisation mid-onboarding, resume there instead of creating a
    second one."""
    existing = request.user.active_memberships.filter(
        role=ORG_ROLE_ADMIN
    ).exclude(organisation__onboarding_step=Organisation.ONBOARDING_COMPLETE).first()
    if existing:
        return redirect("organisations:onboarding_step", slug=existing.organisation.slug, step=existing.organisation.onboarding_step)

    if request.method == "POST":
        form = org_forms.OrganisationIdentityForm(request.POST)
        if form.is_valid():
            organisation = form.save(commit=False)
            organisation.created_by = request.user
            organisation.onboarding_step = Organisation.ONBOARDING_LEGAL
            organisation.save()
            OrganisationMembership.objects.create(organisation=organisation, user=request.user, role=ORG_ROLE_ADMIN)
            log_action("organisation.created", organisation=organisation, obj=organisation, actor=request.user)
            request.session[SESSION_KEY] = organisation.slug
            messages.success(request, f"{organisation.display_name} has been created. Let's continue setting it up.")
            return redirect("organisations:onboarding_step", slug=organisation.slug, step=Organisation.ONBOARDING_LEGAL)
    else:
        form = org_forms.OrganisationIdentityForm()
    return render(request, "organisations/onboarding_identity.html", {"form": form})


def _require_admin(request, organisation):
    return organisation.memberships.filter(user=request.user, is_active=True, role=ORG_ROLE_ADMIN).exists() or request.user.is_platform_admin


@login_required
def onboarding_step(request, slug, step):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    if not _require_admin(request, organisation):
        messages.error(request, "Only an organisation administrator can continue onboarding.")
        return redirect("organisations:workspace_home")

    context = {"organisation": organisation, "step": step, "steps": Organisation.ONBOARDING_STEP_CHOICES}

    if step == Organisation.ONBOARDING_LEGAL:
        form = org_forms.OrganisationLegalForm(request.POST or None, instance=organisation)
        if request.method == "POST" and form.is_valid():
            form.save()
            _advance(organisation, step)
            return redirect("organisations:onboarding_step", slug=slug, step=Organisation.ONBOARDING_REGISTRATION)
        context["form"] = form
        return render(request, "organisations/onboarding_legal.html", context)

    if step == Organisation.ONBOARDING_REGISTRATION:
        form = org_forms.OrganisationRegistrationForm(request.POST or None, instance=organisation)
        if request.method == "POST" and form.is_valid():
            form.save()
            _advance(organisation, step)
            return redirect("organisations:onboarding_step", slug=slug, step=Organisation.ONBOARDING_GOVERNANCE)
        context["form"] = form
        return render(request, "organisations/onboarding_registration.html", context)

    if step == Organisation.ONBOARDING_GOVERNANCE:
        form = GovernanceOfficialForm(request.POST or None)
        if request.method == "POST":
            if "continue" in request.POST:
                _advance(organisation, step)
                return redirect("organisations:onboarding_step", slug=slug, step=Organisation.ONBOARDING_ACTIVITIES)
            if form.is_valid():
                official = form.save(commit=False)
                official.organisation = organisation
                official.save()
                messages.success(request, f"{official.full_name} added.")
                form = GovernanceOfficialForm()
        context["form"] = form
        context["officials"] = organisation.governance_officials.filter(status="active")
        return render(request, "organisations/onboarding_governance.html", context)

    if step == Organisation.ONBOARDING_ACTIVITIES:
        initial = {
            "sectors": ", ".join(organisation.sectors),
            "programme_areas": ", ".join(organisation.programme_areas),
            "beneficiary_groups": ", ".join(organisation.beneficiary_groups),
            "sensitive_service_areas": ", ".join(organisation.sensitive_service_areas),
        }
        form = org_forms.OrganisationActivitiesForm(request.POST or None, initial=initial)
        if request.method == "POST" and form.is_valid():
            form.save(organisation)
            _advance(organisation, step)
            return redirect("organisations:onboarding_step", slug=slug, step=Organisation.ONBOARDING_COMPLIANCE)
        context["form"] = form
        return render(request, "organisations/onboarding_activities.html", context)

    if step == Organisation.ONBOARDING_COMPLIANCE:
        if request.method == "POST":
            sync_obligations_for_organisation(organisation)
            _advance(organisation, step)
            return redirect("organisations:onboarding_step", slug=slug, step=Organisation.ONBOARDING_HEALTH_CHECK)
        sync_obligations_for_organisation(organisation)
        context["obligations"] = organisation.compliance_obligations.select_related("rule").all()
        return render(request, "organisations/onboarding_compliance.html", context)

    if step == Organisation.ONBOARDING_HEALTH_CHECK:
        if request.method == "POST":
            organisation.onboarding_step = Organisation.ONBOARDING_COMPLETE
            organisation.onboarding_completed_at = timezone.now()
            organisation.save(update_fields=["onboarding_step", "onboarding_completed_at"])
            messages.success(request, "Onboarding complete. You can now submit your membership application from My Organisation.")
            return redirect("organisations:workspace_home")
        context["health"] = compute_health_check(organisation)
        return render(request, "organisations/onboarding_health_check.html", context)

    return redirect("organisations:onboarding_step", slug=slug, step=Organisation.ONBOARDING_IDENTITY)


# Where "fix" from the Needs Attention list should send a user for each
# Health Check dimension -- built from URLs that already exist elsewhere
# in the workspace, not new pages.
_DIMENSION_FIX_URL_NAME = {
    "registration": ("organisations:org_360", {}),
    "compliance": ("compliance:passport", {}),
    "governance": ("governance:list", {}),
    "policies": ("policies:list", {}),
    "programme_management": ("programmes:list", {}),
    "me": ("monitoring_evaluation:dashboard", {}),
    "financial_accountability": ("expenses:list", {}),
}


def _dimension_fix_url(organisation, dimension_key):
    url_name, _ = _DIMENSION_FIX_URL_NAME.get(dimension_key, (None, {}))
    if not url_name:
        return None
    return reverse(url_name, kwargs={"slug": organisation.slug})


@login_required
def workspace_home(request):
    organisation = request.organisation
    if not organisation:
        return redirect("organisations:create")
    if organisation.onboarding_step != Organisation.ONBOARDING_COMPLETE:
        return redirect("organisations:onboarding_step", slug=organisation.slug, step=organisation.onboarding_step)

    health = compute_health_check(organisation)

    # One action per below-100 dimension keeps this a short, actionable
    # list rather than a dump of every recommendation the Health Check has
    # -- the full set is still one click away on the Health Check page.
    needs_attention = []
    for dim in health["dimensions"]:
        if dim.score < 100 and dim.recommended_actions:
            needs_attention.append({
                "text": dim.recommended_actions[0], "dimension": dim.label,
                "fix_url": _dimension_fix_url(organisation, dim.key),
            })
    needs_attention = needs_attention[:6]

    primary_network = get_primary_network()
    network_memberships = organisation.network_memberships.select_related("network").order_by("-created_at")

    context = {
        "organisation": organisation,
        "health": health,
        "needs_attention": needs_attention,
        "open_obligations": organisation.compliance_obligations.exclude(
            status__in=["submitted", "evidence_recorded", "not_applicable"]
        ).count(),
        "active_programmes": organisation.programmes.filter(status="active").count(),
        "active_projects": organisation.projects.filter(status="active").count(),
        "document_count": organisation.documents.filter(status="active").count(),
        "beneficiary_count": organisation.beneficiaries.count(),
        "people_reached": people_reached_for_organisation(organisation),
        # Every network/programme this organisation has ever applied to or
        # joined, not just the platform's own -- an org can independently
        # hold memberships with several networks/programmes at once (e.g.
        # a partner programme like Black Sash) alongside its own workspace.
        "network_memberships": network_memberships,
        "primary_network": primary_network,
        "membership_application": network_memberships.filter(network=primary_network).first(),
        "recent_activity": organisation.audit_entries.select_related("actor")[:6],
    }
    return render(request, "organisations/workspace_home.html", context)


ORG_360_TABS = [
    ("overview", "Overview"), ("legal", "Legal & Registration"), ("governance", "Governance"),
    ("people", "People"), ("programmes", "Programmes"), ("projects", "Projects"),
    ("funding", "Funding"), ("compliance", "Compliance"), ("policies", "Policies"),
    ("documents", "Documents"), ("impact", "Impact"),
]


@login_required
def org_360(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    tab = request.GET.get("tab", "overview")
    context = {"organisation": organisation, "tab": tab, "tabs": ORG_360_TABS}
    return render(request, "organisations/org_360.html", context)


@login_required
def health_check(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    context = {"organisation": organisation, "health": compute_health_check(organisation)}
    return render(request, "organisations/health_check.html", context)


@login_required
@require_POST
def switch(request):
    slug = request.POST.get("organisation_slug")
    organisation = get_object_or_404(Organisation, slug=slug, memberships__user=request.user, memberships__is_active=True)
    request.session[SESSION_KEY] = organisation.slug
    return redirect("organisations:workspace_home")


@login_required
def public_profile_settings(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    if not _require_admin(request, organisation):
        messages.error(request, "Only an organisation administrator can edit public profile settings.")
        return redirect("organisations:org_360", slug=slug)
    form = org_forms.OrganisationPublicProfileForm(request.POST or None, request.FILES or None, instance=organisation)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_action("organisation.public_profile_updated", organisation=organisation, obj=organisation, actor=request.user)
        messages.success(request, "Public profile settings updated.")
        return redirect("organisations:org_360", slug=slug)
    return render(request, "organisations/public_profile_settings.html", {"organisation": organisation, "form": form})
