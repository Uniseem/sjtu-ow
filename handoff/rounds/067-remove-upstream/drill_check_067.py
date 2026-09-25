# Check the migrated database. Run in the 067 checkout after `migrate`:
# python manage.py shell < drill_check_067.py
from django.db import connection

from django_tasks_db.models import DBTaskResult
from tournaments.models import Registration, Tournament


def rows(sql):
    with connection.cursor() as cursor:
        cursor.execute(sql)
        return cursor.fetchall()


def columns(table):
    return [row[1] for row in rows(f"PRAGMA table_info({table})")]


tables = sorted(
    name for (name,) in rows("SELECT name FROM sqlite_master WHERE type='table'")
    if name.startswith("integrations_")
)
indexes = [
    name for (name,) in rows("SELECT name FROM sqlite_master WHERE type='index'")
    if name.startswith("integration")
]
tournament_columns = columns("tournaments_tournament")
log_columns = columns("tournaments_registrationstatuslog")

print("integrations tables left:", tables)
print("integrations indexes left:", indexes)
print(
    "old tournament columns left:",
    [c for c in ("source_client_id", "external_id", "review_mode") if c in tournament_columns],
)
print("auto_approve present:", "auto_approve" in tournament_columns)
print("actor_client_id left:", "actor_client_id" in log_columns)
print("registration statuses:", list(Registration.objects.values_list("status", flat=True)))
print("auto_approve values:", list(Tournament.objects.values_list("auto_approve", flat=True)))
print(
    "integrations tasks left:",
    DBTaskResult.objects.filter(task_path__startswith="integrations.").count(),
    "| other tasks kept:",
    DBTaskResult.objects.exclude(task_path__startswith="integrations.").count(),
)
print(
    "integrations migration rows:",
    [name for (name,) in rows(
        "SELECT name FROM django_migrations WHERE app='integrations' ORDER BY name"
    )],
)
print(
    "tournaments migration rows:",
    [name for (name,) in rows(
        "SELECT name FROM django_migrations WHERE app='tournaments' ORDER BY name"
    )],
)
