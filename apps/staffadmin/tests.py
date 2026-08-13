from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.permissions import ORG_ROLE_ADMIN
from apps.memberships.models import MembershipApplication
from apps.networks.models import Network
from apps.opportunities.models import Opportunity
from apps.organisations.models import Organisation, OrganisationMembership
from apps.resources.models import Resource

PASSWORD = "TestPass!2026"

STAFF_URL_NAMES = [
    "staffadmin:overview", "staffadmin:organisation_list", "staffadmin:people_list",
    "staffadmin:network_list", "staffadmin:membership_overview", "staffadmin:opportunity_list",
    "staffadmin:events", "staffadmin:insights", "staffadmin:partnerships",
    "staffadmin:documents", "staffadmin:staff", "staffadmin:reports", "staffadmin:settings",
]


class StaffPortalAccessControlTests(TestCase):
    """The whole point of a separate staff portal is that ordinary
    organisation users can never reach it -- being staff must never leak
    into an organisation's own workspace either."""

    def setUp(self):
        self.org = Organisation.objects.create(legal_name="Org A", organisation_type="npo")
        self.org_admin = User.objects.create_user(email="orgadmin@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.org, user=self.org_admin, role=ORG_ROLE_ADMIN)
        self.platform_admin = User.objects.create_user(email="staff@example.com", password=PASSWORD, is_platform_admin=True)

    def test_organisation_admin_cannot_reach_any_staff_portal_page(self):
        self.client.login(email=self.org_admin.email, password=PASSWORD)
        for url_name in STAFF_URL_NAMES:
            with self.subTest(url_name=url_name):
                resp = self.client.get(reverse(url_name))
                self.assertEqual(resp.status_code, 403)

    def test_anonymous_user_is_redirected_to_login(self):
        resp = self.client.get(reverse("staffadmin:overview"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/accounts/login/", resp.url)

    def test_platform_admin_can_reach_every_staff_portal_page(self):
        self.client.login(email=self.platform_admin.email, password=PASSWORD)
        for url_name in STAFF_URL_NAMES:
            with self.subTest(url_name=url_name):
                resp = self.client.get(reverse(url_name))
                self.assertEqual(resp.status_code, 200)

    def test_organisation_detail_does_not_leak_into_org_workspace_nav(self):
        # Sanity check the reverse direction: the staff portal's own pages
        # never accidentally require organisation membership.
        self.client.login(email=self.platform_admin.email, password=PASSWORD)
        resp = self.client.get(reverse("staffadmin:organisation_detail", args=[self.org.slug]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Org A")


class StaffOverviewMetricsTests(TestCase):
    """Every figure on the staff Overview must come from a real query --
    no hard-coded or estimated numbers (mirrors the same rule already
    enforced on apps.impact's organisation-facing dashboard)."""

    def setUp(self):
        self.platform_admin = User.objects.create_user(email="staff@example.com", password=PASSWORD, is_platform_admin=True)
        self.client.login(email=self.platform_admin.email, password=PASSWORD)
        self.network = Network.objects.create(slug="bohlale-impact", name="Bohlale Impact")
        self.org_verified = Organisation.objects.create(
            legal_name="Verified Org", organisation_type="npo", province="GP",
            is_publicly_listed=True, public_verification_status="verified",
        )
        self.org_unverified = Organisation.objects.create(
            legal_name="Unverified Org", organisation_type="ngo", province="WC",
            is_publicly_listed=True, public_verification_status="unverified",
        )
        MembershipApplication.objects.create(organisation=self.org_unverified, network=self.network, status=MembershipApplication.STATUS_SUBMITTED)
        Opportunity.objects.create(network=self.network, title="Grant A", status=Opportunity.STATUS_PUBLISHED)
        Resource.objects.create(title="Guide A", status=Resource.STATUS_PUBLISHED, external_url="https://example.org/g.pdf")

    def test_overview_metrics_match_real_counts(self):
        resp = self.client.get(reverse("staffadmin:overview"))
        self.assertEqual(resp.context["total_organisations"], 2)
        self.assertEqual(resp.context["verified_organisations"], 1)
        self.assertEqual(resp.context["awaiting_verification"], 1)
        self.assertEqual(resp.context["network_count"], 1)
        self.assertEqual(resp.context["pending_network_applications"], 1)
        self.assertEqual(resp.context["published_opportunities"], 1)
        self.assertEqual(resp.context["published_resources"], 1)

    def test_organisation_list_filters_by_province(self):
        resp = self.client.get(reverse("staffadmin:organisation_list"), {"province": "GP"})
        orgs = list(resp.context["page_obj"])
        self.assertIn(self.org_verified, orgs)
        self.assertNotIn(self.org_unverified, orgs)

    def test_organisation_list_filters_by_category(self):
        resp = self.client.get(reverse("staffadmin:organisation_list"), {"category": "ngo"})
        orgs = list(resp.context["page_obj"])
        self.assertIn(self.org_unverified, orgs)
        self.assertNotIn(self.org_verified, orgs)

    def test_organisation_list_filters_by_verification_status(self):
        resp = self.client.get(reverse("staffadmin:organisation_list"), {"verification_status": "verified"})
        orgs = list(resp.context["page_obj"])
        self.assertIn(self.org_verified, orgs)
        self.assertNotIn(self.org_unverified, orgs)

    def test_organisation_list_table_has_operational_columns_and_row_action(self):
        resp = self.client.get(reverse("staffadmin:organisation_list"))
        self.assertContains(resp, "Joined")
        self.assertContains(resp, "Verified Org")
        self.assertContains(resp, "View")

    def test_overview_shows_breadcrumb_tabs_and_attention_table(self):
        resp = self.client.get(reverse("staffadmin:overview"))
        self.assertContains(resp, "Items Requiring Attention")
        self.assertContains(resp, "Organisations awaiting verification")
        self.assertContains(resp, "Membership applications pending review")
        self.assertContains(resp, 'class="breadcrumbs"')
        self.assertContains(resp, 'class="tabs"')


class OpportunityEditTests(TestCase):
    def setUp(self):
        self.network = Network.objects.create(slug="bohlale-impact", name="Bohlale Impact")
        self.platform_admin = User.objects.create_user(email="staff@example.com", password=PASSWORD, is_platform_admin=True)
        self.client.login(email=self.platform_admin.email, password=PASSWORD)
        self.opportunity = Opportunity.objects.create(network=self.network, title="Grant A", status=Opportunity.STATUS_DRAFT)

    def test_editing_an_opportunity_updates_it(self):
        resp = self.client.post(reverse("opportunities:edit", args=[self.opportunity.id]), {
            "title": "Grant A (Updated)", "opportunity_type": Opportunity.TYPE_FUNDING, "status": Opportunity.STATUS_PUBLISHED,
        })
        self.assertEqual(resp.status_code, 302)
        self.opportunity.refresh_from_db()
        self.assertEqual(self.opportunity.title, "Grant A (Updated)")
        self.assertEqual(self.opportunity.status, Opportunity.STATUS_PUBLISHED)

    def test_archiving_an_opportunity_closes_it(self):
        resp = self.client.post(reverse("opportunities:archive", args=[self.opportunity.id]))
        self.assertEqual(resp.status_code, 302)
        self.opportunity.refresh_from_db()
        self.assertEqual(self.opportunity.status, Opportunity.STATUS_CLOSED)

    def test_org_user_without_network_capability_cannot_edit(self):
        org = Organisation.objects.create(legal_name="Org A", organisation_type="npo")
        org_admin = User.objects.create_user(email="orgadmin@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=org, user=org_admin, role=ORG_ROLE_ADMIN)
        self.client.login(email=org_admin.email, password=PASSWORD)
        resp = self.client.get(reverse("opportunities:edit", args=[self.opportunity.id]))
        self.assertEqual(resp.status_code, 403)
