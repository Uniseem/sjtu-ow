"""截现行站和新站的 /_styleguide/ 正文，比文字和像素。

在测试机上：

    uv run python handoff/rounds/238-m2-styleguide-shots/compare.py

先构建新站。现行站用临时库，超管会话不输入密码。两边都不挂排版样式表。
减少动态效果、浅色、宽 1280。图在 /tmp/sjtu-ow-stylecompare/out/。
"""

from __future__ import annotations

import difflib
import importlib.util
import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[3]
WORK = Path("/tmp/sjtu-ow-stylecompare")
OUT = WORK / "out"
WIDTH = 1280
# Antialiasing on the same machine still moves a few edge pixels.
CHANNEL = 18
RATIO_MAX = 0.008
HEIGHT_MAX = 4

spec = importlib.util.spec_from_file_location("ow_screens", ROOT / "scripts/screens.py")
screens = importlib.util.module_from_spec(spec)
spec.loader.exec_module(screens)
screens.WORK = WORK


def seed() -> str:
    # Running the file directly puts the script directory on sys.path, not the repo.
    sys.path.insert(0, str(ROOT))
    import django

    django.setup()
    from django.test import Client
    from django.utils import timezone

    from accounts.models import User
    from core.models import SiteSettings

    now = timezone.now()
    user = User.objects.create_user(
        email="officer@screens.test",
        password=None,
        nickname="截图站长",
        is_sjtu=True,
        agreed_terms_at=now,
        agreed_cross_border_at=now,
    )
    User.objects.filter(pk=user.pk).update(is_superuser=True, is_staff=True)
    settings_obj = SiteSettings.load()
    settings_obj.font_css_path = ""
    settings_obj.save(update_fields=["font_css_path"])
    client = Client()
    client.force_login(user)
    return client.cookies["sessionid"].value


def build_site() -> None:
    subprocess.run(
        ["pnpm", "--filter", "@sjtu-ow/site", "build"],
        cwd=ROOT / "web",
        check=True,
    )


def start_new(port: int, api_port: int) -> subprocess.Popen:
    stub = subprocess.Popen(
        [
            "node",
            "-e",
            (
                "require('node:http').createServer((req,res)=>{"
                "res.writeHead(200,{'content-type':'application/json'});"
                "res.end(JSON.stringify({user:{nickname:'截图站长',admin:true}}));"
                f"}}).listen({api_port})"
            ),
        ]
    )
    server = subprocess.Popen(
        ["node", "dist/server/server.js"],
        cwd=ROOT / "web/apps/site",
        env={
            **dict(**__import__("os").environ),
            "NODE_ENV": "production",
            "STRICT_CSP": "1",
            "PORT": str(port),
            "API_BASE": f"http://127.0.0.1:{api_port}",
        },
    )
    server.stub = stub  # type: ignore[attr-defined]
    return server


def evaluate(tools, expression: str):
    result = tools.send(
        "Runtime.evaluate",
        {"expression": expression, "awaitPromise": True, "returnByValue": True},
    )
    remote = result.get("result", {})
    if remote.get("subtype") == "error" or "exceptionDetails" in result:
        raise RuntimeError(result.get("exceptionDetails") or remote)
    return remote.get("value")


def shoot(tools, url: str, cookie: str | None) -> dict:
    tools.send("Network.clearBrowserCookies")
    if cookie:
        tools.send(
            "Network.setCookie",
            {"name": "sessionid", "value": cookie, "domain": "127.0.0.1", "path": "/"},
        )
    tools.send("Page.navigate", {"url": url})
    time.sleep(0.5)
    for _ in range(40):
        if evaluate(tools, "document.readyState") == "complete":
            break
        time.sleep(0.1)
    # Lazy images below the fold report complete before they start. The
    # specimen is tall; without this the old page is a stack of empty boxes.
    evaluate(
        tools,
        """(() => {
          for (const img of document.images) img.loading = 'eager';
          const step = Math.max(window.innerHeight, 1);
          const limit = document.documentElement.scrollHeight;
          for (let y = 0; y <= limit; y += step) window.scrollTo(0, y);
          window.scrollTo(0, 0);
        })()""",
    )
    for _ in range(40):
        pending = evaluate(tools, "[...document.images].filter((img) => !img.complete).length")
        if pending == 0:
            break
        time.sleep(0.25)
    broken = evaluate(
        tools,
        "[...document.images].filter((img) => img.naturalWidth === 0).map((img) => img.getAttribute('src'))",
    )
    if broken:
        print(f"图片没出来 {url} {broken[:6]} 共 {len(broken)}")
    time.sleep(0.4)
    box = evaluate(
        tools,
        """(() => {
          const el = document.querySelector('#main');
          if (!el) return null;
          const r = el.getBoundingClientRect();
          return {x: r.x + window.scrollX, y: r.y + window.scrollY, width: r.width, height: r.height, text: el.innerText};
        })()""",
    )
    if not box:
        raise SystemExit(f"{url} 没有 #main")
    return box


