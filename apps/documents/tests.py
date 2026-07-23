from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.permissions import ORG_ROLE_ADMIN
from apps.documents.models import Document
from apps.organisations.models import Organisation, OrganisationMembership


class DocumentIDORTests(TestCase):
    """Release blocker per spec section 22/38/52: a user from one
    organisation must never be able to download another organisation's
    private documents, even if they guess/enumerate the document id."""

    def setUp(self):
        self.org_a = Organisation.objects.create(legal_name="Org A", organisation_type="npo")
        self.org_b = Organisation.objects.create(legal_name="Org B", organisation_type="npo")
        self.user_a = User.objects.create_user(email="a@example.com", password="Sup3rSecurePass!23")
        self.user_b = User.objects.create_user(email="b@example.com", password="Sup3rSecurePass!23")
        OrganisationMembership.objects.create(organisation=self.org_a, user=self.user_a, role=ORG_ROLE_ADMIN)
        OrganisationMembership.objects.create(organisation=self.org_b, user=self.user_b, role=ORG_ROLE_ADMIN)
        self.document = Document.objects.create(
            organisation=self.org_a, title="Board Minutes", uploaded_by=self.user_a,
            file=SimpleUploadedFile("minutes.pdf", b"%PDF-1.4 fake", content_type="application/pdf"),
        )

    def test_other_org_member_cannot_download(self):
        self.client.force_login(self.user_b)
        resp = self.client.get(reverse("documents:download", args=[self.org_a.slug, self.document.id]))
        self.assertEqual(resp.status_code, 404)

    def test_other_org_member_cannot_reach_via_own_org_url(self):
        self.client.force_login(self.user_b)
        resp = self.client.get(reverse("documents:download", args=[self.org_b.slug, self.document.id]))
        self.assertEqual(resp.status_code, 404)

    def test_owning_org_member_can_download(self):
        self.client.force_login(self.user_a)
        resp = self.client.get(reverse("documents:download", args=[self.org_a.slug, self.document.id]))
        self.assertEqual(resp.status_code, 200)

    def test_document_file_has_no_public_url(self):
        # private_storage.url() always raises — Document.file.url can never
        # be embedded as a plain public link, even by accident in a template.
        with self.assertRaises(NotImplementedError):
            _ = self.document.file.url
