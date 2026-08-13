from django.urls import path

from . import views

app_name = "resources"

urlpatterns = [
    path("", views.manage_list, name="manage_list"),
    path("create/", views.create, name="create"),
    path("<uuid:resource_id>/edit/", views.edit, name="edit"),
]
