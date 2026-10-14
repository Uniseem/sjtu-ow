"""Strict, private extraction and SQLite snapshot for migration rehearsals.

Never guess a production source. Never follow archive symlinks. Output only
counts and timing in the caller; this module does not print database contents.
"""
from pathlib import Path, PurePosixPath
import os
import sqlite3
import sys
import tarfile


def unpack(source: Path, destination: Path) -> tuple[Path, Path]:
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tarfile.open(source, 'r:gz') as archive:
        members = archive.getmembers()
        for member in members:
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or '\\' in member.name:
                raise ValueError('unsafe backup member path')
            if not member.isfile() and not member.isdir():
                raise ValueError('backup contains link or special file')
            if not path.parts or path.parts[0] not in ('db.sqlite3', 'media'):
                raise ValueError('unexpected backup member')
            if path.parts[0] == 'db.sqlite3' and (len(path.parts) != 1 or not member.isfile()):
                raise ValueError('invalid database member')
        if sum(m.name == 'db.sqlite3' for m in members) != 1:
            raise ValueError('backup must contain exactly one database')
        archive.extractall(destination, members=members, filter='data')
    media = destination / 'media'
    media.mkdir(mode=0o700, exist_ok=True)
    return destination / 'db.sqlite3', media


def snapshot(source: Path, target: Path):
    if not source.is_file() or source.stat().st_size == 0:
        raise ValueError('missing or empty legacy database')
    with sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True) as old:
        if old.execute('PRAGMA quick_check').fetchone() != ('ok',):
            raise ValueError('legacy SQLite quick_check failed')
        tables = {row[0] for row in old.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'accounts_user', 'wagtailcore_page'} <= tables:
            raise ValueError('source is not a legacy Django database')
        with sqlite3.connect(target) as new:
            old.backup(new)
            # backup() retains the source journal mode. A standalone file
            # mounted read-only into the importer cannot initialize WAL/SHM.
            # Convert this coherent copy only; never alter the live source.
            if new.execute('PRAGMA journal_mode=DELETE').fetchone() != ('delete',):
                raise ValueError('snapshot journal conversion failed')
    target.chmod(0o600)


def prepare(source: Path, media: Path | None, work: Path):
    if not source.is_file():
        raise ValueError('explicit legacy input does not exist')
    if source.name.endswith('.tar.gz'):
        if media is not None:
            raise ValueError('backup archive already supplies media')
        database, media = unpack(source, work / 'extracted')
    else:
        database = source
        if media is None or not media.is_dir():
            raise ValueError('legacy database requires an explicit media directory')
    snapshot(database, work / 'legacy-source.sqlite3')
    # Only a path is returned to the shell; it stays on the rehearsal machine.
    return media.resolve()


if __name__ == '__main__':
    os.umask(0o077)
    try:
        print(prepare(Path(sys.argv[1]), Path(sys.argv[2]) if sys.argv[2] else None, Path(sys.argv[3])))
    except (ValueError, OSError, sqlite3.Error, tarfile.TarError):
        print('REHEARSAL-INPUT-FAILED: invalid backup/database/media; no import performed', file=sys.stderr)
        sys.exit(1)
