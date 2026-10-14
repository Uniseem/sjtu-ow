#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
work=$(mktemp -d /srv/sjtu-ow-check/ops-301-images/import-permissions.XXXXXX)
mkdir -p "$work/media" "$work/snapshot"
chmod 700 "$work" "$work/snapshot"
python3 - "$work/source.sqlite3" <<'PY'
import sqlite3,sys
from pathlib import Path
with sqlite3.connect(sys.argv[1]) as database:
    database.execute('PRAGMA journal_mode=WAL')
    database.execute('CREATE TABLE accounts_user(id INTEGER PRIMARY KEY)')
    database.execute('CREATE TABLE wagtailcore_page(id INTEGER PRIMARY KEY)')
    database.execute('INSERT INTO accounts_user VALUES(17)')
Path(sys.argv[1]).chmod(0o600)
PY
python3 deploy/rehearsal_input.py "$work/source.sqlite3" "$work/media" "$work/snapshot" > /dev/null
snapshot="$work/snapshot/legacy-source.sqlite3"
before=$(sha256sum "$snapshot" | cut -d ' ' -f1)
if docker run --rm --entrypoint sh -v "$snapshot:/input/legacy.sqlite3:ro" sjtu-ow-next-server:301 -c 'test -r /input/legacy.sqlite3'; then
    echo 'Expected root600 snapshot to reject the nonroot importer' >&2
    exit 1
fi
echo 'BASELINE-ROOT600-IMPORT-REJECTED'
chown 10001:10001 "$snapshot"
chmod 600 "$snapshot"
docker run --rm --entrypoint sh -v "$snapshot:/input/legacy.sqlite3:ro" sjtu-ow-next-server:301 -c 'test -r /input/legacy.sqlite3'
[[ "$before" = "$(sha256sum "$snapshot" | cut -d ' ' -f1)" ]]
[[ "$(stat -c %a "$snapshot")" = 600 && "$(stat -c %a "$work/snapshot")" = 700 ]]
bash -n deploy/cutover.sh
TMPDIR=/srv/sjtu-ow-check/tmp/300-operations python3 deploy/test_rehearsal_input.py
echo 'IMPORT-SNAPSHOT-NONROOT-READ-OK unchanged-content private600 parent700'
