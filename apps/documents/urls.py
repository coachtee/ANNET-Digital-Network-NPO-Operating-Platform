from django.urls import path

from . import views

app_name = "documents"

urlpatterns = [
    path("<slug:slug>/", views.document_list, name="list"),
    path("<slug:slug>/upload/", views.upload_document, name="upload"),
    path("<slug:slug>/<uuid:document_id>/download/", views.download_document, name="download"),
]
