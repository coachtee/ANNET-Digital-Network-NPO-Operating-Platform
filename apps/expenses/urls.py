from django.urls import path

from . import views

app_name = "expenses"

urlpatterns = [
    path("<slug:slug>/", views.expense_list, name="list"),
    path("<slug:slug>/project/<uuid:project_id>/", views.project_expenses, name="project_expenses"),
    path("<slug:slug>/expense/<uuid:expense_id>/review/", views.review_expense, name="review_expense"),
    path("<slug:slug>/expense/<uuid:expense_id>/receipt/", views.download_receipt, name="download_receipt"),
]
