from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.organisations.models import Organisation, OrganisationMembership
from apps.core.permissions import ORG_ROLE_ADMIN


class HomePageStatsTests(TestCase):
    """Platform statistics must always be live counts, never hardcoded —
    an empty database must render 0, not a placeholder number."""

    def test_empty_database_shows_zero_stats_and_empty_state(self):
        response = self.client.get(reverse("sitepublic:home"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["registered_organisations"], 0)
        self.assertEqual(response.context["verified_organisations"], 0)
        self.assertEqual(response.context["funding_opportunities"], 0)
        self.assertEqual(response.context["national_networks"], 0)
        self.assertContains(response, "No organisations have joined yet")

    def test_registered_counts_all_organisations_not_only_public(self):
        Organisation.objects.create(legal_name="Private Org", slug="private-org", is_publicly_listed=False)
        Organisation.objects.create(
            legal_name="Public Org", slug="public-org", is_publicly_listed=True,
            public_verification_status="verified",
        )
        response = self.client.get(reverse("sitepublic:home"))
        self.assertEqual(response.context["registered_organisations"], 2)
        self.assertEqual(response.context["verified_organisations"], 1)
        self.assertContains(response, "Public Org")
        self.assertNotContains(response, "Private Org")


class DirectorySearchTests(TestCase):
    def setUp(self):
        self.org = Organisation.objects.create(
            legal_name="Coastal Youth Trust", slug="coastal-youth-trust",
            is_publicly_listed=True, province="WC",
            public_verification_status="verified", sectors=["Youth Development", "Education"],
        )
        Organisation.objects.create(
            legal_name="Highveld Health Foundation", slug="highveld-health-foundation",
            is_publicly_listed=True, province="GP",
            public_verification_status="unverified", sectors=["Health"],
        )

    def test_filters_by_sector(self):
        response = self.client.get(reverse("sitepublic:directory"), {"sector": "Youth Development"})
        orgs = list(response.context["page_obj"])
        self.assertEqual(orgs, [self.org])

    def test_filters_by_verification_status(self):
        response = self.client.get(reverse("sitepublic:directory"), {"verification_status": "verified"})
        orgs = list(response.context["page_obj"])
        self.assertEqual(orgs, [self.org])

    def test_unlisted_organisations_never_appear(self):
        Organisation.objects.create(legal_name="Hidden Org", slug="hidden-org", is_publicly_listed=False)
        response = self.client.get(reverse("sitepublic:directory"))
        self.assertNotContains(response, "Hidden Org")


class OperatorFooterLinkTests(TestCase):
    """A discreet, publicly-visible "Operator" link to the staff login must
    exist in the footer, without exposing any staff functionality or
    surfacing "Admin"/"Platform Administration" wording in public nav."""

    PASSWORD = "TestPass!2026"

    def test_public_homepage_footer_contains_operator_link(self):
        response = self.client.get(reverse("sitepublic:home"))
        self.assertContains(response, 'href="%s"' % reverse("accounts:staff_login"))
        self.assertContains(response, ">Operator<")
        self.assertNotContains(response, "Platform Administration")
        self.assertNotContains(response, ">Admin<")

    def test_operator_link_target_is_a_login_form_not_staff_content(self):
        # The staff-login page itself must never leak staff data to an
        # unauthenticated visitor -- it's just a login form.
        response = self.client.get(reverse("accounts:staff_login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sign in")
        self.assertNotContains(response, "Platform Overview")

    def test_non_platform_user_authenticating_via_staff_login_still_cannot_reach_platform_admin(self):
        organisation = Organisation.objects.create(
            legal_name="Org A", organisation_type="npo", onboarding_step=Organisation.ONBOARDING_COMPLETE,
        )
        user = User.objects.create_user(email="orgadmin@example.org", password=self.PASSWORD)
        OrganisationMembership.objects.create(organisation=organisation, user=user, role=ORG_ROLE_ADMIN)

        login_ok = self.client.login(email=user.email, password=self.PASSWORD)
        self.assertTrue(login_ok)

        # Using the operator entry point doesn't change what the account is
        # permitted to do -- permission checks are unchanged.
        response = self.client.get(reverse("staffadmin:overview"))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_visitor_cannot_reach_platform_admin(self):
        response = self.client.get("/platform-admin/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)
