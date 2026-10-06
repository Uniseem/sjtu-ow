#!/bin/bash
# 217 复核，14 部署与 CI：复现脚本（只读，不改仓库里的任何东西）。
#
#   bash scripts/remote-check.sh run bash handoff/rounds/217-second-review/findings/14-repro.sh
#
# 在测试机上构建一个临时镜像，用临时数据卷跑几项检查，结束时全部删掉。
set -u
cd "$(dirname "$0")/../../../.."
TAG="review14-$(date +%s)"
IMAGE="sjtu-ow:$TAG"
TMP=$(mktemp -d)
ENV=(
  -e DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod
  -e DJANGO_SECRET_KEY=ci-not-for-production-use-a-long-random-string-at-least-fifty-chars
  -e FIELD_ENCRYPTION_KEY=ci-not-for-production
  -e DJANGO_ALLOWED_HOSTS=localhost
  -e DJANGO_CSRF_TRUSTED_ORIGINS=https://localhost
  -e SITE_URL=https://localhost
  -e DJANGO_SECURE_SSL_REDIRECT=false
)
VOLS="-v $TAG-data:/app/data -v $TAG-media:/app/media -v $TAG-static:/app/staticfiles -v $TAG-prerendered:/app/prerendered -v $TAG-backups:/app/backups"
cleanup() {
  docker rm -f "$TAG-web" >/dev/null 2>&1
  for v in data media static prerendered backups; do docker volume rm -f "$TAG-$v" >/dev/null 2>&1; done
  docker rmi -f "$IMAGE" >/dev/null 2>&1
  rm -rf "$TMP"
}
trap cleanup EXIT
py() { docker run --rm "$@"; }

echo "== A. docker build -q 的输出（check.sh 把它当镜像编号比较）"
docker build -q -t "$IMAGE" . >"$TMP/q.log" 2>&1
echo "退出码 $?，输出 $(wc -l <"$TMP/q.log") 行："
sed 's/^/   | /' "$TMP/q.log"

echo "== B. docker build --check（BuildKit 的构建检查）"
docker build --check . 2>&1 | tail -n 15 | sed 's/^/   | /'

echo "== C. 镜像里留下的环境变量"
py --entrypoint env "$IMAGE" | grep -E 'SECRET|ENCRYPTION|ALLOWED|CSRF|SITE_URL|SSL' | sed 's/^/   /'

echo "== D. .env 里一个密钥都没写时，生产配置拿到的值（prod.py 写的是 required=True）"
py "$IMAGE" python -c "
import django; django.setup()
from django.conf import settings as s
print('   SECRET_KEY =', repr(s.SECRET_KEY))
print('   FIELD_ENCRYPTION_KEY =', repr(s.FIELD_ENCRYPTION_KEY))
print('   ALLOWED_HOSTS =', s.ALLOWED_HOSTS, ' SITE_URL =', s.SITE_URL)
print('   SECURE_SSL_REDIRECT =', s.SECURE_SSL_REDIRECT)
"
echo "   同样没有 .env 时 manage.py check（不加 --deploy）："
py "$IMAGE" python manage.py check 2>&1 | tail -n 2 | sed 's/^/   | /'

echo "== E. 以 app 运行时哪些目录写得进"
py --entrypoint sh "$IMAGE" -c 'id; echo "HOME=$HOME"; for d in /app /app/static /app/locale /app/deploy /tmp /home/app; do if touch "$d/.w" 2>/dev/null; then echo "   $d 可写"; else echo "   $d 不可写"; fi; done'

echo "== F. 镜像里的 __pycache__ 和其它不该进镜像的东西（.dockerignore 只排除根目录那一层）"
py --entrypoint sh "$IMAGE" -c 'echo "   /app 下（不含 .venv）的 __pycache__ 目录数：$(find /app -name __pycache__ -not -path "/app/.venv/*" | wc -l)"; find /app -name __pycache__ -not -path "/app/.venv/*" | head -n 5 | sed "s/^/     /"; echo "   /app 顶层："; ls -A /app | tr "\n" " "; echo'
echo "   测试机检出目录里（构建上下文）不在根目录的 __pycache__："
find . -path ./.venv -prune -o -name __pycache__ -print | grep -v '^\./__pycache__$' | head -n 3 | sed 's/^/     /'

