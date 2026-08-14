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


class StaffLoginEntryPointTests(TestCase):
    """The discreet footer "Operator" link points at a separate login page
    (accounts:staff_login), but authentication and post-login routing are
    identical to the normal login page -- there is no separate auth
    backend or relaxed permission check for this entry point."""

    def setUp(self):
        self.bohlale_impact = Network.objects.create(slug="bohlale-impact", name="Bohlale Impact")

    def test_platform_admin_signing_in_via_staff_login_lands_on_staff_administration(self):
        admin = User.objects.create_user(email="root@example.org", password=PASSWORD, is_platform_admin=True)
        response = self.client.post(
            reverse("accounts:staff_login"), {"username": admin.email, "password": PASSWORD}, follow=True,
        )
        self.assertRedirects(response, reverse("staffadmin:overview"))

    def test_organisation_user_signing_in_via_staff_login_still_lands_on_organisation_dashboard(self):
        organisation = Organisation.objects.create(
            legal_name="Org A", organisation_type="npo", onboarding_step=Organisation.ONBOARDING_COMPLETE,
        )
        user = User.objects.create_user(email="orgadmin@example.org", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=organisation, user=user, role=ORG_ROLE_ADMIN)

        response = self.client.post(
            reverse("accounts:staff_login"), {"username": user.email, "password": PASSWORD}, follow=True,
        )
        self.assertRedirects(response, reverse("organisations:workspace_home"))
        # Signing in through the operator page grants no extra access.
        staff_response = self.client.get(reverse("staffadmin:overview"))
        self.assertEqual(staff_response.status_code, 403)

    def test_network_admin_signing_in_via_staff_login_lands_on_network_dashboard(self):
        user = User.objects.create_user(email="netadmin@example.org", password=PASSWORD)
        NetworkStaffRole.objects.create(network=self.bohlale_impact, user=user, role=NETWORK_ROLE_ADMIN)

        response = self.client.post(
            reverse("accounts:staff_login"), {"username": user.email, "password": PASSWORD}, follow=True,
        )
        self.assertRedirects(response, reverse("networks:dashboard"))


