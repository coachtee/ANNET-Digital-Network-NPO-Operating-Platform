from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.permissions import ORG_ROLE_ADMIN
from apps.organisations.models import Organisation, OrganisationMembership

# A minimal, genuinely valid 2x2 PNG (not a hand-typed stub) -- exercises
# real Pillow/ImageField validation, not just the extension check.
def _make_tiny_png_bytes():
    import io as _io
    from PIL import Image as _Image

    buf = _io.BytesIO()
    _Image.new("RGB", (2, 2), color=(10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


_TINY_PNG_BYTES = _make_tiny_png_bytes()


def _tiny_png(name="logo.png"):
    return SimpleUploadedFile(name, _TINY_PNG_BYTES, content_type="image/png")


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


class LogoUploadTests(TestCase):
    """Regression coverage for the confirmed P0 bug: STORAGES had no
    "default" entry, so any plain ImageField/FileField (public_logo here,
    Network.logo in apps.networks) 500'd the moment a file was actually
    attached -- saving the form with no logo never touched storage and
    always worked, which is why the bug went uncaught until now."""

    def setUp(self):
        self.organisation = Organisation.objects.create(legal_name="Logo Test Org", organisation_type="npo")
        self.user = User.objects.create_user(email="admin@example.com", password="Sup3rSecurePass!23")
        OrganisationMembership.objects.create(organisation=self.organisation, user=self.user, role=ORG_ROLE_ADMIN)
        self.client.force_login(self.user)
        self.url = reverse("organisations:public_profile_settings", args=[self.organisation.slug])

    def tearDown(self):
        # Uploaded test files land under MEDIA_ROOT for real (default_storage
        # is genuine FileSystemStorage, not mocked) -- clean them up rather
        # than leaving stray files in the dev media directory.
        self.organisation.refresh_from_db()
        if self.organisation.public_logo:
            self.organisation.public_logo.delete(save=False)

    def test_saving_profile_without_logo_still_works(self):
        resp = self.client.post(self.url, {"public_about": "We do good work."})
        self.assertEqual(resp.status_code, 302)

    def test_uploading_a_valid_logo_succeeds(self):
        resp = self.client.post(self.url, {
            "public_about": "We do good work.",
            "public_logo": _tiny_png(),
        })
        self.assertEqual(resp.status_code, 302)
        self.organisation.refresh_from_db()
        self.assertTrue(self.organisation.public_logo.name)
        self.assertTrue(self.organisation.public_logo.storage.exists(self.organisation.public_logo.name))

    def test_uploading_a_disallowed_extension_shows_validation_error_not_500(self):
        # Valid image bytes (so Django's own Pillow-backed ImageField
        # validation passes) but a format/extension outside
        # ALLOWED_UPLOAD_EXTENSIONS, to isolate apps.core.validators'
        # extension check specifically.
        import io as _io

        from PIL import Image as _Image

        buf = _io.BytesIO()
        _Image.new("RGB", (2, 2)).save(buf, format="BMP")
        bad_file = SimpleUploadedFile("logo.bmp", buf.getvalue(), content_type="image/bmp")

        resp = self.client.post(self.url, {"public_about": "We do good work.", "public_logo": bad_file})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "not allowed")
        self.organisation.refresh_from_db()
        self.assertFalse(self.organisation.public_logo)

    def test_uploading_an_oversized_file_shows_validation_error_not_500(self):
        from django.test import override_settings

        with override_settings(MAX_UPLOAD_SIZE_BYTES=len(_TINY_PNG_BYTES) - 1):
            resp = self.client.post(self.url, {"public_about": "We do good work.", "public_logo": _tiny_png()})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "exceeds the maximum")


class WorkspaceDashboardTests(TestCase):
    """The Organisation Dashboard's Health table must show every dimension
    with its real, live-computed score -- an operational table, not a
    fabricated summary."""

    def setUp(self):
        self.organisation = Organisation.objects.create(
            legal_name="Dashboard Org", organisation_type="npo", province="GP",
            onboarding_step=Organisation.ONBOARDING_COMPLETE,
        )
        self.user = User.objects.create_user(email="orgadmin@example.com", password="Sup3rSecurePass!23")
        OrganisationMembership.objects.create(organisation=self.organisation, user=self.user, role=ORG_ROLE_ADMIN)
        self.client.force_login(self.user)

    def test_dashboard_shows_breadcrumb_summary_bar_and_tabs(self):
        resp = self.client.get(reverse("organisations:workspace_home"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'class="breadcrumbs"')
        self.assertContains(resp, 'class="summary-bar"')
        self.assertContains(resp, 'class="tabs"')
        self.assertContains(resp, "Province")
        self.assertContains(resp, "Category")

    def test_health_table_shows_all_seven_dimensions_with_real_scores(self):
        resp = self.client.get(reverse("organisations:workspace_home"))
        health_rows = resp.context["health_rows"]
        self.assertEqual(len(health_rows), 7)
        labels = {row["label"] for row in health_rows}
        self.assertIn("Registration Readiness", labels)
        self.assertIn("Financial Accountability", labels)
        for row in health_rows:
            self.assertIsInstance(row["score"], int)
        self.assertContains(resp, "Registration Readiness")
        self.assertContains(resp, "Financial Accountability")

    def test_health_table_action_links_point_to_real_pages(self):
        resp = self.client.get(reverse("organisations:workspace_home"))
        governance_row = next(row for row in resp.context["health_rows"] if row["label"] == "Governance")
        self.assertEqual(governance_row["fix_url"], reverse("governance:list", kwargs={"slug": self.organisation.slug}))

    def test_tabs_link_to_existing_working_pages(self):
        resp = self.client.get(reverse("organisations:workspace_home"))
        for url in [
            reverse("beneficiaries:list", kwargs={"slug": self.organisation.slug}),
            reverse("programmes:list", kwargs={"slug": self.organisation.slug}),
            reverse("projects:list", kwargs={"slug": self.organisation.slug}),
            reverse("documents:list", kwargs={"slug": self.organisation.slug}),
            reverse("monitoring_evaluation:dashboard", kwargs={"slug": self.organisation.slug}),
        ]:
            self.assertContains(resp, url)
            self.assertEqual(self.client.get(url).status_code, 200)
