from django.urls import path

from . import views

app_name = "sitepublic"

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("our-network/", views.our_network, name="our_network"),
    path("directory/", views.directory, name="directory"),
    path("directory/<slug:slug>/", views.organisation_public_profile, name="organisation_profile"),
    path("join/", views.join, name="join"),
    path("resources/", views.resources, name="resources"),
    path("insights/", views.insights, name="insights"),
    path("privacy/", views.privacy, name="privacy"),
    path("terms/", views.terms, name="terms"),
]
