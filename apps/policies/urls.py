from django.urls import path

from . import views

app_name = "policies"

urlpatterns = [
    path("<slug:slug>/", views.policy_list, name="list"),
    path("<slug:slug>/create/", views.create_policy, name="create"),
    path("<slug:slug>/<uuid:policy_id>/", views.policy_detail, name="detail"),
]
