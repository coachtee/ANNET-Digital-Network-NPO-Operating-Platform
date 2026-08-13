from django.urls import path

from . import views

app_name = "documents"

urlpatterns = [
    path("<slug:slug>/", views.document_list, name="list"),
    path("<slug:slug>/upload/", views.upload_document, name="upload"),
    path("<slug:slug>/<uuid:document_id>/", views.document_detail, name="detail"),
    path("<slug:slug>/<uuid:document_id>/download/", views.download_document, name="download"),
    path("<slug:slug>/<uuid:document_id>/archive/", views.archive_document, name="archive"),
    path("<slug:slug>/<uuid:document_id>/new-version/", views.new_version, name="new_version"),
]
