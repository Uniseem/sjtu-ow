import json
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
    "wagtail.contrib.settings",
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
    "allauth",
    "allauth.account",
    "django_htmx",
    "django_tailwind_cli",
    "django_tasks_db",
    "rest_framework",
    "drf_spectacular",
    "drf_spectacular_sidecar",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "core.middleware.LoggedInHintCookieMiddleware",
    "core.middleware.PrerenderMissMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "core.middleware.WagtailAdminCSPMiddleware",
    "core.middleware.RequestIDMiddleware",
    "integrations.middleware.ApiRequestLogMiddleware",
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
                "content.context_processors.seo",
                "core.context_processors.fonts",
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

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

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

LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

EMAIL_BACKEND = "core.mail.QueuedEmailBackend"
EMAIL_DELIVERY_BACKEND = "core.mail.SiteSettingsEmailBackend"
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "noreply@localhost")

# django-allauth 65.19.3 (official setting names for this series).
# Match allauth's shipped migrations (integer AutoField PKs).
ALLAUTH_DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
ALLAUTH_USER_CODE_FORMAT = {"length": 6, "numeric": True, "dashed": False}
ACCOUNT_ADAPTER = "accounts.adapter.AccountAdapter"
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_USER_DISPLAY = "accounts.adapter.user_display"
ACCOUNT_SIGNUP_FORM_CLASS = "accounts.forms.SignupExtraForm"
ACCOUNT_FORMS = {
    "login": "accounts.allauth_forms.LoginForm",
    "signup": "accounts.allauth_forms.SignupForm",
    "add_email": "accounts.allauth_forms.AddEmailForm",
    "change_email": "accounts.allauth_forms.ChangeEmailForm",
    "change_password": "accounts.allauth_forms.ChangePasswordForm",
    "set_password": "accounts.allauth_forms.SetPasswordForm",
    "reset_password": "accounts.allauth_forms.ResetPasswordForm",
    "reset_password_from_key": "accounts.allauth_forms.ResetPasswordKeyForm",
    "reauthenticate": "accounts.allauth_forms.ReauthenticateForm",
    "confirm_email_verification_code": (
        "accounts.allauth_forms.ConfirmEmailVerificationCodeForm"
    ),
    "confirm_password_reset_code": (
        "accounts.allauth_forms.ConfirmPasswordResetCodeForm"
    ),
}
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED = True
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_MAX_ATTEMPTS = 3
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_TIMEOUT = 15 * 60
ACCOUNT_EMAIL_VERIFICATION_SUPPORTS_RESEND = True
ACCOUNT_PASSWORD_RESET_BY_CODE_ENABLED = True
ACCOUNT_PASSWORD_RESET_BY_CODE_MAX_ATTEMPTS = 3
ACCOUNT_PASSWORD_RESET_BY_CODE_TIMEOUT = 3 * 60
ACCOUNT_CHANGE_EMAIL = True
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_PREVENT_ENUMERATION = True
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_EMAIL_SUBJECT_PREFIX = ""
ACCOUNT_RATE_LIMITS = {
    "signup": "20/m/ip",
    "login": "30/m/ip",
    "login_failed": "10/m/ip,5/300s/key",
    "reset_password": "20/m/ip,5/m/key",
    "confirm_email": "1/10s/key",
    "manage_email": "10/m/user",
    "change_password": "5/m/user",
    "reset_password_from_key": "20/m/ip",
    "reauthenticate": "10/m/user",
}

SECURE_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF],
    "style-src": [CSP.SELF],
    "img-src": [CSP.SELF, "data:"],
    "font-src": [CSP.SELF],
    "connect-src": [CSP.SELF],
    "frame-src": [
        CSP.SELF,
        "https://player.bilibili.com",
    ],
    "frame-ancestors": [CSP.NONE],
    "base-uri": [CSP.SELF],
    "form-action": [CSP.SELF],
}

