from django.urls import path

from . import views

app_name = "reporting"

urlpatterns = [
    path("<slug:slug>/", views.report_list, name="list"),
    path("<slug:slug>/organisation-profile.pdf", views.organisation_profile_pdf, name="organisation_profile_pdf"),
    path("<slug:slug>/compliance.csv", views.compliance_csv, name="compliance_csv"),
    path("<slug:slug>/attendance.csv", views.attendance_csv, name="attendance_csv"),
    path("<slug:slug>/expenses.csv", views.expense_csv, name="expense_csv"),
]
