import os

from django.core.management.base import BaseCommand

from apps.accounts.models import User


class Command(BaseCommand):
    """Idempotent, non-interactive superuser bootstrap, called by
    docker/django/entrypoint.sh on every container start.

    Unlike Django's built-in ``createsuperuser --noinput``, this:
    - never touches an existing account's password on re-run (safe to call
      on every container start);
    - reports via exit-code-free stdout markers ("CREATED"/"EXISTS") so the
      entrypoint script knows whether to show the freshly generated password
      or say "credentials unchanged".
    """

    help = "Create the platform admin superuser from DJANGO_SUPERUSER_EMAIL/PASSWORD env vars if it doesn't already exist."

    def handle(self, *args, **options):
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        first_name = os.environ.get("DJANGO_SUPERUSER_FIRST_NAME", "Platform")
        last_name = os.environ.get("DJANGO_SUPERUSER_LAST_NAME", "Administrator")

        if not email or not password:
            self.stderr.write("DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD must be set.")
            return

        user = User.objects.filter(email__iexact=email).first()
        if user is not None:
            self.stdout.write("EXISTS")
            return

        User.objects.create_user(
            email=email, password=password, first_name=first_name, last_name=last_name,
            is_staff=True, is_superuser=True, is_platform_admin=True, email_verified=True,
        )
        self.stdout.write("CREATED")
