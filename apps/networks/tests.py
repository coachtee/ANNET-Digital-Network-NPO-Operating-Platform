from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.permissions import NETWORK_ROLE_ADMIN
from apps.networks.models import Network, NetworkStaffRole

PASSWORD = "TestPass!2026"


class AdministeredNetworksContextProcessorTests(TestCase):
    """The workspace sidebar's "Programme Administration" section must
    only ever link to networks the signed-in user actually administers —
    see apps.networks.context_processors.administered_networks."""

    def setUp(self):
        self.bohlale_impact = Network.objects.create(slug="bohlale-impact", name="Bohlale Impact")
        self.black_sash = Network.objects.create(slug="black-sash", name="Black Sash Community Monitoring Programme")

    def test_staff_on_one_network_only_sees_that_network(self):
        user = User.objects.create_user(email="admin@blacksash.example.org", password=PASSWORD)
        NetworkStaffRole.objects.create(network=self.black_sash, user=user, role=NETWORK_ROLE_ADMIN)
        self.client.login(email=user.email, password=PASSWORD)

        response = self.client.get(reverse("networks:dashboard_for_network", kwargs={"network_slug": self.black_sash.slug}))
        self.assertEqual(list(response.context["administered_networks"]), [self.black_sash])

    def test_platform_admin_sees_every_network(self):
        admin = User.objects.create_user(email="root@example.org", password=PASSWORD, is_platform_admin=True)
        self.client.login(email=admin.email, password=PASSWORD)

        response = self.client.get(reverse("networks:dashboard"))
        self.assertCountEqual(response.context["administered_networks"], [self.bohlale_impact, self.black_sash])

    def test_user_with_no_staff_role_sees_no_networks(self):
        user = User.objects.create_user(email="nobody@example.org", password=PASSWORD)
        self.client.login(email=user.email, password=PASSWORD)

        response = self.client.get(reverse("sitepublic:home"))
        self.assertEqual(list(response.context["administered_networks"]), [])

    def test_anonymous_visitor_sees_no_networks_and_no_extra_queries_crash(self):
        response = self.client.get(reverse("sitepublic:home"))
        self.assertEqual(list(response.context["administered_networks"]), [])
