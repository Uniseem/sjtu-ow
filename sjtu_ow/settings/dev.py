from sjtu_ow.settings.base import *  # noqa: F403

DEBUG = True

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

PRERENDER_ENABLED = env_bool("PRERENDER_ENABLED", False)  # noqa: F405

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "sjtu-ow-dev",
    }
}

# Database-backed tasks still use SQLite; worker is started in a second terminal.
TASKS = {
    "default": {
        "BACKEND": "django_tasks_db.DatabaseBackend",
        "QUEUES": ["default"],
    }
}
