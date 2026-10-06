from django_tasks_db.management.commands.db_worker import Command as DBWorkerCommand

from core.worker import reset_orphaned_running_tasks, start_heartbeat_thread


class Command(DBWorkerCommand):
    help = (
        "Run the database task worker and write a heartbeat to the cache "
        "every 30 seconds (design 16.6); on the same beat, publish pages whose "
        "scheduled time has come (16.5)."
    )

    def handle(self, *args, **options):
        # Before taking new work: tasks left RUNNING by a killed worker
        # (design 16.2, v7.17).
        reset_orphaned_running_tasks()
        start_heartbeat_thread()
        super().handle(*args, **options)
