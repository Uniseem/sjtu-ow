#!/usr/bin/env bash
# 起一个真 Caddy（deploy/Caddyfile.new）和两个桩服务（假装 Go 和 SSR），逐条验
# 路由表、响应头、请求体上限和维护页（frontend-migration B1、B2、B6）。
#
# 在测试机上跑（要 Docker 和 python3）：
#   bash scripts/remote-check.sh run bash e2e/caddy/smoke.sh
# 任何一条不对，退出码 1。容器、桩进程、临时目录在退出时都收掉（AGENTS「跑完要收进程」）。
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
IMAGE=${CADDY_IMAGE:-caddy:2.10-alpine}
NAME=ow-caddy-smoke-$$
TMP=$(mktemp -d)
PIDS=()
cleanup() {
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  for pid in "${PIDS[@]}"; do kill -TERM "$pid" 2>/dev/null || true; done
  rm -rf "$TMP"
}
trap cleanup EXIT

PORT=$((18000 + RANDOM % 1000))
API=$((19000 + RANDOM % 500))
SSR=$((19500 + RANDOM % 500))

# ---- 卷里的东西 ----
mkdir -p "$TMP/assets/assets" "$TMP/assets/img" "$TMP/assets/css" "$TMP/assets/admin/assets" "$TMP/media/fonts/objects" \
  "$TMP/media/r/5" "$TMP/media/images" "$TMP/media/original_images" "$TMP/media/fonts/css" "$TMP/error_pages"
echo "ENTRY" >"$TMP/assets/assets/entry-abc.js"
echo "THEME" >"$TMP/assets/theme.js"
echo "ADMIN-SHELL" >"$TMP/assets/admin/index.html"
echo "ADMIN-CHUNK" >"$TMP/assets/admin/assets/editor-abc.js"
echo "READER" >"$TMP/assets/css/reader.css"
echo "<svg/>" >"$TMP/assets/img/a.svg"
echo "ICO" >"$TMP/assets/img/favicon.ico"
cp "$ROOT/static/css/error.css" "$TMP/assets/css/error.css"
echo "WEBP-5" >"$TMP/media/r/5/fill-88x88.webp"
echo "OLD-JPG" >"$TMP/media/images/old.jpg"
echo "SECRET" >"$TMP/media/original_images/secret.jpg"
echo "FONT-CSS" >"$TMP/media/fonts/css/fonts.0123456789ab.css"
echo "FONT-PREVIEW" >"$TMP/media/fonts/css/preview.0123456789ab.css"
echo "CURRENT-FONT-CSS" >"$TMP/media/fonts/css/fonts.0123456789abcdef0123.css"
echo "CURRENT-PREVIEW" >"$TMP/media/fonts/css/preview.0123456789abcdef0123.css"
FONT_HASH=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
echo "CURRENT-WOFF2" >"$TMP/media/fonts/objects/$FONT_HASH.woff2"
echo "RAW-TTF" >"$TMP/media/fonts/raw.ttf"
cp "$ROOT/deploy/error_pages/maintenance.html" "$TMP/error_pages/maintenance.html"

