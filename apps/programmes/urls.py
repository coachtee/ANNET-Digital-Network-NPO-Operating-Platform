from django.urls import path

from . import views

app_name = "programmes"

urlpatterns = [
    path("<slug:slug>/", views.programme_list, name="list"),
    path("<slug:slug>/create/", views.create_programme, name="create"),
    path("<slug:slug>/<uuid:programme_id>/", views.programme_detail, name="detail"),
    path("<slug:slug>/<uuid:programme_id>/wizard/<str:step>/", views.wizard_step, name="wizard_step"),
    path("<slug:slug>/<uuid:programme_id>/plan/", views.programme_plan, name="plan"),
    path("<slug:slug>/<uuid:programme_id>/team/", views.programme_team, name="team"),
    path("<slug:slug>/<uuid:programme_id>/team/<uuid:membership_id>/remove/", views.remove_programme_member, name="remove_team_member"),
    path("<slug:slug>/<uuid:programme_id>/activities/", views.activity_list, name="activities"),
    path("<slug:slug>/<uuid:programme_id>/activities/create/", views.create_activity, name="create_activity"),
    path("<slug:slug>/<uuid:programme_id>/activities/<uuid:activity_id>/edit/", views.edit_activity, name="edit_activity"),
    path("<slug:slug>/<uuid:programme_id>/activities/<uuid:activity_id>/delete/", views.delete_activity, name="delete_activity"),
    path("<slug:slug>/<uuid:programme_id>/finance/", views.programme_finance, name="finance"),
    path("<slug:slug>/<uuid:programme_id>/evidence/", views.programme_evidence, name="evidence"),
    path("<slug:slug>/<uuid:programme_id>/reports/", views.programme_reports, name="reports"),
]
