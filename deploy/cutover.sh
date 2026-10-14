#!/usr/bin/env bash
# Run only after explicit user deployment authorization and green final batch.
# Required: old database path, old media directory, separate reviewed next .env.
set -euo pipefail
umask 077
REPO_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
if [[ $# -ne 3 || "${CUTOVER_AUTHORIZED:-}" != yes ]]; then
    echo "需用户明确授权后: CUTOVER_AUTHORIZED=yes bash deploy/cutover.sh <旧库绝对路径> <旧媒体绝对目录> <新栈.env绝对路径>" >&2
    exit 64
fi
LEGACY_DB=$1
LEGACY_MEDIA=$2
NEXT_ENV=$3
[[ "$LEGACY_DB" = /* && -s "$LEGACY_DB" && "$LEGACY_MEDIA" = /* && -d "$LEGACY_MEDIA" && "$NEXT_ENV" = /* && -f "$NEXT_ENV" ]]
OLD_ENV="$REPO_DIR/.env"
[[ -f "$OLD_ENV" && "$NEXT_ENV" != "$OLD_ENV" ]]
OLD=(docker compose -p sjtu-ow -f "$REPO_DIR/deploy/docker-compose.yml" -f "$REPO_DIR/deploy/docker-compose.vps.yml" --env-file "$OLD_ENV")
NEXT=(docker compose -p sjtu-ow-next -f "$REPO_DIR/deploy/docker-compose.new.yml" --env-file "$NEXT_ENV")
# Optional reviewed, host-specific next override; never reuse the old override.
if [[ -f "$REPO_DIR/deploy/docker-compose.next-vps.yml" ]]; then
    NEXT+=(-f "$REPO_DIR/deploy/docker-compose.next-vps.yml")
fi
"${OLD[@]}" config --quiet
"${NEXT[@]}" config --quiet
# Disk probe happens only in an authorized deployment; no automatic pruning.
python3 - "$REPO_DIR" <<'CHECK_DISK'
import shutil, sys
s = shutil.disk_usage(sys.argv[1])
if s.free / s.total < 0.25 or s.free < 5 * 1024**3:
    raise SystemExit('割接前需至少25%且5GiB空闲；请先由用户授权处理磁盘')
CHECK_DISK
BACKUP_DIR=/root/sjtu-ow-backups/cutover-$(date +%Y%m%d%H%M%S)
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
echo "CUTOVER-BACKUP $BACKUP_DIR"
# Pin the actual running images, not whichever latest tag currently points at.
for service in web worker; do
    container=$("${OLD[@]}" ps -q "$service")
    [[ -n "$container" ]]
    image=$(docker inspect --format '{{.Image}}' "$container")
    docker tag "$image" "sjtu-ow-$service:legacy"
done
cat > "$BACKUP_DIR/legacy-images.yml" <<'IMAGES'
services:
  web:
    image: sjtu-ow-web:legacy
  worker:
    image: sjtu-ow-worker:legacy
IMAGES
cp -p /etc/cron.d/sjtu-ow "$BACKUP_DIR/cron.d-sjtu-ow"
# Isolated project/images are built before entering the maintenance window.
"${NEXT[@]}" build
# Fail rather than import into a previously used Go database.
"${NEXT[@]}" run --rm --no-deps --entrypoint sh server -c 'test ! -e /srv/sjtuow/data/sjtuow.sqlite3'
STARTED=$(date +%s)
# Preserve every old container/volume. Stop writers individually; no down -v.
"${OLD[@]}" stop worker
"${OLD[@]}" stop web
mv /etc/cron.d/sjtu-ow "$BACKUP_DIR/cron.disabled"
# A coherent SQLite backup incorporates WAL; copying only the .sqlite3 would not.
python3 "$REPO_DIR/deploy/rehearsal_input.py" "$LEGACY_DB" "$LEGACY_MEDIA" "$BACKUP_DIR" > "$BACKUP_DIR/media-path"
# The importer runs as UID10001. Keep the private snapshot mode600 and give
# only that account read access; the enclosing host directory stays root700.
chown 10001:10001 "$BACKUP_DIR/legacy-source.sqlite3"
chmod 600 "$BACKUP_DIR/legacy-source.sqlite3"
"${NEXT[@]}" run --rm --no-deps server migrate
"${NEXT[@]}" run --rm --no-deps -v "$BACKUP_DIR/legacy-source.sqlite3:/input/legacy.sqlite3:ro" server import /input/legacy.sqlite3
"${NEXT[@]}" run --rm --no-deps -v "$LEGACY_MEDIA:/input/media:ro" server import-media /input/media
"${NEXT[@]}" run --rm --no-deps -v "$BACKUP_DIR/legacy-source.sqlite3:/input/legacy.sqlite3:ro" -v "$LEGACY_MEDIA:/input/media:ro" server import-fonts /input/legacy.sqlite3 /input/media
"${NEXT[@]}" run --rm --no-deps -v "$BACKUP_DIR/legacy-source.sqlite3:/input/legacy.sqlite3:ro" server reconcile /input/legacy.sqlite3
# The old proxy still serves existing public prerenders during import.
"${OLD[@]}" stop proxy
"${NEXT[@]}" up -d
# After this point new writes may exist: never restore an old database blindly.
port=${CUTOVER_PORT:-22887}
ready=0
for attempt in $(seq 1 30); do
    if curl --fail --silent "http://127.0.0.1:$port/healthz" > /dev/null; then ready=1; break; fi
    sleep 2
done
[[ "$ready" = 1 ]] || { echo '健康检查失败；保留新旧库，按cutover.md的数据闸处理，禁止覆盖恢复' >&2; exit 1; }
echo "CUTOVER-HEALTH-OK elapsed=$(( $(date +%s) - STARTED )) backup=$BACKUP_DIR"
