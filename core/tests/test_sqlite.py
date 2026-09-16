import pytest
from django.db import connection


@pytest.mark.django_db
def test_sqlite_pragma_and_options():
    options = connection.settings_dict["OPTIONS"]
    assert options["transaction_mode"] == "IMMEDIATE"
    assert options["timeout"] == 5
    assert "journal_mode=WAL" in options["init_command"]
    assert "synchronous=NORMAL" in options["init_command"]

    with connection.cursor() as cursor:
        cursor.execute("PRAGMA journal_mode")
        journal_mode = cursor.fetchone()[0]
        cursor.execute("PRAGMA synchronous")
        synchronous = cursor.fetchone()[0]

    assert str(journal_mode).lower() == "wal"
    # SQLite returns 1 for NORMAL.
    assert str(synchronous).lower() in {"1", "normal"}
