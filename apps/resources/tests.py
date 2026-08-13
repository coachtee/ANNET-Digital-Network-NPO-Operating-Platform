from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.resources.models import Resource

PASSWORD = "TestPass!2026"


class ResourceManagementPermissionTests(TestCase):
    """Only platform admins can manage resources -- there's no
    "Platform Staff" capability tier yet (see
    STAKEHOLDER_READINESS_ASSESSMENT.md), so this is the same is_platform_admin
    escape hatch used elsewhere, not a new permission model."""

    def setUp(self):
        self.admin = User.objects.create_user(email="admin@example.com", password=PASSWORD, is_platform_admin=True)
        self.regular_user = User.objects.create_user(email="user@example.com", password=PASSWORD)

    def test_platform_admin_can_reach_manage_list(self):
        self.client.login(email=self.admin.email, password=PASSWORD)
        resp = self.client.get(reverse("resources:manage_list"))
        self.assertEqual(resp.status_code, 200)

    def test_regular_user_cannot_reach_manage_list(self):
        self.client.login(email=self.regular_user.email, password=PASSWORD)
        resp = self.client.get(reverse("resources:manage_list"))
        self.assertEqual(resp.status_code, 403)

    def test_anonymous_user_is_redirected_to_login(self):
        resp = self.client.get(reverse("resources:manage_list"))
        self.assertEqual(resp.status_code, 302)

    def test_platform_admin_can_create_a_link_resource(self):
        self.client.login(email=self.admin.email, password=PASSWORD)
        resp = self.client.post(reverse("resources:create"), {
            "title": "Governance Toolkit", "resource_type": Resource.TYPE_TOOLKIT,
            "category": "Governance", "description": "Board pack templates.",
            "external_url": "https://example.org/toolkit.pdf", "status": Resource.STATUS_PUBLISHED,
        })
        self.assertEqual(resp.status_code, 302)
        resource = Resource.objects.get(title="Governance Toolkit")
        self.assertEqual(resource.status, Resource.STATUS_PUBLISHED)
        self.assertIsNotNone(resource.published_at)
        self.assertEqual(resource.created_by, self.admin)

    def test_creating_a_resource_without_file_or_url_is_rejected(self):
        self.client.login(email=self.admin.email, password=PASSWORD)
        resp = self.client.post(reverse("resources:create"), {
            "title": "Nowhere Resource", "resource_type": Resource.TYPE_GUIDE, "status": Resource.STATUS_DRAFT,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Resource.objects.filter(title="Nowhere Resource").exists())


class PublicResourceListingTests(TestCase):
    def setUp(self):
        Resource.objects.create(
            title="Published Guide", resource_type=Resource.TYPE_GUIDE,
            external_url="https://example.org/guide.pdf", status=Resource.STATUS_PUBLISHED,
        )
        Resource.objects.create(
            title="Draft Toolkit", resource_type=Resource.TYPE_TOOLKIT,
            external_url="https://example.org/toolkit.pdf", status=Resource.STATUS_DRAFT,
        )

    def test_public_page_only_shows_published_resources(self):
        resp = self.client.get(reverse("sitepublic:resources"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Published Guide")
        self.assertNotContains(resp, "Draft Toolkit")

    def test_public_page_with_no_published_resources_shows_empty_state(self):
        Resource.objects.all().delete()
        resp = self.client.get(reverse("sitepublic:resources"))
        self.assertContains(resp, "No resources published yet")
