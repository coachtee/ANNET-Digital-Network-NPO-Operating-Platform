"""Deployment safety checks.

These exist because of a real P0 data-loss incident found in UAT: a
production container was running on the SQLite fallback at
``BASE_DIR / "db.sqlite3"``. That path lives in the container's ephemeral
writable layer (BASE_DIR is /app, the image directory, and db.sqlite3 is
in .dockerignore so it is never even baked in), and nothing mounts a
volume over it. Every restart or redeploy therefore began with no
database file at all, the entrypoint's ``migrate`` recreated an empty
schema, and every registered user, organisation and programme was gone.

The symptom looked like broken authentication ("I can't log back in with
the same credentials") but authentication was fine -- the user row no
longer existed. Nothing in the stack said a word about it, so the fix is
to make that configuration refuse to run rather than lose data quietly.
"""

from pathlib import Path

from django.conf import settings
from django.core.checks import Error, Tags, register

SQLITE_ENGINE = "django.db.backends.sqlite3"

# Paths that are known to be image/ephemeral rather than a mounted volume.
# A SQLite file anywhere under BASE_DIR is inside the container image
# directory; only an explicitly mounted path outside it can survive.
def _is_ephemeral_sqlite_path(name):
    try:
        db_path = Path(name).resolve()
    except (TypeError, ValueError):
        return True
    try:
        db_path.relative_to(Path(settings.BASE_DIR).resolve())
    except ValueError:
        # Outside BASE_DIR -- assumed to be a deliberately mounted volume.
        return False
    return True


@register(Tags.database, deploy=True)
def check_database_is_persistent(app_configs, **kwargs):
    """Refuse to run a real deployment on an ephemeral SQLite file.

    Registered as a *deploy* check, so it runs under
    ``manage.py check --deploy`` (which the container entrypoint runs
    before starting gunicorn) and stays out of the way of local
    development and the test suite -- both of which legitimately run on
    SQLite under BASE_DIR, and both of which run with DEBUG forced off.
    """
    if settings.DEBUG:
        return []

    default = settings.DATABASES.get("default", {})
    if default.get("ENGINE") != SQLITE_ENGINE:
        return []

    name = default.get("NAME")
    # An in-memory database in a DEBUG=False process is always wrong.
    if str(name) in (":memory:", "") or name is None:
        return [
            Error(
                "The application is configured to run on an in-memory SQLite database "
                "with DEBUG=False. All data would be lost when the process exits.",
                hint="Set DATABASE_URL to your PostgreSQL connection string.",
                id="core.E001",
            )
        ]

    if _is_ephemeral_sqlite_path(name):
        return [
            Error(
                f"The application is configured to run on SQLite at {name} with "
                "DEBUG=False. That path is inside the application/image directory, so "
                "it is destroyed on every container restart or redeploy, taking every "
                "user, organisation and programme with it.",
                hint=(
                    "Set DATABASE_URL to your managed PostgreSQL connection string "
                    "(recommended -- see COOLIFY.md), or, if you genuinely intend to "
                    "run on SQLite, set SQLITE_PATH to a path on a mounted persistent "
                    "volume (e.g. SQLITE_PATH=/app/data/db.sqlite3 with a volume "
                    "mounted at /app/data)."
                ),
                id="core.E002",
            )
        ]

    return []
