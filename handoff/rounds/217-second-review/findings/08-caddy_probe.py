"""217 复核 08：真 Caddy 对「字体原文件 404」的各种变形地址，以及 /media/documents/。

照 215 的 caddy_probe.py 起 caddy:2.10-alpine，原样发路径（http.client，不做任何规范化）。

  bash scripts/remote-check.sh run uv run python \
    handoff/rounds/217-second-review/findings/08-caddy_probe.py
"""

import http.client
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
IMAGE = "caddy:2.10-alpine"
CADDYFILE = ROOT / "deploy" / "Caddyfile"
SECRET = "UPLOADED ORIGINAL"
WORK = Path(tempfile.mkdtemp(prefix="caddy-217-"))
FILES = {
    "media/fonts/3/original/Secret-Bold.otf": SECRET,
    "media/fonts/3/original/Secret-Bold.woff2": SECRET,
    "media/fonts/3/700-000.abcd1234.woff2": "slice",
    "media/fonts/css/fonts.0123456789ab.css": "css",
    "media/documents/note.html": "<script>alert(document.domain)</script>",
    "media/documents/pic.svg": '<svg xmlns="http://www.w3.org/2000/svg"><script>1</script></svg>',
    "prerendered/index.html": "home",
    "prerendered/news/a/index.html": "article a",
    "error_pages/maintenance.html": "maintenance",
    "static/x.css": "x",
}
for name, body in FILES.items():
    target = WORK / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
(WORK / "django.Caddyfile").write_text(
    "{\n\tadmin off\n}\n:8000 {\n\trespond \"django answered\" 200\n}\n",
    encoding="utf-8",
)
TAG = f"c217-{int(time.time())}"


def docker(*args, check=True):
    return subprocess.run(["docker", *args], check=check, capture_output=True, text=True)


docker("network", "create", TAG)
try:
    docker("run", "-d", "--name", f"{TAG}-web", "--network", TAG, "--network-alias",
           "web", "-v", f"{WORK / 'django.Caddyfile'}:/etc/caddy/Caddyfile:ro", IMAGE)
    docker("run", "-d", "--name", f"{TAG}-proxy", "--network", TAG,
           "-p", "127.0.0.1::80", "-e", "CADDY_SITE_ADDRESS=:80",
           "-v", f"{CADDYFILE}:/etc/caddy/Caddyfile:ro",
           "-v", f"{WORK / 'error_pages'}:/srv/error_pages:ro",
           "-v", f"{WORK / 'static'}:/srv/static:ro",
           "-v", f"{WORK / 'media'}:/srv/media:ro",
           "-v", f"{WORK / 'prerendered'}:/srv/prerendered:ro", IMAGE)  # fmt: skip
    port = int(docker("port", f"{TAG}-proxy", "80").stdout.split(":")[-1])

    def get(path, method="GET"):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.putrequest(method, path, skip_accept_encoding=True)
        conn.endheaders()
        response = conn.getresponse()
        body = response.read().decode("utf-8", "replace")
        conn.close()
        return response.status, response.headers, body

    for _ in range(50):
        try:
            get("/static/x.css")
            break
        except OSError:
            time.sleep(0.2)

    print("== 字体原文件的变形地址（应全部拿不到原文件）==")
    leaks = 0
    for path in (
        "/media/fonts/3/original/Secret-Bold.woff2",
        "/media//fonts/3/original/Secret-Bold.woff2",
        "/media/fonts//3/original/Secret-Bold.woff2",
        "/media/fonts/3//original/Secret-Bold.woff2",
        "/media/fonts/3/original//Secret-Bold.woff2",
        "/media/fonts/3/original%2FSecret-Bold.woff2",
        "/media/fonts/3%2Foriginal%2FSecret-Bold.woff2",
        "/media/fonts/3/original%2fSecret-Bold.woff2",
        "/media/%66onts/3/original/Secret-Bold.otf",
        "/media/fonts/3/./original/Secret-Bold.otf",
        "/media/./fonts/3/original/Secret-Bold.otf",
        "/media/fonts/3/x/../original/Secret-Bold.woff2",
        "/media/fonts/../fonts/3/original/Secret-Bold.otf",
        "/static/../media/fonts/3/original/Secret-Bold.otf",
        "/media/fonts/3/original\\Secret-Bold.woff2",
        "/media/fonts/3/original%5CSecret-Bold.woff2",
        "/MEDIA/fonts/3/original/Secret-Bold.otf",
        "/media/FONTS/3/original/Secret-Bold.otf",
        "/media/fonts/3/ORIGINAL/Secret-Bold.otf",
        "/media/fonts/3/original/Secret-Bold.otf/",
        "/media/fonts/3/original/Secret-Bold.otf%00",
        "/media/fonts/3/original/Secret-Bold.otf?download=1",
        "/media/fonts/3/original/",
        "/media/fonts/3/",
    ):
        try:
            status, headers, body = get(path)
        except Exception as exc:  # noqa: BLE001
            print(f"  ERR  {path}  {exc}")
            continue
        leaked = SECRET in body
        leaks += leaked
        print(f"  {'LEAK' if leaked else 'ok  '} {status} {path}")
    print(f"  泄露 {leaks} 处")

    print("== 正常分片仍然 200 ==")
    for path in ("/media/fonts/3/700-000.abcd1234.woff2",
                 "/media/fonts/css/fonts.0123456789ab.css"):
        status, headers, _ = get(path)
        print(f"  {status} {path} {headers['Cache-Control']}")

    print("== /media/documents/（Wagtail 文档，任何扩展名）==")
    for path in ("/media/documents/note.html", "/media/documents/pic.svg"):
        status, headers, body = get(path)
        print(f"  {status} {path} Content-Type={headers['Content-Type']} "
              f"nosniff={headers['X-Content-Type-Options']} "
              f"CSP={headers['Content-Security-Policy']} "
              f"Content-Disposition={headers['Content-Disposition']} "
              f"body={body[:40]!r}")

    print("== 预渲染 ==")
    for path in ("/news/a/", "/news/a", "/news/a/index.html"):
        status, headers, body = get(path)
        print(f"  {status} {path} body={body[:20]!r} CSP={'有' if headers['Content-Security-Policy'] else '无'}")
finally:
    docker("rm", "-f", f"{TAG}-proxy", f"{TAG}-web", check=False)
    docker("network", "rm", TAG, check=False)
