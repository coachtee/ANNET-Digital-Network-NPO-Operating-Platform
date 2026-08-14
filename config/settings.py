"""
Django settings for Bohlale Impact — Community Impact Platform.

Configuration is environment-driven (see .env.example). Nothing secret is
hard-coded here — see SECURITY.md for the production hardening checklist.
"""

from pathlib import Path
from decouple import Csv, config

from apps.core.utils import ensure_hosts_present

BASE_DIR = Path(__file__).resolve().parent.parent
# decouple's `config` auto-discovers a .env file relative to this file's
# working directory and otherwise falls back to real environment variables
# — so the app runs unmodified in dev, CI and production.


SECRET_KEY = config("SECRET_KEY", default="django-insecure-CHANGE-ME-IN-PRODUCTION")
DEBUG = config("DEBUG", default=False, cast=bool)
ENVIRONMENT = config("ENVIRONMENT", default="development")  # development | staging | production

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="127.0.0.1,localhost", cast=Csv())
# Container-internal health probes (Docker/Kubernetes/Coolify) hit
# 127.0.0.1:8000 directly, bypassing Traefik/any proxy entirely — so
# whatever ALLOWED_HOSTS an operator configures for the public domain must
# never be able to accidentally lock that probe out. These two are only
# reachable from inside the container's own network namespace in practice,
# not from the public internet, so always-allowing them doesn't weaken
# Host-header validation for real traffic.
ALLOWED_HOSTS = ensure_hosts_present(ALLOWED_HOSTS, "127.0.0.1", "localhost")

CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="", cast=Csv())

# Optional: when set, unhandled 500 errors are emailed here (via Django's
# built-in AdminEmailHandler — see LOGGING below). Disabled by default
# since no SMTP provider can be safely auto-configured; set ADMIN_EMAIL
# and real EMAIL_HOST_* values to enable.
_admin_email = config("ADMIN_EMAIL", default="")
ADMINS = [("Platform Admin", _admin_email)] if _admin_email else []
MANAGERS = ADMINS

# ------------------------------------------------------------------
# Applications
# ------------------------------------------------------------------

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.sitemaps",
]

THIRD_PARTY_APPS = [
    "django_htmx",
]

LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.organisations",
    "apps.networks",
    "apps.memberships",
    "apps.compliance",
    "apps.governance",
    "apps.policies",
    "apps.documents",
    "apps.grants",
    "apps.projects",
    "apps.programmes",
    "apps.beneficiaries",
    "apps.attendance",
    "apps.monitoring_evaluation",
    "apps.expenses",
    "apps.reporting",
    "apps.impact",
    "apps.opportunities",
    "apps.resources",
    "apps.staffadmin",
    "apps.notifications",
    "apps.audit",
    "apps.sitepublic",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "apps.organisations.middleware.OrganisationContextMiddleware",
    "apps.audit.middleware.AuditContextMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.organisations.context_processors.active_organisation",
                "apps.core.context_processors.platform_settings",
                "apps.networks.context_processors.administered_networks",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ------------------------------------------------------------------
# Database
# ------------------------------------------------------------------

if config("DATABASE_URL", default=""):
    # Coolify's managed PostgreSQL resource (and most other PaaS databases)
    # hand you a single connection string rather than separate DB_* values
    # — support both so either integration style works unmodified.
    import dj_database_url

    DATABASES = {"default": dj_database_url.parse(config("DATABASE_URL"), conn_max_age=60)}
elif config("DB_ENGINE", default="sqlite") == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DB_NAME", default="bohlale_impact"),
            "USER": config("DB_USER", default="bohlale_impact"),
            "PASSWORD": config("DB_PASSWORD", default=""),
            "HOST": config("DB_HOST", default="localhost"),
            "PORT": config("DB_PORT", default="5432"),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    # SQLite is for local development and the test suite only. The path is
    # configurable because BASE_DIR inside a container is the *image*
    # directory (/app), which is wiped on every restart/redeploy -- pointing
    # SQLITE_PATH at a mounted volume is what makes a SQLite deployment
    # survive a restart. Production must not rely on this at all: see the
    # ephemeral-database check in apps/core/checks.py, which refuses to let
    # a DEBUG=False deployment run on a non-persistent SQLite file.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": config("SQLITE_PATH", default=str(BASE_DIR / "db.sqlite3")),
        }
    }

# ------------------------------------------------------------------
# Cache (Redis in production/Docker; falls back to in-process memory so
# local dev and the test suite never require a Redis server to be running)
# ------------------------------------------------------------------

