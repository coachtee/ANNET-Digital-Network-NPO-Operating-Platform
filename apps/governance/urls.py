from django.urls import path

from . import views

app_name = "governance"

urlpatterns = [
    path("<slug:slug>/", views.governance_list, name="list"),
    path("<slug:slug>/officials/add/", views.add_official, name="add_official"),
    path("<slug:slug>/officials/<uuid:official_id>/resign/", views.resign_official, name="resign_official"),
    path("<slug:slug>/meetings/create/", views.create_meeting, name="create_meeting"),
    path("<slug:slug>/meetings/<uuid:meeting_id>/", views.meeting_detail, name="meeting_detail"),
    path("<slug:slug>/meetings/<uuid:meeting_id>/minutes/upload/", views.upload_minutes, name="upload_minutes"),
]
