from django.urls import path

from . import views

app_name = "attendance"

urlpatterns = [
    path("<slug:slug>/", views.attendance_list, name="list"),
    path("<slug:slug>/record/", views.record_attendance, name="record"),
    path("<slug:slug>/kiosk/launch/", views.kiosk_launch, name="kiosk_launch"),
    path("kiosk/<uuid:token>/", views.kiosk_entry, name="kiosk_entry"),
]
