import io
from pathlib import Path
import sqlite3
import tarfile
import tempfile
import unittest
from rehearsal_input import prepare, unpack


class RehearsalInputTests(unittest.TestCase):
    def test_missing_source_never_falls_back_to_an_empty_database(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                prepare(root / 'missing.sqlite3', root, root)
            self.assertFalse((root / 'legacy-source.sqlite3').exists())

    def test_snapshot_includes_committed_wal_and_requires_explicit_media(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source.sqlite3'
            with sqlite3.connect(source) as connection:
                connection.execute('PRAGMA journal_mode=WAL')
                connection.execute('CREATE TABLE accounts_user(id INTEGER)')
                connection.execute('CREATE TABLE wagtailcore_page(id INTEGER)')
                connection.execute('INSERT INTO accounts_user VALUES(17)')
                connection.commit()
                work = root / 'private'
                work.mkdir()
                with self.assertRaises(ValueError):
                    prepare(source, None, work)
                self.assertEqual(prepare(source, root, work), root.resolve())
                with sqlite3.connect(work / 'legacy-source.sqlite3') as snapshot:
                    self.assertEqual(snapshot.execute('SELECT id FROM accounts_user').fetchall(), [(17,)])

    def test_archive_refuses_traversal_links_and_duplicate_database(self):
        for name, kind in [('media/../../escape', tarfile.REGTYPE), ('media/link', tarfile.SYMTYPE), ('/absolute', tarfile.REGTYPE)]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                archive = root / 'backup.tar.gz'
                with tarfile.open(archive, 'w:gz') as bundle:
                    member = tarfile.TarInfo(name)
                    member.type = kind
                    member.linkname = '/etc/passwd' if kind == tarfile.SYMTYPE else ''
                    member.size = 1 if kind == tarfile.REGTYPE else 0
                    bundle.addfile(member, io.BytesIO(b'x') if member.size else None)
                with self.assertRaises(ValueError):
                    unpack(archive, root / 'out')
                self.assertFalse((root / 'escape').exists())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / 'duplicate.tar.gz'
            with tarfile.open(archive, 'w:gz') as bundle:
                for _ in range(2):
                    member = tarfile.TarInfo('db.sqlite3')
                    bundle.addfile(member, io.BytesIO(b''))
            with self.assertRaises(ValueError):
                unpack(archive, root / 'out')


if __name__ == '__main__':
    unittest.main()
