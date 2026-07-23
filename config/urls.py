from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
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

if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
