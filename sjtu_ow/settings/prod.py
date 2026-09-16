from django.core.exceptions import ImproperlyConfigured

from sjtu_ow.settings.base import *  # noqa: F403
from sjtu_ow.settings.base import env, env_bool, env_list

DEBUG = False

SECRET_KEY = env("DJANGO_SECRET_KEY", required=True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be set in production.")

SITE_URL = env("SITE_URL", required=True)
WAGTAILADMIN_BASE_URL = SITE_URL
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
if not CSRF_TRUSTED_ORIGINS:
    raise ImproperlyConfigured("DJANGO_CSRF_TRUSTED_ORIGINS must be set in production.")

FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY", required=True)

# Never let the SSRF guard on webhook URLs be switched off in production.
WEBHOOK_ALLOW_INSECURE_URLS = False
if env_bool("WEBHOOK_ALLOW_INSECURE_URLS", False):
    raise ImproperlyConfigured(
        "WEBHOOK_ALLOW_INSECURE_URLS must not be set in production."
    )

PRERENDER_ENABLED = env_bool("PRERENDER_ENABLED", True)

EMAIL_BACKEND = "core.mail.QueuedEmailBackend"
EMAIL_DELIVERY_BACKEND = "core.mail.SiteSettingsEmailBackend"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "loggers": {
        "sjtu_ow.mail": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "core.middleware.LoggedInHintCookieMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "core.middleware.WagtailAdminCSPMiddleware",
    "core.middleware.RequestIDMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

EMAIL_ALLOWLIST = env_list("EMAIL_ALLOWLIST")
