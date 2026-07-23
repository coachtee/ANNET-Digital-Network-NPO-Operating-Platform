from django.urls import path

from . import views

app_name = "grants"

urlpatterns = [
    path("<slug:slug>/", views.grant_list, name="list"),
    path("<slug:slug>/create/", views.create_grant, name="create"),
    path("<slug:slug>/<uuid:grant_id>/", views.grant_detail, name="detail"),
]
