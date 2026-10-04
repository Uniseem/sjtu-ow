#!/bin/sh
# Round 182 drill, part 3: turn the restored demo into an empty production
# site, the steps written down for the real switch on the demo server.
set -eu
T0=$(date +%s)
say() { echo "[$(( $(date +%s) - T0 ))s] $*"; }
cd /srv/sjtu-ow-drill/app
C="docker compose -p sjtu-ow-drill -f deploy/docker-compose.yml -f deploy/docker-compose.drill.yml --env-file .env"
KEEP=/srv/sjtu-ow-drill/kept

say "1. a last backup of the demo, copied out of the volume (backup prunes after 14 days)"
$C exec -T web python manage.py backup | tail -2
mkdir -p "$KEEP"
LAST=$($C exec -T web sh -c 'ls -t /app/backups/sjtu-ow-*.tar.gz | head -1' | tr -d '\r')
$C cp "web:$LAST" "$KEEP/demo-final.tar.gz"
ls -la "$KEEP"

say "2. stop web and worker, empty the database, uploads and static pages"
$C stop web worker
$C run --rm --no-deps web sh -c '
  rm -f /app/data/db.sqlite3 /app/data/db.sqlite3-wal /app/data/db.sqlite3-shm
  find /app/media -mindepth 1 -delete
  find /app/prerendered -mindepth 1 -delete
  ls -A /app/data /app/media /app/prerendered'

say "3. a fresh database"
$C run --rm --no-deps web python manage.py migrate --noinput | tail -1
$C run --rm --no-deps web python manage.py createcachetable
$C run --rm --no-deps web python manage.py init_site --verbosity 0 | tail -3

say "4. no more test banner"
sed -i '/^TEST_ENVIRONMENT=/d' .env
$C up -d --force-recreate
for i in $(seq 1 60); do
  if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:22890/healthz | grep -q 200; then break; fi
  sleep 2
done
$C exec -T web python manage.py prerender | tail -1

say "5. check"
for path in / /news/ /teams/ /accounts/signup/ /robots.txt /healthz; do
  curl -s -o /dev/null -w "$path %{http_code}\n" "http://127.0.0.1:22890$path"
done
echo "robots: $(curl -s http://127.0.0.1:22890/robots.txt | tr '\n' ' ' | cut -c1-80)"
echo "banner on home: $(curl -s http://127.0.0.1:22890/ | grep -c '测试环境' || true)"
$C exec -T web python manage.py shell -c "
from accounts.models import User
from teams.models import Team
from content.models import ArticlePage
from wagtail.images.models import Image
print('users', User.objects.count(), 'teams', Team.objects.count(), 'articles', ArticlePage.objects.count(), 'images', Image.objects.count())
"
say "done"
