#!/bin/sh
# Round 182 restore drill, part 2: the demo site's real backup onto the fresh
# site from part 1, following README 「备份与恢复」. The drill site has its own
# keys, so --skip-key-check: the demo's keys never leave the demo server, and
# with no SMTP password or bucket secret stored there is nothing encrypted to
# lose. A real recovery uses the keys from the password manager instead.
set -eu
T0=$(date +%s)
say() { echo "[$(( $(date +%s) - T0 ))s] $*"; }
cd /srv/sjtu-ow-drill/app
C="docker compose -p sjtu-ow-drill -f deploy/docker-compose.yml -f deploy/docker-compose.drill.yml --env-file .env"
ARCHIVE=sjtu-ow-20261004-030004.tar.gz

say "copy the archive into the backups volume"
$C cp "../$ARCHIVE" "web:/app/backups/$ARCHIVE"
say "dry run"
$C exec -T web python manage.py restore "/app/backups/$ARCHIVE" --skip-key-check | tail -8
say "stop web and worker"
$C stop web worker
say "restore"
$C run --rm --no-deps web python manage.py restore "/app/backups/$ARCHIVE" --yes --skip-key-check | tail -8
say "migrate (the backup may be older than the code)"
$C run --rm --no-deps web python manage.py migrate --noinput | tail -3
say "start"
$C up -d
for i in $(seq 1 60); do
  if $C exec -T web python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)" 2>/dev/null; then break; fi
  sleep 2
done
say "sync the site address to this machine, then regenerate every page"
$C exec -T web python manage.py init_site --verbosity 0
$C exec -T web python manage.py prerender | tail -2
say "check"
for path in / /news/ /teams/ /tournaments/ /scrims/ /members/ /accounts/login/ /healthz; do
  curl -s -o /dev/null -w "$path %{http_code} %{size_download}B\n" "http://127.0.0.1:22890$path"
done
$C exec -T web python manage.py shell -c "
from accounts.models import User
from teams.models import Team
from content.models import ArticlePage
from comments.models import Comment
from wagtail.images.models import Image
print('users', User.objects.count(), 'teams', Team.objects.count(), 'articles', ArticlePage.objects.count(), 'comments', Comment.objects.count(), 'images', Image.objects.count())
"
say "done"
