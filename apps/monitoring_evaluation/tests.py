from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.permissions import ORG_ROLE_ADMIN
from apps.monitoring_evaluation.models import Outcome
from apps.organisations.models import Organisation, OrganisationMembership
from apps.programmes.models import Programme

PASSWORD = "TestPass!2026"


class ProgrammeMEModalPatternTests(TestCase):
    """Outcome/Output/Indicator quick-create each live behind their own
    trigger button and modal on the M&E tab -- tables show data, forms
    stay hidden until asked for, and only the modal whose own form failed
    validation re-opens itself."""

    def setUp(self):
        self.organisation = Organisation.objects.create(legal_name="Org A", organisation_type="npo")
        self.user = User.objects.create_user(email="admin@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.organisation, user=self.user, role=ORG_ROLE_ADMIN)
        self.client.force_login(self.user)
        self.programme = Programme.objects.create(organisation=self.organisation, name="Programme")
        self.url = reverse("monitoring_evaluation:programme_me", kwargs={"slug": self.organisation.slug, "programme_id": self.programme.id})

    def test_all_three_modals_closed_by_default(self):
        resp = self.client.get(self.url)
        self.assertContains(resp, 'data-modal-open="outcome-modal"')
        self.assertContains(resp, 'data-modal-open="output-modal"')
        self.assertContains(resp, 'data-modal-open="indicator-modal"')
        self.assertNotContains(resp, 'data-open-on-load="true"')

    def test_invalid_outcome_submission_only_reopens_the_outcome_modal(self):
        resp = self.client.post(self.url, {"add_outcome": "1", "title": "", "description": ""})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="outcome-modal" data-open-on-load="true"')
        self.assertNotContains(resp, 'id="output-modal" data-open-on-load="true"')
        self.assertNotContains(resp, 'id="indicator-modal" data-open-on-load="true"')

    def test_valid_outcome_submission_redirects_and_is_saved(self):
        resp = self.client.post(self.url, {"add_outcome": "1", "title": "Improved literacy", "description": ""})
        self.assertRedirects(resp, self.url)
        self.assertTrue(Outcome.objects.filter(programme=self.programme, title="Improved literacy").exists())
