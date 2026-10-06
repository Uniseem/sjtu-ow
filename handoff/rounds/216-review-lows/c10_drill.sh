#!/bin/bash
# Round 216, C10: the image runs as "app" (uid 10001), not root.
#
# Tests cannot see which user a container runs as or who owns a volume, so
# this builds the image and runs it the way docker-compose.yml does, twice:
#
#   1. fresh volumes (a new install): migrate, collectstatic and the worker
#      must work with no extra step;
#   2. volumes that root made (every install before 216): the new image must
#      fail to write, and the hand-over in README「升级到 216」 must fix it.
#
# Run on the test machine (Docker, network for the base image):
#   bash scripts/remote-check.sh run bash handoff/rounds/216-review-lows/c10_drill.sh
set -u
cd "$(dirname "$0")/../../.."
TAG="c10-$(date +%s)"
IMAGE="sjtu-ow:$TAG"
ENV=(
  -e DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod
  -e DJANGO_SECRET_KEY=ci-not-for-production-use-a-long-random-string-at-least-fifty-chars
  -e FIELD_ENCRYPTION_KEY=ci-not-for-production
  -e DJANGO_ALLOWED_HOSTS=localhost
  -e DJANGO_CSRF_TRUSTED_ORIGINS=https://localhost
  -e SITE_URL=https://localhost
  -e DJANGO_SECURE_SSL_REDIRECT=false
)
failed=0
check() { # name, then the command
  local name="$1"; shift
  if "$@" >/tmp/$TAG.out 2>&1; then
    echo "ok   $name"
  else
    echo "FAIL $name"; tail -5 /tmp/$TAG.out | sed 's/^/     /'; failed=1
  fi
}
expect_fail() {
  local name="$1"; shift
  if "$@" >/tmp/$TAG.out 2>&1; then
    echo "FAIL $name（本该失败却成功了）"; failed=1
  else
    echo "ok   $name（失败了，符合预期：$(grep -o -m1 -E 'readonly database|Permission denied|unable to open' /tmp/$TAG.out)）"
  fi
}
volumes() { # prefix -> the -v flags of the web service
  echo "-v $1-data:/app/data -v $1-media:/app/media -v $1-static:/app/staticfiles -v $1-prerendered:/app/prerendered -v $1-backups:/app/backups"
}
cleanup() {
  docker rm -f "$TAG-web" "$TAG-worker" >/dev/null 2>&1
  for p in "$TAG-new" "$TAG-old"; do
    for v in data media static prerendered backups; do docker volume rm -f "$p-$v" >/dev/null 2>&1; done
  done
  docker rmi -f "$IMAGE" >/dev/null 2>&1
  rm -f /tmp/$TAG.out
}
trap cleanup EXIT

echo "== 构建镜像"
docker build -q -t "$IMAGE" . >/dev/null || { echo "构建失败"; exit 1; }
echo "镜像里的用户：$(docker run --rm --entrypoint id "$IMAGE")"

echo "== 1. 全新数据卷"
NEW=$(volumes "$TAG-new")
check "migrate" docker run --rm "${ENV[@]}" $NEW "$IMAGE" python manage.py migrate --noinput
check "createcachetable + collectstatic" docker run --rm "${ENV[@]}" $NEW "$IMAGE" \
  sh -c "python manage.py createcachetable && python manage.py collectstatic --noinput"
check "backup 写进 backups 卷" docker run --rm "${ENV[@]}" $NEW "$IMAGE" python manage.py backup
check "数据库文件归 app" docker run --rm $NEW --entrypoint stat "$IMAGE" -c '%U' /app/data/db.sqlite3
docker run --rm $NEW --entrypoint stat "$IMAGE" -c '     db.sqlite3 属于 %U（%u）' /app/data/db.sqlite3
# Like the Compose file: the worker mounts static read-only.
WORKER_VOLUMES="-v $TAG-new-data:/app/data -v $TAG-new-media:/app/media -v $TAG-new-static:/app/staticfiles:ro -v $TAG-new-prerendered:/app/prerendered"
docker run -d --name "$TAG-worker" "${ENV[@]}" $WORKER_VOLUMES "$IMAGE" /app/deploy/entrypoint-worker.sh >/dev/null
docker run -d --name "$TAG-web" "${ENV[@]}" $NEW "$IMAGE" >/dev/null
sleep 15
# Who each process runs as, from inside: /proc/1 is the container's first
# process (gunicorn's master, the worker), its uid the fourth field of Uid.
uid_of() { docker exec "$1" sh -c "grep '^Uid:' /proc/1/status | cut -f2"; }
echo "     web 的 1 号进程：$(docker exec "$TAG-web" cat /proc/1/cmdline | tr '\0' ' ')，uid $(uid_of "$TAG-web")"
echo "     worker 的 1 号进程：$(docker exec "$TAG-worker" cat /proc/1/cmdline | tr '\0' ' ')，uid $(uid_of "$TAG-worker")"
check "web 的进程是 10001，不是 root" test "$(uid_of "$TAG-web")" = 10001
check "worker 还在跑、进程是 10001" sh -c "test \"\$(docker inspect -f '{{.State.Running}}' $TAG-worker)\" = true && test \"\$(docker exec $TAG-worker sh -c \"grep '^Uid:' /proc/1/status | cut -f2\")\" = 10001"
check "健康检查脚本（容器里，含 worker 心跳）" docker exec "$TAG-web" python /app/deploy/healthcheck.py

echo "== 2. 216 以前的数据卷（属于 root）"
OLD=$(volumes "$TAG-old")
# What older images left: the volumes made and written by root, none of them
# empty. (An empty volume takes the image's owner again each time it is
# mounted, which is why a first try of this drill could write into them;
# production's volumes all hold files.)
docker run --rm --user root "${ENV[@]}" $OLD "$IMAGE" sh -c \
  "python manage.py migrate --noinput >/dev/null && for d in media staticfiles prerendered backups; do touch /app/\$d/.from-before-216; done && chown -R root:root /app/data /app/media /app/staticfiles /app/prerendered /app/backups"
docker run --rm $OLD --entrypoint stat "$IMAGE" -c '     交接前 db.sqlite3 属于 %U' /app/data/db.sqlite3
expect_fail "不交接直接 migrate" docker run --rm "${ENV[@]}" $OLD "$IMAGE" python manage.py migrate --noinput
# collectstatic has nothing to write when the same version is already on the
# volume; an upgrade brings new files. Write into each volume directly.
for dir in staticfiles media prerendered backups; do
  expect_fail "不交接直接往 $dir 写文件" docker run --rm $OLD --entrypoint touch "$IMAGE" /app/$dir/.probe
done
check "README 的交接：以 root chown 一次" docker run --rm --user root $OLD --entrypoint chown "$IMAGE" -R 10001:10001 \
  /app/data /app/media /app/staticfiles /app/prerendered /app/backups
check "交接后 migrate" docker run --rm "${ENV[@]}" $OLD "$IMAGE" python manage.py migrate --noinput
check "交接后 collectstatic" docker run --rm "${ENV[@]}" $OLD "$IMAGE" python manage.py collectstatic --noinput
check "交接后 backup" docker run --rm "${ENV[@]}" $OLD "$IMAGE" python manage.py backup

echo
if [ "$failed" = 0 ]; then echo "C10 演练通过"; else echo "C10 演练有失败"; fi
exit "$failed"
