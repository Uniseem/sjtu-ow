#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
LOG_DIR=/srv/sjtu-ow-check/ops-301-images
mkdir -p "$LOG_DIR"
SOURCE=$(git rev-parse HEAD)
if [ "${1:-}" != "--web-only" ]; then
  docker build --label "sjtuow.source=$SOURCE" -f deploy/Dockerfile.server -t sjtu-ow-next-server:301 . > "$LOG_DIR/server-build.log" 2>&1
  printf 'SERVER-IMAGE-BUILD-OK source=%s\n' "$SOURCE"
fi
docker build --label "sjtuow.source=$SOURCE" -f deploy/Dockerfile.web -t sjtu-ow-next-web:301 . > "$LOG_DIR/web-build.log" 2>&1
printf 'WEB-IMAGE-BUILD-OK source=%s\n' "$SOURCE"
volume=sjtu-ow-301-assets-probe
docker volume create --label sjtuow.round=301 "$volume" > /dev/null
trap 'docker volume rm "$volume" > /dev/null' EXIT
docker run --rm --entrypoint sh -v "$volume:/var/assets" sjtu-ow-next-web:301 -c 'mkdir -p /var/assets/img /var/assets/css /var/assets/admin && cp -a /app/web/apps/site/dist/client/. /var/assets/ && cp -a /app/web/apps/admin/dist/. /var/assets/admin/ && cp -a /app/static/img/. /var/assets/img/ && cp /app/static/css/error.css /app/static/css/reader.css /var/assets/css/ && test -s /var/assets/admin/index.html && test -s /var/assets/css/reader.css && printf "ASSETS-NONROOT-VOLUME-OK\n"' > "$LOG_DIR/assets-probe.log" 2>&1
cat "$LOG_DIR/assets-probe.log"
docker save sjtu-ow-next-server:301 sjtu-ow-next-web:301 | gzip -1 > "$LOG_DIR/images.tar.gz"
sha256sum "$LOG_DIR/images.tar.gz" > "$LOG_DIR/images.sha256"
printf 'IMAGES-READY %s\n' "$LOG_DIR"
