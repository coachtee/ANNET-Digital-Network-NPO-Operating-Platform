from django.urls import path

from . import views

app_name = "impact"

urlpatterns = [
    path("<slug:slug>/", views.impact_dashboard, name="dashboard"),
]
