from django.urls import path

from . import views

app_name = "opportunities"

urlpatterns = [
    path("", views.public_list, name="public_list"),
    path("manage/", views.manage_list, name="manage_list"),
    path("manage/create/", views.create_opportunity, name="create"),
    path("<uuid:opportunity_id>/", views.public_detail, name="public_detail"),
]
