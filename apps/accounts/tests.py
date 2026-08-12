from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.permissions import NETWORK_ROLE_ADMIN
from apps.networks.models import Network, NetworkStaffRole

PASSWORD = "TestPass!2026"


class PostLoginRedirectTests(TestCase):
    """A network/programme staff member must always land somewhere they
    can actually access after signing in — not unconditionally on the
    platform's own (primary) network dashboard, which 403s for a staff
    member who only administers a different network/programme."""

    def setUp(self):
        self.bohlale_impact = Network.objects.create(slug="bohlale-impact", name="Bohlale Impact")
        self.black_sash = Network.objects.create(slug="black-sash", name="Black Sash Community Monitoring Programme")

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

    def test_platform_admin_lands_on_primary_dashboard_regardless_of_staff_roles(self):
        admin = User.objects.create_user(email="root@example.org", password=PASSWORD, is_platform_admin=True)
        self.client.login(email=admin.email, password=PASSWORD)

        response = self.client.get(reverse("accounts:post_login_redirect"))
        self.assertRedirects(response, reverse("networks:dashboard"))