class AccountPersistenceTests(TestCase):
    """P0 UAT blocker regression: an account created once must remain
    usable across logout, re-login and application restart.

    The original failure was NOT an authentication bug -- it was that the
    deployed container fell back to SQLite at /app/db.sqlite3, inside the
    ephemeral image layer, so every restart destroyed the user row and
    login then legitimately failed. These tests pin the authentication
    half of the contract; ``DeploymentPersistenceCheckTests`` pins the
    configuration half that actually caused the data loss.
    """

    def _register(self, email="thabiso@dopa.example.com", password="DopaDemo!2026"):
        return self.client.post(reverse("accounts:register"), {
            "email": email, "first_name": "Thabiso", "last_name": "Naleli",
            "password1": password, "password2": password,
        })

    def test_a_register_logout_then_log_in_again_with_the_same_credentials(self):
        self._register()
        self.assertTrue(User.objects.filter(email="thabiso@dopa.example.com").exists())

        self.client.post(reverse("accounts:logout"))
        self.assertNotIn("_auth_user_id", self.client.session)

        logged_in = self.client.login(username="thabiso@dopa.example.com", password="DopaDemo!2026")
        self.assertTrue(logged_in, "The same credentials must work again after logging out.")

    def test_a2_login_works_through_the_real_login_form(self):
        self._register()
        self.client.post(reverse("accounts:logout"))
        resp = self.client.post(reverse("accounts:login"), {
            "username": "thabiso@dopa.example.com", "password": "DopaDemo!2026",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_a3_unverified_email_does_not_block_logging_back_in(self):
        # Registration sends a verification link but must not lock the
        # account out of the platform if the email is never clicked.
        self._register()
        user = User.objects.get(email="thabiso@dopa.example.com")
        self.assertFalse(user.email_verified)
        self.client.post(reverse("accounts:logout"))
        self.assertTrue(self.client.login(username=user.email, password="DopaDemo!2026"))

    def test_b_organisation_and_programme_survive_logout_and_login(self):
        from apps.programmes.models import Programme

        self._register()
        user = User.objects.get(email="thabiso@dopa.example.com")
        organisation = Organisation.objects.create(legal_name="DOPA", organisation_type="npo")
        OrganisationMembership.objects.create(organisation=organisation, user=user, role=ORG_ROLE_ADMIN)
        programme = Programme.objects.create(organisation=organisation, name="DOPA Youth Digital Skills")

        self.client.post(reverse("accounts:logout"))
        self.assertTrue(self.client.login(username=user.email, password="DopaDemo!2026"))

        resp = self.client.get(reverse("programmes:list", kwargs={"slug": organisation.slug}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "DOPA Youth Digital Skills")
        self.assertEqual(Programme.objects.get(id=programme.id).organisation, organisation)

    def test_c_data_survives_a_simulated_application_restart(self):
        # A restart drops in-process state (sessions, caches, connections)
        # but must never drop committed rows.
        from django.db import connection

        from apps.programmes.models import Programme

        self._register()
        user = User.objects.get(email="thabiso@dopa.example.com")
        organisation = Organisation.objects.create(legal_name="DOPA", organisation_type="npo")
        OrganisationMembership.objects.create(organisation=organisation, user=user, role=ORG_ROLE_ADMIN)
        Programme.objects.create(organisation=organisation, name="DOPA Youth Digital Skills")

        # Simulate the process going away and coming back.
        self.client.post(reverse("accounts:logout"))
        connection.close()
        self.client = self.client_class()

        self.assertTrue(self.client.login(username=user.email, password="DopaDemo!2026"))
        self.assertTrue(Organisation.objects.filter(slug=organisation.slug).exists())
        self.assertTrue(Programme.objects.filter(name="DOPA Youth Digital Skills").exists())

    def test_d_wrong_password_is_rejected(self):
        self._register()
        self.client.post(reverse("accounts:logout"))
        self.assertFalse(self.client.login(username="thabiso@dopa.example.com", password="WrongPassword!1"))
        resp = self.client.post(reverse("accounts:login"), {
            "username": "thabiso@dopa.example.com", "password": "WrongPassword!1",
        })
        self.assertEqual(resp.status_code, 200)  # re-renders the form, no session
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_e_one_organisations_data_never_appears_in_another_account(self):
        from apps.programmes.models import Programme

        self._register()
        dopa_user = User.objects.get(email="thabiso@dopa.example.com")
        dopa = Organisation.objects.create(legal_name="DOPA", organisation_type="npo")
        OrganisationMembership.objects.create(organisation=dopa, user=dopa_user, role=ORG_ROLE_ADMIN)
        Programme.objects.create(organisation=dopa, name="DOPA Confidential Programme")

        other_user = User.objects.create_user(email="other@example.com", password=PASSWORD)
        other_org = Organisation.objects.create(legal_name="Other NPO", organisation_type="npo")
        OrganisationMembership.objects.create(organisation=other_org, user=other_user, role=ORG_ROLE_ADMIN)

        self.client.post(reverse("accounts:logout"))
        self.client.login(username="other@example.com", password=PASSWORD)

        # Their own workspace never shows DOPA's programme...
        resp = self.client.get(reverse("programmes:list", kwargs={"slug": other_org.slug}))
        self.assertNotContains(resp, "DOPA Confidential Programme")
        # ...and DOPA's workspace is not reachable at all.
        resp = self.client.get(reverse("programmes:list", kwargs={"slug": dopa.slug}))
        self.assertEqual(resp.status_code, 404)


class DeploymentPersistenceCheckTests(TestCase):
    """The configuration guard that would have caught the real incident:
    a DEBUG=False deployment must refuse to run on a database that does
    not survive a restart."""

    def _run_check(self, **overrides):
        from apps.core.checks import check_database_is_persistent

        with self.settings(**overrides):
            return check_database_is_persistent(None)

    def test_ephemeral_sqlite_in_production_is_an_error(self):
        from django.conf import settings

        errors = self._run_check(
            DEBUG=False,
            DATABASES={"default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": str(settings.BASE_DIR / "db.sqlite3"),
            }},
        )
        self.assertEqual([e.id for e in errors], ["core.E002"])

    def test_in_memory_sqlite_in_production_is_an_error(self):
        errors = self._run_check(
            DEBUG=False,
            DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
        )
        self.assertEqual([e.id for e in errors], ["core.E001"])

    def test_sqlite_on_a_mounted_volume_is_accepted(self):
        errors = self._run_check(
            DEBUG=False,
            DATABASES={"default": {
                "ENGINE": "django.db.backends.sqlite3", "NAME": "/mnt/persistent/db.sqlite3",
            }},
        )
        self.assertEqual(errors, [])

    def test_postgresql_is_accepted(self):
        errors = self._run_check(
            DEBUG=False,
            DATABASES={"default": {"ENGINE": "django.db.backends.postgresql", "NAME": "bohlale_impact"}},
        )
        self.assertEqual(errors, [])

    def test_local_development_on_sqlite_is_not_flagged(self):
        from django.conf import settings

        errors = self._run_check(
            DEBUG=True,
            DATABASES={"default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": str(settings.BASE_DIR / "db.sqlite3"),
            }},
        )
        self.assertEqual(errors, [])


class SignOutControlTests(TestCase):
    """The "Sign out" control in the app chrome must actually sign the
    user out.

    Regression: it was a plain ``<a href>`` (a GET). Django 5's
    LogoutView accepts POST only, so clicking it returned 405 and left
    the user signed in -- which is what "I logged out and came back"
    really did during UAT.
    """

    def setUp(self):
        self.user = User.objects.create_user(email="member@example.com", password=PASSWORD)
        self.organisation = Organisation.objects.create(legal_name="DOPA", organisation_type="npo")
        OrganisationMembership.objects.create(
            organisation=self.organisation, user=self.user, role=ORG_ROLE_ADMIN,
        )
        self.client.force_login(self.user)

    def test_get_logout_is_not_how_the_ui_signs_out(self):
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)

    def test_post_logout_signs_the_user_out(self):
        resp = self.client.post(reverse("accounts:logout"))
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_workspace_chrome_renders_sign_out_as_a_post_form(self):
        resp = self.client.get(reverse("programmes:list", kwargs={"slug": self.organisation.slug}))
        html = resp.content.decode()
        logout_url = reverse("accounts:logout")
        self.assertIn(f'<form method="post" action="{logout_url}"', html)
        self.assertNotIn(f'<a href="{logout_url}"', html)

    def test_signing_out_then_back_in_works_end_to_end(self):
        self.client.post(reverse("accounts:logout"))
        self.assertTrue(self.client.login(username="member@example.com", password=PASSWORD))
        resp = self.client.get(reverse("programmes:list", kwargs={"slug": self.organisation.slug}))
        self.assertEqual(resp.status_code, 200)
