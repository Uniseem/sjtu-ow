from pathlib import Path

from django.utils.csp import CSP

from sjtu_ow.settings.env import env, env_bool, env_list

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = env(
    "DJANGO_SECRET_KEY", "dev-insecure-secret-key-do-not-use-in-production"
)

DEBUG = False

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")

SITE_URL = env("SITE_URL", "http://localhost:8000")

INSTALLED_APPS = [
    "accounts",
    "core",
    "content",
    "teams",
    "lfg",
    "tournaments",
    "scrims",
    "moderation",
    "integrations",
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtail",
    "modelcluster",
    "taggit",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_htmx",
    "django_tailwind_cli",
    "django_tasks_db",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "core.middleware.WagtailAdminCSPMiddleware",
    "core.middleware.RequestIDMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
]

ROOT_URLCONF = "sjtu_ow.urls"

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
            ],
        },
    },
]

WSGI_APPLICATION = "sjtu_ow.wsgi.application"

DATABASE_PATH = Path(env("DATABASE_PATH", str(BASE_DIR / "data" / "db.sqlite3")))

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATABASE_PATH,
        "OPTIONS": {
            "transaction_mode": "IMMEDIATE",
            "timeout": 5,
            "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;",
        },
        # File-backed tests so WAL/synchronous PRAGMAs can be asserted.
        # Django's default in-memory test DB reports journal_mode=memory.
        "TEST": {
            "NAME": BASE_DIR / "data" / "test.sqlite3",
        },
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
    }
}

TASKS = {
    "default": {
        "BACKEND": "django_tasks_db.DatabaseBackend",
        "QUEUES": ["default"],
    }
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = Path(env("STATIC_ROOT", str(BASE_DIR / "staticfiles")))
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", str(BASE_DIR / "media")))

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_AGE = 14 * 24 * 60 * 60
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
# HTMX reads the CSRF cookie in static/js/app.js (design 13.7 / 13.13.3).
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:8000")

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

SECURE_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF],
    "style-src": [CSP.SELF],
    "img-src": [CSP.SELF, "data:"],
    "font-src": [CSP.SELF],
    "connect-src": [CSP.SELF],
    "frame-ancestors": [CSP.NONE],
    "base-uri": [CSP.SELF],
    "form-action": [CSP.SELF],
}

WAGTAIL_SITE_NAME = "上海交通大学守望先锋社区"
WAGTAILADMIN_BASE_URL = SITE_URL
ADMIN_URL_PREFIX = "/admin/"
WAGTAIL_PASSWORD_MANAGEMENT_ENABLED = False
WAGTAILSEARCH_BACKENDS = {
    "default": {
        "BACKEND": "wagtail.search.backends.database",
    }
}

TAILWIND_CLI_USE_DAISY_UI = True
# Source lives outside STATICFILES_DIRS so collectstatic/hashed storage
# does not pick up @import "tailwindcss" (django-tailwind-cli W001).
TAILWIND_CLI_SRC_CSS = BASE_DIR / "assets" / "css" / "input.css"
TAILWIND_CLI_DIST_CSS = "css/app.css"
# tailwind-cli-extra v2.9.0 = Tailwind CSS 4.3.2 + daisyUI 5.6.10
TAILWIND_CLI_VERSION = "2.9.0"

PRERENDER_ENABLED = env_bool("PRERENDER_ENABLED", False)
PRERENDER_ROOT = Path(env("PRERENDER_ROOT", str(BASE_DIR / "prerendered")))

# Placeholder until M5 / M2. Read here so production env is complete (design 16.3).
FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY", "")
MODERATION_API_KEY = env("MODERATION_API_KEY", "")
MODERATION_BASE_URL = env("MODERATION_BASE_URL", "")
SENTRY_DSN = env("SENTRY_DSN", "")
EMAIL_ALLOWLIST = env_list("EMAIL_ALLOWLIST")

DISK_MIN_FREE_RATIO = 0.20
HEALTH_PROBE_BUSY_TIMEOUT_MS = 200
HEALTHZ_CACHE_TABLE = "django_cache"
