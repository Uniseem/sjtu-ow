#!/bin/sh
# Everything a round has to pass before it is committed (AGENTS.md「常用命令」),
# in CI's order (.github/workflows/ci.yml). Linux, from the repository root:
#
#   sh scripts/check.sh
#
# CHECK_SHARDS=N (or auto, one per CPU) splits pytest over worktrees
# (scripts/pytest-shards.sh). CHECK_DOCKER=1 also builds the image, as CI's
# last step does, in the background from the start so it costs no extra time.
# scripts/remote-check.sh runs this on the test machine against your working
# tree with both, so nothing has to run on the developer's own computer.
set -eu
export DJANGO_SETTINGS_MODULE=sjtu_ow.settings.dev

step() { printf '\n== %s (%s)\n' "$1" "$(date +%H:%M:%S)"; }

docker_log=""
if [ "${CHECK_DOCKER:-0}" = 1 ]; then
  if command -v docker >/dev/null; then
    docker_log=$(mktemp)
    docker_old=$(docker image inspect -f '{{.Id}}' sjtu-ow:check 2>/dev/null || true)
    docker build -q -t sjtu-ow:check . >"$docker_log" 2>&1 &
    docker_pid=$!
  else
    echo "这台机器没有 Docker，不构建镜像"
  fi
fi

step "依赖"
uv sync --frozen --quiet

step "ruff"
uv run ruff check .
uv run ruff format --check .

step "Tailwind"
uv run python manage.py tailwind download_cli >/dev/null
uv run python manage.py tailwind build --force

step "pytest"
if [ "${CHECK_SHARDS:-1}" != 1 ]; then
  bash scripts/pytest-shards.sh "$CHECK_SHARDS"
else
  uv run pytest -q
fi

step "迁移"
uv run python manage.py makemigrations --check --dry-run

step "生产配置"
DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod \
  DJANGO_SECRET_KEY=ci-not-for-production-use-a-long-random-string-at-least-fifty-chars \
  FIELD_ENCRYPTION_KEY=ci-not-for-production DJANGO_ALLOWED_HOSTS=example.com \
  DJANGO_CSRF_TRUSTED_ORIGINS=https://example.com SITE_URL=https://example.com \
  DJANGO_SECURE_SSL_REDIRECT=true \
  uv run python manage.py check --deploy

step "错误页和模板一致"
uv run python manage.py render_error_pages >/dev/null
git diff --exit-code -- deploy/error_pages

if [ -n "$docker_log" ]; then
  step "Docker 镜像"
  if ! wait "$docker_pid"; then
    cat "$docker_log"
    exit 1
  fi
  echo "构建成功：$(cut -c 8-19 "$docker_log")"
  # Only the image this script built last time, nothing else on the machine.
  if [ -n "$docker_old" ] && [ "$docker_old" != "$(cat "$docker_log")" ]; then
    docker rmi -f "$docker_old" >/dev/null 2>&1 || true
  fi
  rm -f "$docker_log"
fi

step "全部通过"
