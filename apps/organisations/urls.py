from django.urls import path

from . import views

app_name = "organisations"

urlpatterns = [
    path("", views.workspace_home, name="workspace_home"),
    path("switch/", views.switch, name="switch"),
    path("create/", views.create, name="create"),
    path("<slug:slug>/onboarding/<str:step>/", views.onboarding_step, name="onboarding_step"),
    path("<slug:slug>/", views.org_360, name="org_360"),
    path("<slug:slug>/health-check/", views.health_check, name="health_check"),
    path("<slug:slug>/manage/", views.manage_hub, name="manage_hub"),
    path("<slug:slug>/funds-finance/", views.funds_finance_hub, name="funds_finance_hub"),
    path("<slug:slug>/evidence/", views.evidence_hub, name="evidence_hub"),
    path("<slug:slug>/public-profile/", views.public_profile_settings, name="public_profile_settings"),
]
