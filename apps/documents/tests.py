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
        # private_storage.url() always raises -- Document.file.url can never
        # be embedded as a plain public link, even by accident in a template.
        with self.assertRaises(NotImplementedError):
            _ = self.document.file.url


class DocumentVisibilityTests(TestCase):
    """VISIBILITY_PRIVATE must be narrower than the general documents.view
    capability every org member with view access holds -- previously
    unenforced (any org member with documents.view could read a "private"
    document, which defeated the point of the tighter visibility level)."""

    def setUp(self):
        self.org = Organisation.objects.create(legal_name="Org A", organisation_type="npo")
        self.admin = User.objects.create_user(email="admin@example.com", password="Sup3rSecurePass!23")
        self.staff = User.objects.create_user(email="staff@example.com", password="Sup3rSecurePass!23")
        OrganisationMembership.objects.create(organisation=self.org, user=self.admin, role=ORG_ROLE_ADMIN)
        OrganisationMembership.objects.create(organisation=self.org, user=self.staff, role="staff")
        self.private_doc = Document.objects.create(
            organisation=self.org, title="Board Minutes", uploaded_by=self.admin, visibility=Document.VISIBILITY_PRIVATE,
            file=SimpleUploadedFile("minutes.pdf", b"%PDF-1.4 fake", content_type="application/pdf"),
        )
        self.org_doc = Document.objects.create(
            organisation=self.org, title="Volunteer Handbook", uploaded_by=self.admin, visibility=Document.VISIBILITY_ORGANISATION,
            file=SimpleUploadedFile("handbook.pdf", b"%PDF-1.4 fake", content_type="application/pdf"),
        )

    def test_staff_without_manage_cannot_download_private_document(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse("documents:download", args=[self.org.slug, self.private_doc.id]))
        self.assertEqual(resp.status_code, 403)

    def test_staff_can_download_organisation_visibility_document(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse("documents:download", args=[self.org.slug, self.org_doc.id]))
        self.assertEqual(resp.status_code, 200)

    def test_admin_can_download_private_document(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("documents:download", args=[self.org.slug, self.private_doc.id]))
        self.assertEqual(resp.status_code, 200)


class DocumentArchiveAndVersionTests(TestCase):
    def setUp(self):
        self.org = Organisation.objects.create(legal_name="Org A", organisation_type="npo")
        self.admin = User.objects.create_user(email="admin@example.com", password="Sup3rSecurePass!23")
        OrganisationMembership.objects.create(organisation=self.org, user=self.admin, role=ORG_ROLE_ADMIN)
        self.client.force_login(self.admin)
        self.document = Document.objects.create(
            organisation=self.org, title="Constitution", uploaded_by=self.admin,
            file=SimpleUploadedFile("constitution.pdf", b"%PDF-1.4 v1", content_type="application/pdf"),
        )

    def test_archive_moves_document_out_of_the_active_list(self):
        resp = self.client.post(reverse("documents:archive", args=[self.org.slug, self.document.id]))
        self.assertEqual(resp.status_code, 302)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, Document.STATUS_ARCHIVED)

        active_resp = self.client.get(reverse("documents:list", args=[self.org.slug]))
        self.assertNotContains(active_resp, "Constitution")
        archived_resp = self.client.get(reverse("documents:list", args=[self.org.slug]) + "?show=archived")
        self.assertContains(archived_resp, "Constitution")

    def test_uploading_a_new_version_supersedes_the_old_one(self):
        resp = self.client.post(
            reverse("documents:new_version", args=[self.org.slug, self.document.id]),
            {"file": SimpleUploadedFile("constitution-v2.pdf", b"%PDF-1.4 v2", content_type="application/pdf")},
        )
        self.assertEqual(resp.status_code, 302)

        self.document.refresh_from_db()
        self.assertEqual(self.document.status, Document.STATUS_ARCHIVED)

        new_version = Document.objects.exclude(id=self.document.id).get(organisation=self.org)
        self.assertEqual(new_version.version, 2)
        self.assertEqual(new_version.supersedes, self.document)
        self.assertEqual(new_version.status, Document.STATUS_ACTIVE)
        self.assertEqual(new_version.title, "Constitution")

    def test_document_detail_shows_version_history(self):
        self.client.post(
            reverse("documents:new_version", args=[self.org.slug, self.document.id]),
            {"file": SimpleUploadedFile("constitution-v2.pdf", b"%PDF-1.4 v2", content_type="application/pdf")},
        )
        new_version = Document.objects.exclude(id=self.document.id).get(organisation=self.org)
        resp = self.client.get(reverse("documents:detail", args=[self.org.slug, new_version.id]))
        self.assertContains(resp, "Version 2")
        self.assertContains(resp, "Version 1")
