from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from apps.accounts.models import User


class EnsureSuperuserCommandTests(TestCase):
    """The docker entrypoint / deploy.sh call this on every startup, so it
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
