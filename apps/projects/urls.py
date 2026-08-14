from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    path("<slug:slug>/", views.project_list, name="list"),
    path("<slug:slug>/create/", views.create_project, name="create"),
    path("<slug:slug>/<uuid:project_id>/", views.project_detail, name="detail"),
    path("<slug:slug>/<uuid:project_id>/edit/", views.project_edit, name="edit"),
    path("<slug:slug>/<uuid:project_id>/activities/", views.project_activities, name="activities"),
    path("<slug:slug>/<uuid:project_id>/activities/create/", views.project_create_activity, name="create_activity"),
    path("<slug:slug>/<uuid:project_id>/tasks/", views.project_tasks, name="tasks"),
    path("<slug:slug>/<uuid:project_id>/people/", views.project_people, name="people"),
    path("<slug:slug>/<uuid:project_id>/budget/", views.project_budget, name="budget"),
    path("<slug:slug>/<uuid:project_id>/expenses/", views.project_expenses, name="expenses"),
    path("<slug:slug>/<uuid:project_id>/evidence/", views.project_evidence, name="evidence"),
    path("<slug:slug>/<uuid:project_id>/reports/", views.project_reports, name="reports"),
]
