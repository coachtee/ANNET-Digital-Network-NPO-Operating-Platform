from django.urls import path

from . import views

app_name = "programmes"

urlpatterns = [
    path("<slug:slug>/", views.programme_list, name="list"),
    path("<slug:slug>/create/", views.create_programme, name="create"),
    path("<slug:slug>/<uuid:programme_id>/", views.programme_detail, name="detail"),
]
