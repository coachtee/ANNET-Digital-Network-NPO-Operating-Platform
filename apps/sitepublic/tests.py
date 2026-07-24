from django.test import TestCase
from django.urls import reverse

from apps.organisations.models import Organisation


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
