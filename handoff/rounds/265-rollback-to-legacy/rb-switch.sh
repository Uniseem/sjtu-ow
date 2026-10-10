#!/bin/sh
# 265 回滚第二步：停新栈（卷都留着）、起旧站、全量预渲染。
set -u
cd /srv/sjtu-ow || exit 1
NEW="docker compose -p sjtu-ow -f deploy/docker-compose.new.yml"
OLD="docker compose -p sjtu-ow -f deploy/docker-compose.yml -f deploy/docker-compose.vps.yml --env-file .env"
echo "== $(date) 停新栈"
$NEW stop || exit 1
echo "== 新栈最后的库留一份"
mkdir -p /root/rollback-check/newdata-final
docker cp sjtu-ow-server-1:/srv/sjtuow/data/. /root/rollback-check/newdata-final/ || exit 1
ls -la /root/rollback-check/newdata-final
$NEW down || exit 1
echo "== $(date) 起旧站"
$OLD up -d --no-build || exit 1
echo "== 等 web 健康"
for i in $(seq 1 60); do
  s=$(docker inspect -f '{{.State.Health.Status}}' sjtu-ow-web-1 2>/dev/null)
  echo "  $i $s"
  [ "$s" = "healthy" ] && break
  sleep 5
done
$OLD ps
echo "== $(date) 全量预渲染"
$OLD exec -T web python manage.py prerender < /dev/null
echo "== $(date) 完"
