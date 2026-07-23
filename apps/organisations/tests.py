from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.permissions import ORG_ROLE_ADMIN
from apps.organisations.models import Organisation, OrganisationMembership


class SmokeTestGoldenPath(TestCase):
    """Exercises Workflow A from the spec: register -> create org -> walk
    the onboarding wizard -> land on the workspace home. Not exhaustive,
    but proves the wiring between accounts/organisations/compliance/
    governance actually holds together end-to-end.
    """

    def test_register_and_onboard(self):
        resp = self.client.post(reverse("accounts:register"), {
            "first_name": "Test", "last_name": "User", "email": "test@example.com",
            "password1": "Sup3rSecurePass!23", "password2": "Sup3rSecurePass!23",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(User.objects.filter(email="test@example.com").exists())

        resp = self.client.get(reverse("organisations:create"))
        self.assertEqual(resp.status_code, 200)

        resp = self.client.post(reverse("organisations:create"), {
            "legal_name": "Siyafunda Community Technology Centre",
            "organisation_type": "npo", "email": "info@siyafunda.org.za",
            "province": "GP", "municipality": "Ekurhuleni",
        })
        self.assertEqual(resp.status_code, 302)
        org = Organisation.objects.get(legal_name="Siyafunda Community Technology Centre")
        self.assertTrue(OrganisationMembership.objects.filter(organisation=org, role=ORG_ROLE_ADMIN).exists())

        resp = self.client.post(
            reverse("organisations:onboarding_step", args=[org.slug, "legal"]),
            {"legal_structure": "npc"},
        )
        self.assertEqual(resp.status_code, 302)

        resp = self.client.post(
            reverse("organisations:onboarding_step", args=[org.slug, "registration"]),
            {"dsd_registered": "True", "cipc_registered": "False"},
        )
        self.assertEqual(resp.status_code, 302)

        resp = self.client.post(
            reverse("organisations:onboarding_step", args=[org.slug, "activities"]),
            {"sectors": "Education, Youth Development", "programme_areas": "Digital Skills"},
        )
        self.assertEqual(resp.status_code, 302)

        resp = self.client.post(reverse("organisations:onboarding_step", args=[org.slug, "compliance"]))
        self.assertEqual(resp.status_code, 302)

        resp = self.client.get(reverse("organisations:onboarding_step", args=[org.slug, "health_check"]))
        self.assertEqual(resp.status_code, 200)
        resp = self.client.post(reverse("organisations:onboarding_step", args=[org.slug, "health_check"]))
        self.assertEqual(resp.status_code, 302)

        org.refresh_from_db()
        self.assertEqual(org.onboarding_step, Organisation.ONBOARDING_COMPLETE)

        resp = self.client.get(reverse("organisations:workspace_home"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Siyafunda")


class TenantIsolationTests(TestCase):
    def setUp(self):
        self.org_a = Organisation.objects.create(legal_name="Org A", organisation_type="npo")
        self.org_b = Organisation.objects.create(legal_name="Org B", organisation_type="npo")
        self.user_a = User.objects.create_user(email="a@example.com", password="Sup3rSecurePass!23")
        self.user_b = User.objects.create_user(email="b@example.com", password="Sup3rSecurePass!23")
        OrganisationMembership.objects.create(organisation=self.org_a, user=self.user_a, role=ORG_ROLE_ADMIN)
        OrganisationMembership.objects.create(organisation=self.org_b, user=self.user_b, role=ORG_ROLE_ADMIN)

    def test_user_cannot_access_other_organisations_360(self):
        self.client.force_login(self.user_a)
        resp = self.client.get(reverse("organisations:org_360", args=[self.org_b.slug]))
        self.assertEqual(resp.status_code, 404)

    def test_user_cannot_access_other_organisations_compliance_passport(self):
        self.client.force_login(self.user_a)
        resp = self.client.get(reverse("compliance:passport", args=[self.org_b.slug]))
        self.assertEqual(resp.status_code, 404)

    def test_user_can_access_own_organisation(self):
        self.client.force_login(self.user_a)
        resp = self.client.get(reverse("organisations:org_360", args=[self.org_a.slug]))
        self.assertEqual(resp.status_code, 200)
