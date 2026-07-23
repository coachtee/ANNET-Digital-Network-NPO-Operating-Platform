from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    path("<slug:slug>/", views.project_list, name="list"),
    path("<slug:slug>/create/", views.create_project, name="create"),
    path("<slug:slug>/<uuid:project_id>/", views.project_detail, name="detail"),
]