def save_shot(tools, box: dict, path: Path) -> None:
    shot = tools.send(
        "Page.captureScreenshot",
        {
            "format": "png",
            "captureBeyondViewport": True,
            "clip": {
                "x": box["x"],
                "y": box["y"],
                "width": box["width"],
                "height": box["height"],
                "scale": 1,
            },
        },
    )
    import base64

    path.write_bytes(base64.b64decode(shot["data"]))


def norm(text: str) -> str:
    lines = []
    for line in text.replace("\u3000", " ").splitlines():
        stripped = " ".join(line.split())
        if stripped:
            lines.append(stripped)
    return "\n".join(lines)


def pixel_ratio(old: Path, new: Path) -> tuple[float, tuple[int, int], tuple[int, int]]:
    a = Image.open(old).convert("RGB")
    b = Image.open(new).convert("RGB")
    w, h = min(a.width, b.width), min(a.height, b.height)
    diff = ImageChops.difference(a.crop((0, 0, w, h)), b.crop((0, 0, w, h)))
    mask = None
    for band in diff.split():
        hot = band.point(lambda p: 255 if p > CHANNEL else 0)
        mask = hot if mask is None else ImageChops.lighter(mask, hot)
    bad = sum(1 for p in mask.getdata() if p)
    mask.save(OUT / "diff.png")
    return bad / (w * h), a.size, b.size


def main() -> None:
    shutil.rmtree(WORK, ignore_errors=True)
    OUT.mkdir(parents=True)
    build_site()
    if not (ROOT / "static/css/app.css").exists():
        screens.manage("tailwind", "build")
    screens.manage("migrate", "--noinput", stdout=subprocess.DEVNULL)
    screens.manage("createcachetable")
    screens.manage("init_site", "--verbosity", "0", stdout=subprocess.DEVNULL)
    import os

    os.environ.update(screens.site_env())
    cookie = seed()

    old_port, new_port, api_port, debug = (screens.free_port() for _ in range(4))
    django = subprocess.Popen(
        [sys.executable, "manage.py", "runserver", f"127.0.0.1:{old_port}", "--noreload"],
        cwd=ROOT,
        env=screens.site_env(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    node = start_new(new_port, api_port)
    profile = WORK / "chromium-profile"
    browser = subprocess.Popen(
        [
            "chromium",
            "--headless=new",
            "--no-sandbox",
            "--hide-scrollbars",
            f"--remote-debugging-port={debug}",
            f"--user-data-dir={profile}",
            f"--window-size={WIDTH},900",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        screens.wait_for(f"http://127.0.0.1:{old_port}/robots.txt")
        screens.wait_for(f"http://127.0.0.1:{new_port}/")
        screens.wait_for(f"http://127.0.0.1:{debug}/json/version")
        targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{debug}/json"))
        page = next(t for t in targets if t.get("type") == "page")
        tools = screens.DevTools(page["webSocketDebuggerUrl"])
        tools.sock.settimeout(180)
        tools.send("Page.enable")
        tools.send("Network.enable")
        tools.send(
            "Emulation.setEmulatedMedia",
            {
                "features": [
                    {"name": "prefers-color-scheme", "value": "light"},
                    {"name": "prefers-reduced-motion", "value": "reduce"},
                ]
            },
        )
        tools.send(
            "Emulation.setDeviceMetricsOverride",
            {"width": WIDTH, "height": 900, "deviceScaleFactor": 1, "mobile": False},
        )
        tools.send(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "localStorage.setItem('ow-theme','light')"},
        )
        old = shoot(tools, f"http://127.0.0.1:{old_port}/_styleguide/", cookie)
        save_shot(tools, old, OUT / "old.png")
        new = shoot(tools, f"http://127.0.0.1:{new_port}/_styleguide/", None)
        save_shot(tools, new, OUT / "new.png")
    finally:
        browser.terminate()
        django.terminate()
        node.terminate()
        node.stub.terminate()  # type: ignore[attr-defined]
        browser.wait(timeout=10)
        django.wait(timeout=10)
        node.wait(timeout=10)

    old_text, new_text = norm(old["text"]), norm(new["text"])
    (OUT / "old.txt").write_text(old_text, encoding="utf-8")
    (OUT / "new.txt").write_text(new_text, encoding="utf-8")
    if old_text != new_text:
        diff = "\n".join(
            difflib.unified_diff(
                old_text.splitlines(),
                new_text.splitlines(),
                fromfile="old",
                tofile="new",
                lineterm="",
            )
        )
        print(diff)
        raise SystemExit("正文不一致")
    ratio, old_size, new_size = pixel_ratio(OUT / "old.png", OUT / "new.png")
    height_gap = abs(old_size[1] - new_size[1])
    print(
        f"正文一致。像素差 {ratio:.4%}，高度 {old_size[1]} / {new_size[1]}（差 {height_gap}px）"
    )
    if ratio > RATIO_MAX or height_gap > HEIGHT_MAX:
        raise SystemExit("截图像差过大")
    print("COMPARE-OK")


if __name__ == "__main__":
    main()
