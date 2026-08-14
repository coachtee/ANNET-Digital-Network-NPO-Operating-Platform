from django.urls import path

from . import views

app_name = "programmes"

urlpatterns = [
    path("<slug:slug>/", views.programme_list, name="list"),
    path("<slug:slug>/<uuid:programme_id>/", views.programme_detail, name="detail"),
    path("<slug:slug>/<uuid:programme_id>/plan/", views.programme_plan, name="plan"),
    path("<slug:slug>/<uuid:programme_id>/plan/assumptions/<uuid:assumption_id>/edit/", views.assumption_edit, name="assumption_edit"),
    path("<slug:slug>/<uuid:programme_id>/plan/assumptions/<uuid:assumption_id>/delete/", views.assumption_delete, name="assumption_delete"),
    path("<slug:slug>/<uuid:programme_id>/learning/", views.programme_learning, name="learning"),
    path("<slug:slug>/<uuid:programme_id>/learning/questions/<uuid:question_id>/edit/", views.learning_question_edit, name="learning_question_edit"),
    path("<slug:slug>/<uuid:programme_id>/learning/questions/<uuid:question_id>/delete/", views.learning_question_delete, name="learning_question_delete"),
    path("<slug:slug>/<uuid:programme_id>/learning/log/<uuid:entry_id>/edit/", views.learning_log_edit, name="learning_log_edit"),
    path("<slug:slug>/<uuid:programme_id>/learning/log/<uuid:entry_id>/delete/", views.learning_log_delete, name="learning_log_delete"),
    path("<slug:slug>/<uuid:programme_id>/learning/context/<uuid:note_id>/edit/", views.context_note_edit, name="context_note_edit"),
    path("<slug:slug>/<uuid:programme_id>/learning/context/<uuid:note_id>/delete/", views.context_note_delete, name="context_note_delete"),
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
