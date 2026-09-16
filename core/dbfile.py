"""Where the SQLite database actually lives right now.

``settings.DATABASE_PATH`` is the configured default, but the connection is
the authority: under tests Django swaps in ``TEST["NAME"]``, and a command
that backed up ``DATABASE_PATH`` would snapshot the wrong file.
"""

from pathlib import Path

from django.db import connection


def database_path() -> Path:
    return Path(connection.settings_dict["NAME"])


def wal_siblings(database: Path | None = None) -> list[Path]:
    database = database or database_path()
    return [database.with_name(database.name + suffix) for suffix in ("-wal", "-shm")]
