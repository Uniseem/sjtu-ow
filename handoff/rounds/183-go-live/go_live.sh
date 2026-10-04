#!/bin/sh
# Round 183: the demo site at 169.58.217.180 becomes the production site.
# Demo people and content go; the image library stays (export, fresh
# database, import). Run on the server from /srv/sjtu-ow, detached:
#   setsid sh /root/go_live.sh > /root/go_live.log 2>&1 < /dev/null &
set -eu
T0=$(date +%s)
say() { echo "[$(( $(date +%s) - T0 ))s] $*"; }
cd /srv/sjtu-ow
C="docker compose -p sjtu-ow -f deploy/docker-compose.yml -f deploy/docker-compose.vps.yml --env-file .env"
STAMP=$(date +%Y%m%d-%H%M%S)
KEEP=/root/sjtu-ow-backups
mkdir -p "$KEEP"
chmod 700 "$KEEP"

say "0. keep: .env, a last full backup copied out of the volume"
cp -p .env "$KEEP/env-before-golive-$STAMP"
$C exec -T web python manage.py backup | tail -3
LAST=$($C exec -T web sh -c 'ls -t /app/backups/sjtu-ow-*.tar.gz | head -1' | tr -d '\r')
$C cp "web:$LAST" "$KEEP/demo-final-$STAMP.tar.gz"
ls -la "$KEEP/demo-final-$STAMP.tar.gz"

say "1. export the image library"
$C exec -T web python manage.py shell < /root/export_images.py 2>&1 | grep -v "objects imported"

say "2. stop web and worker; old database aside; drop thumbnails, font files, static pages"
$C stop web worker
$C run --rm --no-deps web sh -c '
  set -e
  cd /app/data
  mv db.sqlite3 demo-final.sqlite3
  for ext in wal shm; do
    if [ -e db.sqlite3-$ext ]; then mv db.sqlite3-$ext demo-final.sqlite3-$ext; fi
  done
  rm -rf /app/media/images /app/media/fonts
  find /app/prerendered -mindepth 1 -delete
  ls -la /app/data; du -sh /app/media/*'

say "3. a fresh database"
$C run --rm --no-deps web python manage.py migrate --noinput | tail -1
$C run --rm --no-deps web python manage.py createcachetable
$C run --rm --no-deps web python manage.py init_site --verbosity 0 | tail -4

say "4. the image library back"
$C run --rm --no-deps -T web python manage.py shell < /root/import_images.py 2>&1 | grep -v "objects imported"

say "5. production: no test banner, containers recreated, every page generated"
sed -i '/^TEST_ENVIRONMENT=/d' .env
$C up -d --force-recreate
for i in $(seq 1 60); do
  if $C exec -T web python /app/deploy/healthcheck.py >/dev/null 2>&1; then break; fi
  sleep 2
done
$C exec -T web python manage.py prerender | tail -1
say "done"
