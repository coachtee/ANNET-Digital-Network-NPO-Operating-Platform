from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.permissions import NETWORK_ROLE_ADMIN
from apps.networks.models import Network, NetworkStaffRole

PASSWORD = "TestPass!2026"

# Same root cause as apps.organisations.tests.LogoUploadTests: STORAGES had
# no "default" entry, so any plain ImageField -- Network.logo included --
# 500'd the moment a file was actually saved through it. There's no
# view/form exposing Network.logo yet (only Django admin can set it today),
# so this is a model-level regression test rather than an HTTP one.
def _make_tiny_png_bytes():
    import io as _io
    from PIL import Image as _Image

    buf = _io.BytesIO()
    _Image.new("RGB", (2, 2), color=(10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


_TINY_PNG_BYTES = _make_tiny_png_bytes()


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


class NetworkLogoUploadTests(TestCase):
    def setUp(self):
        self.network = Network.objects.create(slug="bohlale-impact", name="Bohlale Impact")

    def tearDown(self):
        self.network.refresh_from_db()
        if self.network.logo:
            self.network.logo.delete(save=False)

    def test_saving_a_logo_persists_to_storage(self):
        self.network.logo = SimpleUploadedFile("network-logo.png", _TINY_PNG_BYTES, content_type="image/png")
        self.network.save()

        self.network.refresh_from_db()
        self.assertTrue(self.network.logo.name)
        self.assertTrue(self.network.logo.storage.exists(self.network.logo.name))
