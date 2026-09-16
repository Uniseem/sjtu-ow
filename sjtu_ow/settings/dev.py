from sjtu_ow.settings.base import *  # noqa: F403

DEBUG = True

EMAIL_DELIVERY_BACKEND = "django.core.mail.backends.console.EmailBackend"

PRERENDER_ENABLED = env_bool("PRERENDER_ENABLED", False)  # noqa: F405

# DatabaseCache is required so the worker heartbeat is visible to /healthz
# in a second process. LocMemCache is process-local and would hide a dead worker.

# Database-backed tasks still use SQLite; worker is started in a second terminal.
TASKS = {
    "default": {
        "BACKEND": "django_tasks_db.DatabaseBackend",
        "QUEUES": ["default"],
    }
}
