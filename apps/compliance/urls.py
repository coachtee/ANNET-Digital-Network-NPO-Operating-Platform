from django.urls import path

from . import views

app_name = "compliance"

urlpatterns = [
    path("<slug:slug>/", views.passport, name="passport"),
    path("<slug:slug>/calendar/", views.calendar, name="calendar"),
    path("<slug:slug>/obligation/<uuid:obligation_id>/", views.obligation_detail, name="obligation_detail"),
]
