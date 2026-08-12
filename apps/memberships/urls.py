from django.urls import path

from . import views

app_name = "memberships"

urlpatterns = [
    path("<slug:slug>/apply/", views.apply, name="apply"),
    path("<slug:slug>/apply/<slug:network_slug>/", views.apply_to_network, name="apply_to_network"),
    path("queue/", views.queue, name="queue"),
    path("queue/network/<slug:network_slug>/", views.queue_for_network, name="queue_for_network"),
    path("queue/<uuid:application_id>/", views.application_detail, name="application_detail"),
]
