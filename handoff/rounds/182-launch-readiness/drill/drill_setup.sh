#!/bin/sh
# Round 182 restore drill, part 1: a fresh site on the test machine, the way
# README 「生产 / 测试环境启动」 describes it. Port 22890 on localhost only.
set -eu
T0=$(date +%s)
say() { echo "[$(( $(date +%s) - T0 ))s] $*"; }
cd /srv/sjtu-ow-drill
rm -rf app
say "clone"
git clone -q --depth 1 https://github.com/Uniseem/sjtu-ow.git app
cd app
say "commit $(git log --oneline -1)"
key() { python3 -c 'import secrets; print(secrets.token_urlsafe(50))'; }
umask 077
cat > .env <<EOF
DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod
DJANGO_SECRET_KEY=$(key)
FIELD_ENCRYPTION_KEY=$(key)
BACKUP_ENCRYPTION_KEY=$(key)
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:22890
SITE_URL=http://localhost:22890
DJANGO_SECURE_SSL_REDIRECT=false
TEST_ENVIRONMENT=1
GUNICORN_WORKERS=3
EOF
umask 022
cat > deploy/docker-compose.drill.yml <<'EOF'
services:
  proxy:
    ports: !override
      - "127.0.0.1:22890:80"
    environment:
      CADDY_SITE_ADDRESS: ":80"
EOF
C="docker compose -p sjtu-ow-drill -f deploy/docker-compose.yml -f deploy/docker-compose.drill.yml --env-file .env"
say "build"
$C build -q
say "up"
$C up -d
say "wait for web"
for i in $(seq 1 60); do
  if $C exec -T web python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)" 2>/dev/null; then break; fi
  sleep 2
done
$C exec -T web python manage.py init_site --verbosity 0 || true
say "fresh site up"
curl -s -o /dev/null -w "home %{http_code}\n" http://127.0.0.1:22890/
say "done"
