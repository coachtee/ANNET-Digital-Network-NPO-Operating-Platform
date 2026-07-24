from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from apps.core.views import health_check

urlpatterns = [
    # No auth, no DB query, no redirect — see apps.core.views.health_check.
    # Kept first and outside any app include so nothing else on the
    # request path can accidentally start gating it later.
    path("health/", health_check, name="health_check"),
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("app/", include("apps.organisations.urls")),
    path("compliance/", include("apps.compliance.urls")),
    path("governance/", include("apps.governance.urls")),
    path("policies/", include("apps.policies.urls")),
    path("documents/", include("apps.documents.urls")),
    path("grants/", include("apps.grants.urls")),
    path("projects/", include("apps.projects.urls")),
    path("programmes/", include("apps.programmes.urls")),
    path("beneficiaries/", include("apps.beneficiaries.urls")),
    path("attendance/", include("apps.attendance.urls")),
    path("me/", include("apps.monitoring_evaluation.urls")),
    path("finance/", include("apps.expenses.urls")),
    path("reports/", include("apps.reporting.urls")),
    path("impact/", include("apps.impact.urls")),
    path("network/", include("apps.networks.urls")),
    path("membership/", include("apps.memberships.urls")),
    path("opportunities/", include("apps.opportunities.urls")),
    path("", include("apps.sitepublic.urls")),
]

# django.contrib.staticfiles.storage / WhiteNoise serves STATIC_URL from
# within the app process (see STORAGES in settings.py) — no web server in
# front of it needs to. MEDIA_URL (public organisation/network logos only;
# never PRIVATE_MEDIA_ROOT — see apps.documents) previously relied on an
# Nginx `location /media/` block, which the Coolify deployment does not
# have (Coolify's Traefik is a reverse proxy only, not a file server). So
# Django serves it directly here, in every environment, not just DEBUG.
# Fine at this platform's scale (logo images only); move to object storage
# per DEPLOYMENT.md if that changes.
from django.views.static import serve as serve_media  # noqa: E402

urlpatterns += [
    path(
        f"{settings.MEDIA_URL.lstrip('/')}<path:path>",
        serve_media,
        {"document_root": settings.MEDIA_ROOT},
    ),
]
