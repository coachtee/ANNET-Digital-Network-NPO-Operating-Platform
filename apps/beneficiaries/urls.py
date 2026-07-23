from django.urls import path

from . import views

app_name = "beneficiaries"

urlpatterns = [
    path("<slug:slug>/", views.beneficiary_list, name="list"),
    path("<slug:slug>/create/", views.create_beneficiary, name="create"),
]
