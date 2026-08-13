from django.urls import path

from . import views

app_name = "staffadmin"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("organisations/", views.organisation_list, name="organisation_list"),
    path("organisations/<slug:slug>/", views.organisation_detail, name="organisation_detail"),
    path("people/", views.people_list, name="people_list"),
    path("networks/", views.network_list, name="network_list"),
    path("memberships/", views.membership_overview, name="membership_overview"),
    path("opportunities/", views.opportunity_list, name="opportunity_list"),
    path("events/", views.coming_soon, {"title": "Events"}, name="events"),
    path("insights/", views.coming_soon, {"title": "Insights"}, name="insights"),
    path("partnerships/", views.coming_soon, {"title": "Partnerships"}, name="partnerships"),
    path("documents/", views.coming_soon, {"title": "Platform Documents"}, name="documents"),
    path("staff/", views.coming_soon, {"title": "Staff & Permissions"}, name="staff"),
    path("reports/", views.coming_soon, {"title": "Reports"}, name="reports"),
    path("settings/", views.coming_soon, {"title": "Settings"}, name="settings"),
]