# ---- 桩：回答自己是谁、看到的方法、路径、X-Real-IP；SSR 桩故意带一条别的 CSP ----
cat >"$TMP/stub.py" <<'PY'
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
who, port = sys.argv[1], int(sys.argv[2])
class H(BaseHTTPRequestHandler):
    def answer(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        body = json.dumps({"who": who, "method": self.command, "path": self.path,
                           "real_ip": self.headers.get("X-Real-IP")}).encode()
        code = int(self.path.rsplit('/', 1)[-1]) if self.path.startswith('/upstream-status/') else 200
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        if who == "ssr":
            self.send_header("Content-Security-Policy", "default-src *")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    do_GET = do_POST = do_HEAD = do_PATCH = do_DELETE = answer
    def log_message(self, *a): pass
class Quiet(HTTPServer):
    # 413 时 Caddy 会掐断转发中的请求，桩这边写回答会断管，不算问题
    def handle_error(self, *a): pass
Quiet(("127.0.0.1", port), H).serve_forever()
PY
python3 "$TMP/stub.py" api "$API" & PIDS+=($!)
python3 "$TMP/stub.py" ssr "$SSR" & PIDS+=($!)
SSR_PID=$!

docker run --rm -v "$ROOT/deploy/Caddyfile.new:/etc/caddy/Caddyfile:ro" "$IMAGE" \
  caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null
echo "caddy validate 通过"

docker run -d --name "$NAME" --network host \
  -e CADDY_SITE_ADDRESS=":$PORT" -e API_UPSTREAM="127.0.0.1:$API" -e SSR_UPSTREAM="127.0.0.1:$SSR" \
  -e ASSETS_ROOT=/var/assets -e MEDIA_PARENT=/var -e ERROR_PAGES_ROOT=/srv/error_pages \
  -v "$ROOT/deploy/Caddyfile.new:/etc/caddy/Caddyfile:ro" \
  -v "$TMP/assets:/var/assets:ro" -v "$TMP/media:/var/media:ro" -v "$TMP/error_pages:/srv/error_pages:ro" \
  "$IMAGE" >/dev/null
for _ in $(seq 1 50); do
  curl -s -o /dev/null "http://127.0.0.1:$PORT/assets/entry-abc.js" && break
  sleep 0.2
done

BASE="http://127.0.0.1:$PORT"
FAILS=0
# check 名字 期望 实际
check() {
  if [ "$2" = "$3" ]; then
    echo "  ✓ $1"
  else
    echo "  ✗ $1：期望 [$2]，得到 [$3]"
    FAILS=$((FAILS + 1))
  fi
}
status() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
body() { curl -s "$@"; }
header() { local name=$1; shift; curl -s -o /dev/null -D - "$@" | tr -d '\r' | grep -i "^$name:" | head -1 | cut -d' ' -f2-; }
count_header() { local name=$1; shift; curl -s -o /dev/null -D - "$@" | tr -d '\r' | grep -ic "^$name:" || true; }
who() { body "$@" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["who"], d["method"], d["path"])'; }

CSP="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-src 'self' https://player.bilibili.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
ADMIN_CSP="default-src 'self'; script-src 'self'; style-src 'self'; style-src-attr 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-src 'self' https://player.bilibili.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
SERVER_CSP=$(grep -o "\"default-src[^\"]*\"" "$ROOT/web/apps/site/server.ts" | head -1 | tr -d '"')

echo "页面和接口的去向"
check "首页去 SSR" "ssr GET /" "$(who "$BASE/")"
check "访客 IP 是反代带来的那个（{client_ip}）" "203.0.113.9" \
  "$(body -H 'X-Forwarded-For: 203.0.113.9' "$BASE/" | python3 -c 'import json,sys; print(json.load(sys.stdin)["real_ip"])')"
check "接口去 Go" "api GET /api/session" "$(who "$BASE/api/session")"
check "接口的访客 IP" "203.0.113.9" \
  "$(body -H 'X-Forwarded-For: 203.0.113.9' "$BASE/api/session" | python3 -c 'import json,sys; print(json.load(sys.stdin)["real_ip"])')"
check "接口的写请求去 Go" "api POST /api/teams/1/applications" "$(who -X POST -H 'Content-Type: application/json' -d '{}' "$BASE/api/teams/1/applications")"
check "页面地址的写请求 405" "405" "$(status -X POST "$BASE/teams/")"
for method in PATCH DELETE PUT; do
  check "页面 $method 405" "405" "$(status -X "$method" "$BASE/teams/")"
done
check "旧预渲染设置真实301" "301 /admin/settings/" "$(status "$BASE/admin/settings/prerender/") $(header Location "$BASE/admin/settings/prerender/")"
check "旧前台信纸路径去Go且不跳转" "api GET /letters/12345678-1234-1234-1234-123456789abc/1/" "$(who "$BASE/letters/12345678-1234-1234-1234-123456789abc/1/")"
check "旧后台信纸路径去Go且不进SPA" "api GET /admin/letters/12345678-1234-1234-1234-123456789abc/1/" "$(who "$BASE/admin/letters/12345678-1234-1234-1234-123456789abc/1/")"
check "旧报名CSV保留URI和query去Go" "api GET /admin/registrations/export.csv?tournament=3&status=pending" "$(who "$BASE/admin/registrations/export.csv?tournament=3&status=pending")"
check "旧活动CSV保留URI和query去Go" "api GET /admin/activity/?start=2026-01-01&end=2026-12-31&format=csv" "$(who "$BASE/admin/activity/?start=2026-01-01&end=2026-12-31&format=csv")"
check "普通活动页仍独立SPA" "ADMIN-SHELL" "$(body "$BASE/admin/activity/?start=2026-01-01")"
check "一键退订 POST 去 Go" "api POST /unsubscribe/tok/" "$(who -X POST "$BASE/unsubscribe/tok/")"
check "退订页 GET 去 SSR" "ssr GET /unsubscribe/tok/" "$(who "$BASE/unsubscribe/tok/")"
check "sitemap 去 Go" "api GET /sitemap.xml" "$(who "$BASE/sitemap.xml")"
check "robots 去 Go" "api GET /robots.txt" "$(who "$BASE/robots.txt")"
check "健康检查去 Go" "api GET /healthz" "$(who "$BASE/healthz")"
check "日历去 Go" "api GET /calendar/t.ics" "$(who "$BASE/calendar/t.ics")"

echo "文件"
check "构建产物" "ENTRY" "$(body "$BASE/assets/entry-abc.js")"
check "构建产物缓存一年" "public, max-age=31536000, immutable" "$(header Cache-Control "$BASE/assets/entry-abc.js")"
check "theme.js" "THEME" "$(body "$BASE/theme.js")"
check "theme.js 每次问" "no-cache" "$(header Cache-Control "$BASE/theme.js")"
check "固定图" "<svg/>" "$(body "$BASE/static/img/a.svg")"
check "固定图缓存一天" "public, max-age=86400" "$(header Cache-Control "$BASE/static/img/a.svg")"
check "错误页样式表" "200" "$(status "$BASE/static/css/error.css")"
check "favicon.ico 跳固定地址" "301 /static/img/favicon.ico" "$(status "$BASE/favicon.ico") $(header Location "$BASE/favicon.ico")"
check "apple-touch-icon 跳固定地址" "301 /static/img/apple-touch-icon.png" "$(status "$BASE/apple-touch-icon.png") $(header Location "$BASE/apple-touch-icon.png")"

echo "图片"
check "已有的缩略图直接给" "WEBP-5" "$(body "$BASE/media/r/5/fill-88x88.webp")"
check "缩略图缓存一年" "public, max-age=31536000, immutable" "$(header Cache-Control "$BASE/media/r/5/fill-88x88.webp")"
check "没有的缩略图交给 Go 现做" "api GET /media/r/6/fill-88x88.webp" "$(who "$BASE/media/r/6/fill-88x88.webp")"
check "编号不是数字的缩略图 404" "404" "$(status "$BASE/media/r/abc/fill-88x88.webp")"
check "旧缩略图原样给" "OLD-JPG" "$(body "$BASE/media/images/old.jpg")"
check "原图不公开" "404" "$(status "$BASE/media/original_images/secret.jpg")"
check "带哈希的字体样式表给" "FONT-CSS" "$(body "$BASE/media/fonts/css/fonts.0123456789ab.css")"
check "字体原件不给" "404" "$(status "$BASE/media/fonts/raw.ttf")"
check "实际Go字体20位哈希" "CURRENT-FONT-CSS" "$(body "$BASE/media/fonts/css/fonts.0123456789abcdef0123.css")"
check "实际Go预览20位哈希" "CURRENT-PREVIEW" "$(body "$BASE/media/fonts/css/preview.0123456789abcdef0123.css")"
check "实际Go字体对象切片" "CURRENT-WOFF2" "$(body "$BASE/media/fonts/objects/$FONT_HASH.woff2")"
check "非哈希字体对象不给" "404" "$(status "$BASE/media/fonts/objects/raw.woff2")"

check "独立后台 shell 不走 SSR" "ADMIN-SHELL" "$(body "$BASE/admin/articles/5/")"
check "后台 shell 重新验证缓存" "no-cache" "$(header Cache-Control "$BASE/admin/articles/5/")"
check "后台独立块" "ADMIN-CHUNK" "$(body "$BASE/admin/assets/editor-abc.js")"
check "后台块长期缓存" "public, max-age=31536000, immutable" "$(header Cache-Control "$BASE/admin/assets/editor-abc.js")"
check "阅读预览固定样式" "READER" "$(body "$BASE/static/css/reader.css")"
check "阅读预览固定样式重新验证" "no-cache" "$(header Cache-Control "$BASE/static/css/reader.css")"
check "排版预览哈希样式" "FONT-PREVIEW" "$(body "$BASE/media/fonts/css/preview.0123456789ab.css")"

echo "安全头"
check "页面的 CSP 是 Caddy 的（覆盖了上游带来的）" "$CSP" "$(header Content-Security-Policy "$BASE/")"
check "只有一条 CSP" "1" "$(count_header Content-Security-Policy "$BASE/")"
check "Caddy 的 CSP 和 server.ts 的逐字一致" "$CSP" "$SERVER_CSP"
check "接口也带 nosniff" "nosniff" "$(header X-Content-Type-Options "$BASE/api/session")"
check "文件也带 HSTS" "max-age=31536000; includeSubDomains; preload" "$(header Strict-Transport-Security "$BASE/assets/entry-abc.js")"
check "Referrer-Policy" "same-origin" "$(header Referrer-Policy "$BASE/")"
check "X-Frame-Options" "DENY" "$(header X-Frame-Options "$BASE/")"
check "私有信件预览同站可嵌入" "SAMEORIGIN" "$(header X-Frame-Options "$BASE/api/letters/batch/1/preview")"
check "信纸 CSP 隔离脚本" "default-src 'none'; style-src 'unsafe-inline'; img-src data:; frame-ancestors 'self'; base-uri 'none'; form-action 'none'; sandbox" "$(header Content-Security-Policy "$BASE/api/letters/batch/1/preview")"
check "Markdown 预览只允许外部阅读样式" "default-src 'none'; style-src 'self'; img-src 'self' data:; font-src 'self'; frame-src https://player.bilibili.com; frame-ancestors 'self'; base-uri 'none'; form-action 'none'; sandbox allow-same-origin" "$(header Content-Security-Policy "$BASE/api/admin/previews/token")"
check "样张同站可嵌入" "SAMEORIGIN" "$(header X-Frame-Options "$BASE/api/admin/mail-samples/signup/preview")"
check "后台仅允许编辑器内联样式属性" "$ADMIN_CSP" "$(header Content-Security-Policy "$BASE/admin/")"
check "后台仅一条CSP" "1" "$(count_header Content-Security-Policy "$BASE/admin/")"
for path in /admin/ /api/letters/batch/1/preview /api/admin/previews/token; do
  check "$path HSTS" "max-age=31536000; includeSubDomains; preload" "$(header Strict-Transport-Security "$BASE$path")"
  check "$path nosniff" "nosniff" "$(header X-Content-Type-Options "$BASE$path")"
done


echo "请求体上限"
head -c 2000000 /dev/zero | tr '\0' 'a' >"$TMP/big"
check "普通接口超过 1 MB 是 413" "413" "$(status -X POST -H 'Content-Type: application/json' --data-binary @"$TMP/big" "$BASE/api/teams/1/applications")"
check "传头像 2 MB 放行" "200" "$(status -X POST -H 'Content-Type: application/json' --data-binary @"$TMP/big" "$BASE/api/me/avatar")"
check "传队标 2 MB 放行" "200" "$(status -X POST -H 'Content-Type: application/json' --data-binary @"$TMP/big" "$BASE/api/teams/3/logo")"
head -c 17000000 /dev/zero >"$TMP/too-big"
check "上传编码请求超过16MB拒绝" "413" "$(status -X POST --data-binary @"$TMP/too-big" "$BASE/api/admin/images/upload")"

# This checks upstream response statuses, not just a disconnected socket.
for code in 502 503 504; do
  check "上游$code出维护页" "1" "$(body "$BASE/upstream-status/$code" | grep -c 网站维护中 || true)"
  check "上游$code保留状态" "$code" "$(status "$BASE/upstream-status/$code")"
  check "上游$code不缓存" "no-store" "$(header Cache-Control "$BASE/upstream-status/$code")"
done

# Comparator negative probe: do not let a broken check() report a green suite.
before_probe=$FAILS
check "故意损坏响应头负探针" "nosniff" "broken-header"
if (( FAILS != before_probe + 1 )); then
  echo CADDY-NEGATIVE-PROBE-MISSED >&2
  exit 1
fi
FAILS=$before_probe
echo CADDY-NEGATIVE-PROBE-OK

echo "维护页"
kill -TERM "$SSR_PID"
sleep 0.5
check "SSR 连不上：旧站的维护页" "1" "$(body "$BASE/" | grep -c '网站维护中' || true)"
check "维护页不缓存" "no-store" "$(header Cache-Control "$BASE/")"
check "维护页的策略只放开内联样式" "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'" \
  "$(header Content-Security-Policy "$BASE/")"
check "维护页的状态码是 5xx" "5" "$(status "$BASE/" | cut -c1)"

if [ "$FAILS" -ne 0 ]; then
  echo "CADDY-SMOKE：$FAILS 项没过"
  exit 1
fi
echo "CADDY-SMOKE-OK"