REDIS_URL = config("REDIS_URL", default="")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        }
    }
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# ------------------------------------------------------------------
# Auth
# ------------------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:post_login_redirect"
LOGOUT_REDIRECT_URL = "sitepublic:home"

# ------------------------------------------------------------------
# Internationalization
# ------------------------------------------------------------------

LANGUAGE_CODE = "en-za"
TIME_ZONE = config("TIME_ZONE", default="Africa/Johannesburg")
USE_I18N = True
USE_TZ = True

# ------------------------------------------------------------------
# Static & media files
# ------------------------------------------------------------------

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    # Django does not merge a project's STORAGES with its own built-in
    # default -- setting this key at all replaces the whole dict. Omitting
    # "default" left every plain FileField/ImageField (anything without an
    # explicit storage=, e.g. Organisation.public_logo, Network.logo) with
    # nowhere to resolve default_storage, raising InvalidStorageError the
    # moment a file was actually saved through one (HTTP 500 on upload,
    # confirmed via a forced default_storage lookup). Fields that already
    # pass storage=private_storage (documents.Document, expenses.Expense)
    # were unaffected, since that bypasses this registry entirely.
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        # The manifest storage requires `collectstatic` to have been run
        # (it hashes filenames and needs staticfiles.json to resolve
        # {% static %} tags), which is a production deploy step. Falling
        # back to plain static storage in DEBUG means local dev and the
        # test suite work without that extra step.
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if not DEBUG else "django.contrib.staticfiles.storage.StaticFilesStorage"
        ),
    },
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Private (non-public) uploads live under a separate root and are only ever
# served through authenticated, permission-checked views — never through
# MEDIA_URL / the webserver's static file handling. See documents app.
PRIVATE_MEDIA_ROOT = BASE_DIR / "private_media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ------------------------------------------------------------------
# Email
# ------------------------------------------------------------------

EMAIL_BACKEND = config(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = config("EMAIL_HOST", default="")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="Bohlale Impact <no-reply@bohlale.co.za>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL
EMAIL_SUBJECT_PREFIX = config("EMAIL_SUBJECT_PREFIX", default="[Bohlale Impact] ")

# ------------------------------------------------------------------
# Security
# ------------------------------------------------------------------

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # must be readable by JS if forms use it via JS; template tag covers CSRF token
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_REFERRER_POLICY = "same-origin"

# The health check endpoint must never redirect (Docker/Coolify health
# probes hit it over plain HTTP on the container's internal port and don't
# follow redirects) — exempt it from SECURE_SSL_REDIRECT unconditionally,
# not just when DEBUG=False, so this holds regardless of how that setting
# is toggled below.
SECURE_REDIRECT_EXEMPT = [r"^health/?$"]

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
    SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=31536000, cast=int)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    # Coolify's Traefik terminates TLS and reverse-proxies to this
    # container over plain HTTP, setting X-Forwarded-Proto/X-Forwarded-Host
    # — both must be trusted or Django will see every request as
    # insecure/wrong-host and either redirect-loop or reject it.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True

# Uploads
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
MAX_UPLOAD_SIZE_BYTES = config("MAX_UPLOAD_SIZE_BYTES", default=15 * 1024 * 1024, cast=int)
ALLOWED_UPLOAD_EXTENSIONS = [
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv",
    ".png", ".jpg", ".jpeg", ".gif", ".ppt", ".pptx",
]
# Uploaded files (including private compliance evidence and expense
# receipts) are not group/world-readable on disk by default.
FILE_UPLOAD_PERMISSIONS = 0o640
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o750

# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "[{asctime}] {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
        "mail_admins": {"class": "django.utils.log.AdminEmailHandler", "level": "ERROR"},
    },
    "root": {"handlers": ["console"], "level": config("LOG_LEVEL", default="INFO")},
    "loggers": {
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        # Only wired up when ADMINS is non-empty (see ADMIN_EMAIL above) —
        # AdminEmailHandler silently no-ops without recipients, so this is
        # harmless either way, but explicit is clearer than relying on that.
        "django.request": {
            "handlers": ["console"] + (["mail_admins"] if ADMINS else []),
            "level": "ERROR",
            "propagate": False,
        },
    },
}

# ------------------------------------------------------------------
# Platform-specific settings
# ------------------------------------------------------------------

PLATFORM_NAME = config("PLATFORM_NAME", default="Bohlale Impact")
NETWORK_SHORT_NAME = config("NETWORK_SHORT_NAME", default="Bohlale Impact")
NETWORK_TAGLINE = config("NETWORK_TAGLINE", default="Community Impact Platform")
LOAD_DEMO_DATA_ALLOWED = ENVIRONMENT != "production"
