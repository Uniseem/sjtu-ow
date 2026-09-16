from django_tasks_db.management.commands.db_worker import Command as DBWorkerCommand

from core.worker import start_heartbeat_thread


class Command(DBWorkerCommand):
    help = (
        "Run the database task worker and write a heartbeat to the cache "
        "every 30 seconds (design 16.6)."
    )

    def handle(self, *args, **options):
        start_heartbeat_thread()
        super().handle(*args, **options)