WAGTAIL_SITE_NAME = "上海交通大学守望先锋社区"
WAGTAILADMIN_BASE_URL = SITE_URL
WAGTAILADMIN_LOGIN_URL = "account_login"
ADMIN_URL_PREFIX = "/admin/"
WAGTAIL_PASSWORD_MANAGEMENT_ENABLED = False
# No Gravatar: the admin CSP allows no external images, so the avatars only
# ever rendered blank, and looking one up sends a hash of the admin's email
# to a third party — which the privacy policy does not cover.
WAGTAIL_GRAVATAR_PROVIDER_URL = None
WAGTAILSEARCH_BACKENDS = {
    "default": {
        "BACKEND": "wagtail.search.backends.database",
    }
}
WAGTAILEMBEDS_FINDERS = [
    {
        "class": "content.embeds.BilibiliEmbedFinder",
    }
]
WAGTAILIMAGES_MAX_UPLOAD_SIZE = 5 * 1024 * 1024
WAGTAILIMAGES_EXTENSIONS = ["jpg", "jpeg", "png", "webp"]

TAILWIND_CLI_USE_DAISY_UI = True
# Source lives outside STATICFILES_DIRS so collectstatic/hashed storage
# does not pick up @import "tailwindcss" (django-tailwind-cli W001).
TAILWIND_CLI_SRC_CSS = BASE_DIR / "assets" / "css" / "input.css"
TAILWIND_CLI_DIST_CSS = "css/app.css"
# tailwind-cli-extra v2.9.0 = Tailwind CSS 4.3.2 + daisyUI 5.6.10
TAILWIND_CLI_VERSION = "2.9.0"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "integrations.api.exception_handler",
}
SPECTACULAR_SETTINGS = {
    "TITLE": "上海交通大学守望先锋社区 开放 API",
    "VERSION": "v1",
    "SERVE_INCLUDE_SCHEMA": False,
    # Only the upstream-facing API; Wagtail's admin API is not a contract.
    "PREPROCESSING_HOOKS": ["integrations.schema.only_public_api"],
    # Serve Swagger UI from our own static files. The site's CSP forbids CDN
    # scripts (README「自托管前端脚本」), and the default CDN build renders blank.
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
}
# API signing (design 11.2)
API_TIMESTAMP_TOLERANCE = 300  # seconds
API_NONCE_TTL = 600  # seconds

# Design 11.8.3 requires webhook URLs to be public https addresses. This flag
# lifts that check so development can point a webhook at a local receiver; it
# is refused in production (see settings/prod.py).
WEBHOOK_ALLOW_INSECURE_URLS = env_bool("WEBHOOK_ALLOW_INSECURE_URLS", False)

PRERENDER_ENABLED = env_bool("PRERENDER_ENABLED", False)
PRERENDER_ROOT = Path(env("PRERENDER_ROOT", str(BASE_DIR / "prerendered")))

# Local backups (design 16.2, 16.7). Kept for BACKUP_KEEP_DAYS days.
BACKUP_ROOT = Path(env("BACKUP_ROOT", str(BASE_DIR / "backups")))
# Design 16.7: backups are encrypted before they leave the server. This key
# must NOT live in the database — it would then be inside the very backup it
# protects. Keep it in the club's password manager alongside SECRET_KEY.
BACKUP_ENCRYPTION_KEY = env("BACKUP_ENCRYPTION_KEY", "")
BACKUP_KEEP_DAYS = int(env("BACKUP_KEEP_DAYS", "14"))
# Design 16.5: old static files linger for a month after an upgrade.
STATIC_KEEP_DAYS = int(env("STATIC_KEEP_DAYS", "30"))

# Placeholder until M5 / M2. Read here so production env is complete (design 16.3).
FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY", "dev-insecure-field-encryption-key")
MODERATION_API_KEY = env("MODERATION_API_KEY", "")
MODERATION_BASE_URL = env("MODERATION_BASE_URL", "")
MODERATION_TIMEOUT = int(env("MODERATION_TIMEOUT", "30"))
MODERATION_MAX_OUTPUT_TOKENS = int(env("MODERATION_MAX_OUTPUT_TOKENS", "600"))
# Extra body fields for the provider, e.g. the switch that turns thinking off.
# The exact key differs per provider, so it stays configuration, not code.
MODERATION_EXTRA_BODY = json.loads(env("MODERATION_EXTRA_BODY", "{}"))
SENTRY_DSN = env("SENTRY_DSN", "")
EMAIL_ALLOWLIST = env_list("EMAIL_ALLOWLIST")

DISK_MIN_FREE_RATIO = 0.20
HEALTH_PROBE_BUSY_TIMEOUT_MS = 200
HEALTHZ_CACHE_TABLE = "django_cache"
