from django.urls import path

from . import views

app_name = "memberships"

urlpatterns = [
    path("<slug:slug>/apply/", views.apply, name="apply"),
    path("queue/", views.queue, name="queue"),
    path("queue/<uuid:application_id>/", views.application_detail, name="application_detail"),
]
