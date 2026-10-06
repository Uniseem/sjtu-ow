"""Round 215: the real Caddy, with the repo's Caddyfile, asked for real.

C4 (font originals 404) and C6 (HSTS on what Caddy serves itself) are pinned
by tests that read the Caddyfile as text. Whether Caddy then routes the way
the text reads (its own ordering of `handle` blocks, snippets importing
snippets) only Caddy can say. This starts `caddy:2.10-alpine` with the same
mounts as deploy/docker-compose.yml, a stand-in for Django (another Caddy
that answers with its own HSTS value), and checks each kind of address.

Run on the test machine (has Docker and the image):
  bash scripts/remote-check.sh run uv run python \\
    handoff/rounds/215-caddy-and-prerender/caddy_probe.py

`--caddyfile PATH` runs it against another Caddyfile (the control: the one
before this round must fail). Exit code 1 if any check fails.
"""

import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
IMAGE = "caddy:2.10-alpine"
CADDYFILE = ROOT / "deploy" / "Caddyfile"
if "--caddyfile" in sys.argv:
    CADDYFILE = Path(sys.argv[sys.argv.index("--caddyfile") + 1]).resolve()
HSTS = "max-age=31536000; includeSubDomains; preload"
FROM_DJANGO = "from-the-stand-in-django"

WORK = Path(tempfile.mkdtemp(prefix="caddy-probe-"))
FILES = {
    "static/css/app.0123456789ab.css": "hashed static",
    "static/js/plain.js": "plain static",
    "media/fonts/css/fonts.0123456789ab.css": "font stylesheet",
    "media/fonts/3/latin.0123456789ab.woff2": "font slice",
    "media/fonts/3/original/Secret-Bold.otf": "UPLOADED ORIGINAL",
    "media/fonts/3/original/Secret-Bold.woff2": "UPLOADED ORIGINAL",
    "media/images/face.fill-96x96.jpg": "thumbnail",
    "media/original_images/face.jpg": "public picture",
    "prerendered/index.html": "<!doctype html><title>home</title>prerendered home",
    "error_pages/maintenance.html": "maintenance",
}
for name, body in FILES.items():
    target = WORK / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
(WORK / "django.Caddyfile").write_text(
    "{\n\tadmin off\n}\n:8000 {\n"
    f'\theader Strict-Transport-Security "{FROM_DJANGO}"\n'
    '\trespond "django answered" 200\n}\n',
    encoding="utf-8",
)

TAG = f"c215-{int(time.time())}"


def docker(*args, check=True):
    return subprocess.run(
        ["docker", *args], check=check, capture_output=True, text=True
    )


docker("network", "create", TAG)
try:
    docker(
        "run", "-d", "--name", f"{TAG}-web", "--network", TAG,
        "--network-alias", "web",
        "-v", f"{WORK / 'django.Caddyfile'}:/etc/caddy/Caddyfile:ro",
        IMAGE,
    )  # fmt: skip
    docker(
        "run", "-d", "--name", f"{TAG}-proxy", "--network", TAG,
        "-p", "127.0.0.1::80", "-e", "CADDY_SITE_ADDRESS=:80",
        "-v", f"{CADDYFILE}:/etc/caddy/Caddyfile:ro",
        "-v", f"{WORK / 'error_pages'}:/srv/error_pages:ro",
        "-v", f"{WORK / 'static'}:/srv/static:ro",
        "-v", f"{WORK / 'media'}:/srv/media:ro",
        "-v", f"{WORK / 'prerendered'}:/srv/prerendered:ro",
        IMAGE,
    )  # fmt: skip
    port = docker("port", f"{TAG}-proxy", "80").stdout.split(":")[-1].strip()
    base = f"http://127.0.0.1:{port}"

    def get(path):
        request = urllib.request.Request(base + path)
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, response.headers, response.read().decode()
        except urllib.error.HTTPError as error:
            return error.code, error.headers, error.read().decode()

    for _ in range(50):
        try:
            get("/static/js/plain.js")
            break
        except OSError:
            time.sleep(0.2)
    else:
        print(docker("logs", f"{TAG}-proxy", check=False).stderr[-3000:])
        raise SystemExit("Caddy 没有起来")

    results = []

    def check(name, ok, seen):
        results.append(ok)
        print(("ok   " if ok else "FAIL ") + f"{name}  [{seen}]")

    def hsts(headers):
        return headers.get_all("Strict-Transport-Security") or []

    print(f"Caddyfile: {CADDYFILE}\n")
    for path in (
        "/media/fonts/3/original/Secret-Bold.otf",
        "/media/fonts/3/original/Secret-Bold.woff2",
    ):
        status, _, body = get(path)
        check(f"C4 原文件 {path} 是 404", status == 404, status)
        check("   且没有给出文件内容", "UPLOADED ORIGINAL" not in body, len(body))

    for path, cache in (
        ("/", "public, max-age=0, must-revalidate"),
        ("/static/css/app.0123456789ab.css", "public, max-age=31536000, immutable"),
        ("/static/js/plain.js", "public, max-age=300, must-revalidate"),
        ("/media/fonts/css/fonts.0123456789ab.css", "immutable"),
        ("/media/fonts/3/latin.0123456789ab.woff2", "immutable"),
        ("/media/images/face.fill-96x96.jpg", "immutable"),
        ("/media/original_images/face.jpg", "public, max-age=86400"),
    ):
        status, headers, _ = get(path)
        check(f"{path} 是 200", status == 200, status)
        check(f"   缓存头照旧（{cache}）", cache in (headers["Cache-Control"] or ""),
              headers["Cache-Control"])  # fmt: skip
        check("   C6 带 HSTS，值和 Django 一样", hsts(headers) == [HSTS], hsts(headers))

    status, headers, _ = get("/")
    check("预渲染首页仍带 CSP", "default-src 'self'" in (
        headers["Content-Security-Policy"] or ""), status)  # fmt: skip

    for path in ("/accounts/login/", "/?q=1", "/healthz"):
        status, headers, body = get(path)
        check(f"{path} 交给 Django", body == "django answered", body[:40])
        check(
            "   HSTS 只有 Django 自己那一个，没叠一份",
            hsts(headers) == [FROM_DJANGO],
            hsts(headers),
        )
finally:
    docker("rm", "-f", f"{TAG}-proxy", f"{TAG}-web", check=False)
    docker("network", "rm", TAG, check=False)

failed = results.count(False)
print(f"\n{len(results) - failed} 项通过，{failed} 项失败")
sys.exit(1 if failed else 0)
