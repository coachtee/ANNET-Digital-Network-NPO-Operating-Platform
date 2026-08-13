from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.permissions import NETWORK_ROLE_ADMIN, ORG_ROLE_ADMIN
from apps.networks.models import Network, NetworkStaffRole
from apps.organisations.models import Organisation, OrganisationMembership

PASSWORD = "TestPass!2026"


class PostLoginRedirectTests(TestCase):
    """Every account type must land on the area it actually operates in
    after signing in: Bohlale Impact staff on the Staff Administration
    portal, programme/network staff on a network dashboard they can
    actually reach (not unconditionally the platform's own primary-network
    dashboard, which 403s for a staff member who only administers a
    different network/programme), and ordinary organisation users on their
    own organisation's dashboard."""

    def setUp(self):
        self.bohlale_impact = Network.objects.create(slug="bohlale-impact", name="Bohlale Impact")
        self.black_sash = Network.objects.create(slug="black-sash", name="Black Sash Community Monitoring Programme")

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("accounts:post_login_redirect"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_platform_admin_lands_on_staff_administration(self):
        admin = User.objects.create_user(email="root@example.org", password=PASSWORD, is_platform_admin=True)
        self.client.login(email=admin.email, password=PASSWORD)

        response = self.client.get(reverse("accounts:post_login_redirect"))
        self.assertRedirects(response, reverse("staffadmin:overview"))

    def test_platform_admin_who_also_has_a_network_role_still_lands_on_staff_administration(self):
        admin = User.objects.create_user(email="both@example.org", password=PASSWORD, is_platform_admin=True)
        NetworkStaffRole.objects.create(network=self.bohlale_impact, user=admin, role=NETWORK_ROLE_ADMIN)
        self.client.login(email=admin.email, password=PASSWORD)

        response = self.client.get(reverse("accounts:post_login_redirect"))
        self.assertRedirects(response, reverse("staffadmin:overview"))

    def test_platform_admin_manually_visiting_organisation_workspace_still_respects_permissions(self):
        # Being platform staff doesn't grant organisation membership -- a
        # platform admin with no organisation of their own must be routed
        # the same way any other member-less account would be.
        admin = User.objects.create_user(email="root2@example.org", password=PASSWORD, is_platform_admin=True)
        self.client.login(email=admin.email, password=PASSWORD)

        response = self.client.get(reverse("organisations:workspace_home"))
        self.assertRedirects(response, reverse("organisations:create"))

    def test_staff_on_primary_network_lands_on_primary_dashboard(self):
        user = User.objects.create_user(email="admin@bohlale.example.org", password=PASSWORD)
        NetworkStaffRole.objects.create(network=self.bohlale_impact, user=user, role=NETWORK_ROLE_ADMIN)
        self.client.login(email=user.email, password=PASSWORD)

        response = self.client.get(reverse("accounts:post_login_redirect"))
        self.assertRedirects(response, reverse("networks:dashboard"))

    def test_staff_on_non_primary_network_only_lands_on_that_networks_dashboard(self):
        user = User.objects.create_user(email="admin@blacksash.example.org", password=PASSWORD)
        NetworkStaffRole.objects.create(network=self.black_sash, user=user, role=NETWORK_ROLE_ADMIN)
        self.client.login(email=user.email, password=PASSWORD)

        response = self.client.get(reverse("accounts:post_login_redirect"))
        self.assertRedirects(
            response,
            reverse("networks:dashboard_for_network", kwargs={"network_slug": self.black_sash.slug}),
        )
        # And that redirect target must actually be reachable, not another 403.
        follow_up = self.client.get(response.url)
        self.assertEqual(follow_up.status_code, 200)

    def test_organisation_user_lands_on_organisation_dashboard(self):
        organisation = Organisation.objects.create(
            legal_name="Org A", organisation_type="npo", onboarding_step=Organisation.ONBOARDING_COMPLETE,
        )
        user = User.objects.create_user(email="orgadmin@example.org", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=organisation, user=user, role=ORG_ROLE_ADMIN)
        self.client.login(email=user.email, password=PASSWORD)

        response = self.client.get(reverse("accounts:post_login_redirect"))
        self.assertRedirects(response, reverse("organisations:workspace_home"))

    def test_user_with_no_organisation_and_no_staff_role_lands_on_create_organisation(self):
        user = User.objects.create_user(email="new@example.org", password=PASSWORD)
        self.client.login(email=user.email, password=PASSWORD)

        response = self.client.get(reverse("accounts:post_login_redirect"))
        self.assertRedirects(response, reverse("organisations:create"))
