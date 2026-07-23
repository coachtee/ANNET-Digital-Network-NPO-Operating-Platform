from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.permissions import ORG_ROLE_ADMIN, ORG_ROLE_FINANCE_OFFICER
from apps.expenses.models import Budget, Expense
from apps.organisations.models import Organisation, OrganisationMembership
from apps.projects.models import Project


class ExpenseSelfApprovalPreventionTests(TestCase):
    """Release blocker per spec section 30/52: a submitter must never be
    able to approve or reject their own expense claim."""

    def setUp(self):
        self.org = Organisation.objects.create(legal_name="Test Org", organisation_type="npo")
        self.admin = User.objects.create_user(email="admin@example.com", password="Sup3rSecurePass!23")
        self.staff = User.objects.create_user(email="staff@example.com", password="Sup3rSecurePass!23")
        OrganisationMembership.objects.create(organisation=self.org, user=self.admin, role=ORG_ROLE_ADMIN)
        OrganisationMembership.objects.create(organisation=self.org, user=self.staff, role=ORG_ROLE_FINANCE_OFFICER)
        self.project = Project.objects.create(organisation=self.org, name="Test Project")
        Budget.objects.create(project=self.project, total_amount=1000)
        self.expense = Expense.objects.create(
            organisation=self.org, project=self.project, submitted_by=self.staff,
            amount=100, description="Taxi fare",
            receipt=SimpleUploadedFile("receipt.pdf", b"%PDF-1.4 fake", content_type="application/pdf"),
        )

    def test_model_clean_rejects_self_approval(self):
        self.expense.reviewed_by = self.staff
        self.expense.status = Expense.STATUS_APPROVED
        with self.assertRaises(ValidationError):
            self.expense.full_clean()

    def test_view_blocks_submitter_from_reviewing_own_expense(self):
        self.client.force_login(self.staff)
        resp = self.client.post(
            reverse("expenses:review_expense", args=[self.org.slug, self.expense.id]),
            {"status": Expense.STATUS_APPROVED, "review_note": "Looks fine"},
            follow=True,
        )
        self.expense.refresh_from_db()
        self.assertEqual(self.expense.status, Expense.STATUS_SUBMITTED)
        self.assertIsNone(self.expense.reviewed_by)

    def test_a_different_reviewer_can_approve(self):
        self.client.force_login(self.admin)
        resp = self.client.post(
            reverse("expenses:review_expense", args=[self.org.slug, self.expense.id]),
            {"status": Expense.STATUS_APPROVED, "review_note": "Approved"},
        )
        self.assertEqual(resp.status_code, 302)
        self.expense.refresh_from_db()
        self.assertEqual(self.expense.status, Expense.STATUS_APPROVED)
        self.assertEqual(self.expense.reviewed_by, self.admin)
