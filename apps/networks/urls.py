from django.urls import path

from . import views

app_name = "networks"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("capacity/", views.capacity, name="capacity"),
    path("programme/<slug:network_slug>/", views.dashboard_for_network, name="dashboard_for_network"),
    path("programme/<slug:network_slug>/capacity/", views.capacity_for_network, name="capacity_for_network"),
]
