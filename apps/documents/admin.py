from django.contrib import admin

from apps.documents.models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ["title", "organisation", "visibility", "uploaded_by", "created_at"]
    list_filter = ["visibility"]
    search_fields = ["title", "organisation__legal_name"]
