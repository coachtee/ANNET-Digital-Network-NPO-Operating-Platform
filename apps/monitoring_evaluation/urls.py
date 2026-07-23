from django.urls import path

from . import views

app_name = "monitoring_evaluation"

urlpatterns = [
    path("<slug:slug>/", views.me_dashboard, name="dashboard"),
    path("<slug:slug>/programme/<uuid:programme_id>/", views.programme_me, name="programme_me"),
    path("<slug:slug>/indicator/<uuid:indicator_id>/", views.indicator_detail, name="indicator_detail"),
]
