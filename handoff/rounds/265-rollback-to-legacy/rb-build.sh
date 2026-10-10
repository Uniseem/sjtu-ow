#!/bin/sh
# 265 回滚第一步：照旧站的 Compose 构建 Django 镜像（新栈照常跑，不停机）。
cd /srv/sjtu-ow || exit 1
C="docker compose -p sjtu-ow -f deploy/docker-compose.yml -f deploy/docker-compose.vps.yml --env-file .env"
date
$C config >/dev/null || { echo "Compose 配置读不出来"; exit 1; }
$C build web worker
code=$?
date
docker images --format "{{.Repository}}:{{.Tag}} {{.ID}} {{.CreatedAt}} {{.Size}}" | grep sjtu-ow
exit $code
