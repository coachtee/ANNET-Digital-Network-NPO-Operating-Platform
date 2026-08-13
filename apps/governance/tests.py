from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.permissions import ORG_ROLE_ADMIN, ORG_ROLE_BOARD_MEMBER
from apps.documents.models import Document
from apps.governance.models import GovernanceMeeting, GovernanceOfficial, Resolution
from apps.organisations.models import Organisation, OrganisationMembership

PASSWORD = "Sup3rSecurePass!23"


class ResignationEvidenceTests(TestCase):
    """The resignation flow must capture a date, a note, and optionally a
    supporting document -- linked into the Document Vault, not a bespoke
    file field, so it shows up alongside the organisation's other records."""

    def setUp(self):
        self.org = Organisation.objects.create(legal_name="Org A", organisation_type="npo")
        self.admin = User.objects.create_user(email="admin@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.org, user=self.admin, role=ORG_ROLE_ADMIN)
        self.client.force_login(self.admin)
        self.official = GovernanceOfficial.objects.create(
            organisation=self.org, full_name="Thabo Mokoena", position="treasurer", term_start="2024-01-01",
        )

    def test_resigning_with_a_supporting_document_links_it(self):
        resp = self.client.post(
            reverse("governance:resign_official", args=[self.org.slug, self.official.id]),
            {
                "term_end": "2026-08-01", "resignation_note": "Relocating overseas.",
                "supporting_document": SimpleUploadedFile("resignation.pdf", b"%PDF-1.4 fake", content_type="application/pdf"),
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.official.refresh_from_db()
        self.assertEqual(self.official.status, GovernanceOfficial.STATUS_RESIGNED)
        self.assertEqual(self.official.term_end.isoformat(), "2026-08-01")
        self.assertIsNotNone(self.official.resignation_document)
        self.assertEqual(self.official.resignation_document.category, Document.CATEGORY_GOVERNANCE)
        self.assertEqual(self.official.resignation_document.organisation, self.org)

    def test_resigning_without_a_document_still_works(self):
        resp = self.client.post(
            reverse("governance:resign_official", args=[self.org.slug, self.official.id]),
            {"term_end": "2026-08-01", "resignation_note": "Term complete."},
        )
        self.assertEqual(resp.status_code, 302)
        self.official.refresh_from_db()
        self.assertEqual(self.official.status, GovernanceOfficial.STATUS_RESIGNED)
        self.assertIsNone(self.official.resignation_document)

    def test_resignation_date_and_note_are_required(self):
        resp = self.client.post(reverse("governance:resign_official", args=[self.org.slug, self.official.id]), {})
        self.assertEqual(resp.status_code, 200)
        self.official.refresh_from_db()
        self.assertEqual(self.official.status, GovernanceOfficial.STATUS_ACTIVE)

    def test_resigned_official_is_never_deleted(self):
        self.client.post(
            reverse("governance:resign_official", args=[self.org.slug, self.official.id]),
            {"term_end": "2026-08-01", "resignation_note": "Term complete."},
        )
        self.assertTrue(GovernanceOfficial.objects.filter(id=self.official.id).exists())

    def test_board_member_without_manage_capability_cannot_resign_officials(self):
        board_member = User.objects.create_user(email="board@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.org, user=board_member, role=ORG_ROLE_BOARD_MEMBER)
        self.client.force_login(board_member)
        resp = self.client.post(
            reverse("governance:resign_official", args=[self.org.slug, self.official.id]),
            {"term_end": "2026-08-01", "resignation_note": "Term complete."},
        )
        self.assertEqual(resp.status_code, 403)


class MeetingMinutesTests(TestCase):
    def setUp(self):
        self.org = Organisation.objects.create(legal_name="Org A", organisation_type="npo")
        self.admin = User.objects.create_user(email="admin@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.org, user=self.admin, role=ORG_ROLE_ADMIN)
        self.client.force_login(self.admin)
        self.meeting = GovernanceMeeting.objects.create(
            organisation=self.org, meeting_type=GovernanceMeeting.MEETING_BOARD,
            scheduled_date="2026-08-01T10:00:00Z", is_held=True,
        )

    def test_uploading_minutes_links_them_to_the_meeting(self):
        resp = self.client.post(
            reverse("governance:upload_minutes", args=[self.org.slug, self.meeting.id]),
            {"file": SimpleUploadedFile("minutes.pdf", b"%PDF-1.4 fake", content_type="application/pdf")},
        )
        self.assertEqual(resp.status_code, 302)
        self.meeting.refresh_from_db()
        self.assertIsNotNone(self.meeting.minutes_document)
        self.assertEqual(self.meeting.minutes_document.organisation, self.org)

        detail = self.client.get(reverse("governance:meeting_detail", args=[self.org.slug, self.meeting.id]))
        self.assertContains(detail, "Download minutes")

    def test_replacing_minutes_updates_the_link(self):
        self.client.post(
            reverse("governance:upload_minutes", args=[self.org.slug, self.meeting.id]),
            {"file": SimpleUploadedFile("minutes-v1.pdf", b"v1", content_type="application/pdf")},
        )
        first_document_id = GovernanceMeeting.objects.get(id=self.meeting.id).minutes_document_id
        self.client.post(
            reverse("governance:upload_minutes", args=[self.org.slug, self.meeting.id]),
            {"file": SimpleUploadedFile("minutes-v2.pdf", b"v2", content_type="application/pdf")},
        )
        self.meeting.refresh_from_db()
        self.assertNotEqual(self.meeting.minutes_document_id, first_document_id)


class ResolutionTests(TestCase):
    def setUp(self):
        self.org = Organisation.objects.create(legal_name="Org A", organisation_type="npo")
        self.admin = User.objects.create_user(email="admin@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.org, user=self.admin, role=ORG_ROLE_ADMIN)
        self.client.force_login(self.admin)
        self.meeting = GovernanceMeeting.objects.create(
            organisation=self.org, meeting_type=GovernanceMeeting.MEETING_BOARD, scheduled_date="2026-08-01T10:00:00Z",
        )

    def test_recording_a_structured_resolution(self):
        resp = self.client.post(
            reverse("governance:meeting_detail", args=[self.org.slug, self.meeting.id]),
            {"reference_number": "BR-2026-01", "text": "Approve the annual budget.", "decision": Resolution.DECISION_APPROVED},
        )
        self.assertEqual(resp.status_code, 302)
        resolution = Resolution.objects.get(meeting=self.meeting)
        self.assertEqual(resolution.reference_number, "BR-2026-01")
        self.assertEqual(resolution.decision, Resolution.DECISION_APPROVED)
        self.assertEqual(resolution.created_by, self.admin)
        self.assertIsNone(resolution.document)

    def test_recording_a_resolution_with_a_supporting_document(self):
        resp = self.client.post(
            reverse("governance:meeting_detail", args=[self.org.slug, self.meeting.id]),
            {
                "reference_number": "BR-2026-02", "text": "Approve the new signatory.", "decision": Resolution.DECISION_APPROVED,
                "supporting_document": SimpleUploadedFile("resolution.pdf", b"%PDF-1.4 fake", content_type="application/pdf"),
            },
        )
        self.assertEqual(resp.status_code, 302)
        resolution = Resolution.objects.get(meeting=self.meeting)
        self.assertIsNotNone(resolution.document)
        self.assertEqual(resolution.document.object_id, str(resolution.id))

    def test_noted_is_a_valid_decision(self):
        self.client.post(
            reverse("governance:meeting_detail", args=[self.org.slug, self.meeting.id]),
            {"text": "Noted the treasurer's report.", "decision": Resolution.DECISION_NOTED},
        )
        self.assertTrue(Resolution.objects.filter(decision=Resolution.DECISION_NOTED).exists())
