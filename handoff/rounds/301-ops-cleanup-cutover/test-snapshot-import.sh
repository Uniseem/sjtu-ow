#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
source=/srv/sjtu-ow-check/tmp/300-operations/sjtuow-300-operations-zvkig109/db.sqlite3
media=/srv/sjtu-ow-check/tmp/300-operations/sjtuow-300-operations-zvkig109/media
work=/srv/sjtu-ow-check/ops-301-images/standalone-import
test -s "$source" && test -d "$media"
mkdir -p "$work"
chmod 700 "$work"
python3 deploy/rehearsal_input.py "$source" "$media" "$work" > /dev/null
chown 10001:10001 "$work/legacy-source.sqlite3"
chmod 600 "$work/legacy-source.sqlite3"
volume=sjtu-ow-301-snapshot-import-probe
docker volume create --label sjtuow.round=301 "$volume" > /dev/null
cleanup() {
  docker run --rm --entrypoint sh -v "$volume:/srv/sjtuow/data" sjtu-ow-next-server:301 -c 'test ! -e /srv/sjtuow/data/sjtuow.sqlite3 || mv /srv/sjtuow/data/sjtuow.sqlite3 /srv/sjtuow/data/retired.sqlite3'
  docker volume rm "$volume" > /dev/null
}
trap cleanup EXIT
args=(docker run --rm -e SITE_URL=https://example.test -e SIGNING_KEY=operations-test-signing-key-not-production-0123456789 -e FIELD_ENCRYPTION_KEY=operations-test-field-key-not-production-0123456789 -v "$volume:/srv/sjtuow/data" -v "$work/legacy-source.sqlite3:/input/legacy.sqlite3:ro" sjtu-ow-next-server:301)
"${args[@]}" migrate
"${args[@]}" import /input/legacy.sqlite3
"${args[@]}" reconcile /input/legacy.sqlite3
echo 'FICTIONAL-READONLY-CONTAINER-IMPORT-RECONCILE-OK'
