from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.accounts.models import User
from apps.core.utils import ensure_hosts_present


class EnsureSuperuserCommandTests(TestCase):
    """The docker entrypoint calls this on every container startup, so it
    must be safe to run repeatedly without resetting an existing admin's
    password."""

    @override_settings()
    def test_creates_superuser_when_missing(self, *_):
        import os
        os.environ["DJANGO_SUPERUSER_EMAIL"] = "admin@example.com"
        os.environ["DJANGO_SUPERUSER_PASSWORD"] = "InitialGeneratedPass!23"
        try:
            call_command("ensure_superuser")
        finally:
            del os.environ["DJANGO_SUPERUSER_EMAIL"]
            del os.environ["DJANGO_SUPERUSER_PASSWORD"]

        user = User.objects.get(email="admin@example.com")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_platform_admin)
        self.assertTrue(user.check_password("InitialGeneratedPass!23"))

    def test_does_not_reset_password_on_rerun(self):
        import os
        user = User.objects.create_user(email="admin2@example.com", password="OriginalPass!23")
        user.is_superuser = True
        user.is_staff = True
        user.save()

        os.environ["DJANGO_SUPERUSER_EMAIL"] = "admin2@example.com"
        os.environ["DJANGO_SUPERUSER_PASSWORD"] = "SomeNewPassAttempt!23"
        try:
            call_command("ensure_superuser")
        finally:
            del os.environ["DJANGO_SUPERUSER_EMAIL"]
            del os.environ["DJANGO_SUPERUSER_PASSWORD"]

        user.refresh_from_db()
        self.assertTrue(user.check_password("OriginalPass!23"))
        self.assertFalse(user.check_password("SomeNewPassAttempt!23"))


class EnsureHostsPresentTests(TestCase):
    def test_appends_missing_hosts_without_duplicating(self):
        self.assertEqual(
            ensure_hosts_present(["impact.bohlale.co.za"], "127.0.0.1", "localhost"),
            ["impact.bohlale.co.za", "127.0.0.1", "localhost"],
        )

    def test_does_not_duplicate_hosts_already_present(self):
        self.assertEqual(
            ensure_hosts_present(["127.0.0.1", "localhost"], "127.0.0.1", "localhost"),
            ["127.0.0.1", "localhost"],
        )

    def test_does_not_mutate_input_list(self):
        original = ["impact.bohlale.co.za"]
        ensure_hosts_present(original, "127.0.0.1")
        self.assertEqual(original, ["impact.bohlale.co.za"])


class HealthCheckViewTests(TestCase):
    """GET /health/ is the Docker/Kubernetes/Coolify liveness and readiness
    probe — it must require no auth, touch no database, and never redirect,
    since probes hit the container directly over plain HTTP and don't follow
    redirects."""

    def test_returns_200_ok_with_plain_text_body(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"OK")
        self.assertEqual(response["Content-Type"], "text/plain")

    def test_requires_no_authentication(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)

    def test_does_not_query_the_database(self):
        with self.assertNumQueries(0):
            self.client.get("/health/")

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_never_redirects_even_when_ssl_redirect_is_enabled(self):
        response = self.client.get("/health/", secure=False)
        self.assertEqual(response.status_code, 200)