echo "== G. pillow-heif 打包的库（Wagtail 依赖 Willow[heif]）"
py --entrypoint sh "$IMAGE" -c '
site=/app/.venv/lib/python3.13/site-packages
ls "$site"/pillow_heif.libs/ 2>/dev/null | sed "s/^/   /"
grep -iE "^(License|Classifier: License)" "$site"/pillow_heif-*.dist-info/METADATA | sed "s/^/   /"
ls "$site"/pillow_heif-*.dist-info/ "$site"/pillow_heif-*.dist-info/licenses 2>/dev/null | sed "s/^/   /"
python -c "import pillow_heif; print(\"   libheif_info:\", pillow_heif.libheif_info())"
'

echo "== H. 基础镜像的年龄和没打的系统安全更新"
echo "   python:3.13-slim-bookworm 本机这份的创建时间：$(docker image inspect python:3.13-slim-bookworm -f '{{.Created}}' 2>/dev/null)"
py --user root --entrypoint sh "$IMAGE" -c 'apt-get update -qq >/dev/null 2>&1; n=$(apt list --upgradable 2>/dev/null | grep -c "\-security"); echo "   可升级且来自 security 源的包：$n"; apt list --upgradable 2>/dev/null | grep security | head -n 15 | sed "s/^/     /"'
py --entrypoint python "$IMAGE" -c "import sys, ssl; print('   Python', sys.version.split()[0], '|', ssl.OPENSSL_VERSION)"

echo "== I. 慢速上传会被 gunicorn 的 30 秒超时杀掉"
py "${ENV[@]}" $VOLS "$IMAGE" python manage.py migrate --noinput >"$TMP/migrate.log" 2>&1 || { echo "   migrate 失败"; tail "$TMP/migrate.log"; }
docker run -d --name "$TAG-web" "${ENV[@]}" $VOLS "$IMAGE" >/dev/null
ip=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$TAG-web")
for _ in $(seq 1 60); do
  code=$(curl -s -o /dev/null -w '%{http_code}' -H 'Host: localhost' "http://$ip:8000/healthz" || true)
  [ "$code" = 000 ] || break
  sleep 1
done
echo "   web 起来了（/healthz → $code），地址 $ip"
head -c 3000000 /dev/urandom >"$TMP/blob"
tok=abcdefghijklmnopqrstuvwxyzABCDEF
up() { # rate
  curl -s -o /dev/null -w '%{http_code} 用时 %{time_total}s 已发 %{size_upload} 字节' --max-time 120 \
    ${1:+--limit-rate $1} -H 'Host: localhost' -b "csrftoken=$tok" -H "X-CSRFToken: $tok" \
    -F "avatar=@$TMP/blob" "http://$ip:8000/accounts/login/"
}
echo "   不限速上传 3 MB：$(up)"
echo "   限速 50 KB/s 上传 3 MB（约 60 秒）：$(up 50k)"
echo "   gunicorn 日志里的超时："
docker logs "$TAG-web" 2>&1 | grep -E 'WORKER TIMEOUT|Worker .* was sent|Booting worker' | tail -n 5 | sed 's/^/     /'
docker exec "$TAG-web" sh -c 'cat /proc/1/cmdline | tr "\0" " "' | sed 's/^/   gunicorn 命令行：/'; echo

echo "== J. 依赖的已知漏洞（pip-audit，PyPI 漏洞库）"
export PATH="/srv/sjtu-ow-check/uv/bin:$PATH"
uv export --frozen --no-dev --no-hashes --no-emit-project -o "$TMP/req.txt" >/dev/null 2>&1
uvx --quiet pip-audit -r "$TMP/req.txt" --no-deps --disable-pip --progress-spinner off 2>&1 | tail -n 30 | sed 's/^/   | /'

echo "== K. 最近几次整组检查里「Docker 镜像」一步的输出"
for f in $(ls -t /srv/sjtu-ow-check/runs/*.log 2>/dev/null | head -n 12); do
  grep -A2 '== Docker 镜像' "$f" | grep -v '^--$' | sed "s|^|   $(basename "$f"): |"
done | head -n 15
echo "== 完"
