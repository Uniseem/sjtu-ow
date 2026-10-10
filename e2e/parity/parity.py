"""旧站和新站逐页对拍（docs/frontend-migration.md 9.2）。

在测试机上（要 uv、go、node24、pnpm、docker、chromium）：

    bash scripts/remote-check.sh run bash e2e/parity/run.sh [--only 前缀,…] [--wide] [--strict]

同一份数据：旧站（Django，仓库里的代码）用 scripts/screens.py 的种子数据建临时库，
新站 `sjtuow migrate` → `sjtuow import` 这个库 → `sjtuow import-media` 同一个媒体目录。
两边的会话都在服务器上直接发，不输入任何密码。新站按正式站的样子跑：Go + SSR 生产构建
+ 真 Caddy（deploy/Caddyfile.new，容器）。

每个「地址 × 身份」比：状态码和跳转去向、<title>、#main 的纯文本、#main 里的链接、
表单控件、坏图，以及 #main 的截图（默认 1280 浅色；--wide 再加 375 和深色）。
结果在 /tmp/sjtu-ow-parity/out/：report.md、results.json、shots/。

结论：每行「通过」或「不同」。--strict 时有任何一行不是「通过」就退出码 1（做完一组
页面时用它证明「对拍通过」，9.4）；不加 --strict 只出报告（现在大部分页面还没重写）。
"""

from __future__ import annotations

import base64
import difflib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = Path("/tmp/sjtu-ow-parity")
OUT = WORK / "out"
SHOTS = OUT / "shots"

# 截图逐像素比：同一台机器上抗锯齿也会挪几个边缘像素（238 的口径）；上限等第 10 节第 4 件拍板，
# 先用文档建议的 0.5%。
CHANNEL = 18
RATIO_MAX = 0.005

spec = importlib.util.spec_from_file_location("ow_screens", ROOT / "scripts/screens.py")
screens = importlib.util.module_from_spec(spec)
spec.loader.exec_module(screens)
screens.WORK = WORK

# (名字, 身份, 地址)。地址里的 {team} 这类来自种子数据。身份：visitor、member、captain、officer。
PAGES = [
    # 内容
    ("home", "visitor", "/"),
    ("home", "member", "/"),
    ("news", "visitor", "/news/"),
    ("article", "visitor", "/news/screens-guide/"),
    ("article", "member", "/news/screens-guide/"),
    ("about", "visitor", "/about/"),
    ("terms", "visitor", "/terms/"),
    ("privacy", "visitor", "/privacy/"),
    ("search", "visitor", "/search/?q=截图"),
    ("submit", "visitor", "/submit/"),
    ("submit", "member", "/submit/"),
    # 战队、成员
    ("teams", "visitor", "/teams/"),
    ("team", "visitor", "/teams/{team}/"),
    ("team", "member", "/teams/{team}/"),
    ("team-new", "member", "/teams/new/"),
    ("team-manage", "captain", "/teams/{team}/manage/"),
    ("members", "visitor", "/members/"),
    ("members-filter", "visitor", "/members/?role=support&free=1"),
    ("member", "visitor", "/members/{member}/"),
    # 赛事、内战
    ("tournaments", "visitor", "/tournaments/"),
    ("cup", "visitor", "/tournaments/{cup}/"),
    ("cup", "member", "/tournaments/{cup}/"),
    ("teamcup", "captain", "/tournaments/{teamcup}/"),
    ("cup-signup", "member", "/tournaments/{cup}/signup/"),
    ("teamcup-register", "captain", "/tournaments/{teamcup}/register/"),
    ("registration", "captain", "/registrations/{registration}/"),
    ("scrims", "visitor", "/scrims/"),
    ("scrim", "visitor", "/scrims/{scrim}/"),
    ("scrim", "member", "/scrims/{scrim}/"),
    # 个人中心、发信
    ("me", "visitor", "/me/"),
    ("me", "member", "/me/"),
    ("me-game-accounts", "member", "/me/game-accounts/"),
    ("me-contacts", "member", "/me/contacts/"),
    ("me-security", "member", "/me/security/"),
    ("me-delete", "member", "/me/delete/"),
    ("me-teams", "member", "/me/teams/"),
    ("me-registrations", "member", "/me/registrations/"),
    ("me-scrims", "member", "/me/scrims/"),
    ("letters", "member", "/letters/"),
    ("letters-confirm", "member", "/letters/{front_letters}/"),
    # 账号入口
    ("login", "visitor", "/accounts/login/"),
    ("signup", "visitor", "/accounts/signup/"),
    ("password-reset", "visitor", "/accounts/password/reset/"),
    ("password-change", "member", "/accounts/password/change/"),
    ("email", "member", "/accounts/email/"),
    ("logout", "member", "/accounts/logout/"),
    # 其他。404 不在这里比：旧站跑的是开发设置（DEBUG），给的是 Django 的调试页，不是
    # templates/errors/404.html；错误页逐字照旧站由 web/apps/site 的测试和 browser-check 管（263）。
    ("styleguide", "officer", "/_styleguide/"),
]

EMAILS = {
    "member": "member@screens.test",
    "captain": "captain@screens.test",
    "officer": "officer@screens.test",
}


# --- 旧站的种子（在 Django 里跑：parity.py seed） ------------------------------------


def seed() -> dict:
    data = screens.seed()
    from tournaments.models import Registration

    registration = Registration.objects.filter(tournament_id=data["teamcup"]).order_by("pk").first()
    data["registration"] = registration.pk if registration else 0
    return data


# --- 起两边的服务 ------------------------------------------------------------------


def run(cmd, **kwargs):
    return subprocess.run(cmd, check=True, **kwargs)


def new_env(api_port: int) -> dict:
    return {
        **os.environ,
        "DATA_DIR": str(WORK / "new-data"),
        "MEDIA_DIR": str(WORK / "media"),
        "SITE_URL": "http://127.0.0.1",
        "SIGNING_KEY": "parity-signing-key-0123456789-abcdefghij",
        "FIELD_ENCRYPTION_KEY": "parity-field-key-0123456789-abcdefghijk",
        "SJTUOW_HTTP_ADDR": f"127.0.0.1:{api_port}",
    }


def prepare_legacy() -> dict:
    if not (ROOT / "static/css/app.css").exists():
        screens.manage("tailwind", "build")
    screens.manage("migrate", "--noinput", stdout=subprocess.DEVNULL)
    screens.manage("createcachetable")
    screens.manage("init_site", "--verbosity", "0", stdout=subprocess.DEVNULL)
    seeded = subprocess.run(
        [sys.executable, __file__, "seed"],
        cwd=ROOT,
        env=screens.site_env(),
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(seeded.stdout.strip().splitlines()[-1])


def prepare_new(env: dict) -> dict:
    binary = WORK / "sjtuow"
    run(["go", "build", "-o", str(binary), "./cmd/sjtuow"], cwd=ROOT / "server")
    (WORK / "new-data").mkdir(parents=True, exist_ok=True)
    run([str(binary), "migrate"], env=env, stdout=subprocess.DEVNULL)
    run([str(binary), "import", str(WORK / "db.sqlite3")], env=env, stdout=subprocess.DEVNULL)
    made = subprocess.run([str(binary), "import-media", str(WORK / "media")], env=env, capture_output=True, text=True)
    print(made.stdout.strip().splitlines()[0] if made.stdout.strip() else made.stderr.strip())
    sessions = {}
    for who, email in EMAILS.items():
        out = subprocess.run([str(binary), "session", email], env=env, check=True, capture_output=True, text=True)
        sessions[who] = out.stdout.strip()
    return sessions


def assets_dir() -> Path:
    assets = WORK / "assets"
    shutil.copytree(ROOT / "web/apps/site/dist/client", assets)
    shutil.copytree(ROOT / "static/img", assets / "img")
    (assets / "css").mkdir()
    shutil.copy(ROOT / "static/css/error.css", assets / "css/error.css")
    return assets


def start_new(env: dict, api_port: int, ssr_port: int, caddy_port: int) -> list:
    procs = []
    procs.append(subprocess.Popen([str(WORK / "sjtuow"), "serve"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    procs.append(
        subprocess.Popen(
            ["node", "dist/server/server.js"],
            cwd=ROOT / "web/apps/site",
            env={**os.environ, "NODE_ENV": "production", "PORT": str(ssr_port), "API_BASE": f"http://127.0.0.1:{api_port}"},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    )
    assets = assets_dir()
    run(
        [
            "docker", "run", "-d", "--name", "ow-parity-caddy", "--network", "host",
            "-e", f"CADDY_SITE_ADDRESS=:{caddy_port}",
            "-e", f"API_UPSTREAM=127.0.0.1:{api_port}",
            "-e", f"SSR_UPSTREAM=127.0.0.1:{ssr_port}",
            "-v", f"{ROOT}/deploy/Caddyfile.new:/etc/caddy/Caddyfile:ro",
            "-v", f"{ROOT}/deploy/error_pages:/srv/error_pages:ro",
            "-v", f"{assets}:/var/assets:ro",
            "-v", f"{WORK}/media:/var/media:ro",
            "caddy:2.10-alpine",
        ],
        stdout=subprocess.DEVNULL,
    )
    return procs


# --- 看一页 ------------------------------------------------------------------------


def evaluate(tools, expression: str):
    result = tools.send("Runtime.evaluate", {"expression": expression, "awaitPromise": True, "returnByValue": True})
    remote = result.get("result", {})
    if "exceptionDetails" in result:
        raise RuntimeError(result["exceptionDetails"])
    return remote.get("value")


def fetch_status(url: str, cookie: str | None) -> tuple[int, str]:
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    request = urllib.request.Request(url, headers={"Cookie": cookie} if cookie else {})
    try:
        with opener.open(request, timeout=20) as response:
            return response.status, ""
    except urllib.error.HTTPError as err:
        location = err.headers.get("Location", "") or ""
        if location.startswith("http"):
            location = "/" + location.split("/", 3)[3] if location.count("/") >= 3 else location
        return err.code, location


SNAPSHOT = """(() => {
  const main = document.querySelector('#main') || document.querySelector('main') || document.body;
  const text = main.innerText.split('\\n').map((l) => l.replace(/\\s+/g, ' ').trim()).filter(Boolean);
  const links = [...new Set([...main.querySelectorAll('a[href]')].map((a) => {
    const u = new URL(a.getAttribute('href'), location.href);
    return u.origin === location.origin ? u.pathname + u.search + u.hash : u.href;
  }))].sort();
  const fields = [...main.querySelectorAll('input,select,textarea,button')]
    .filter((el) => el.type !== 'hidden' && el.name !== 'csrfmiddlewaretoken')
    .map((el) => `${el.tagName.toLowerCase()}:${el.type || ''}:${el.name || ''}`).sort();
  const broken = [...document.images].filter((img) => img.complete && img.naturalWidth === 0).map((img) => img.getAttribute('src'));
  const box = main.getBoundingClientRect();
  return { title: document.title, text, links, fields, broken,
           box: { x: box.left + scrollX, y: box.top + scrollY, width: box.width, height: box.height } };
})()"""


def look(tools, url: str, cookie: dict | None, width: int, scheme: str, shot: Path) -> dict:
    tools.send("Network.clearBrowserCookies")
    if cookie:
        tools.send("Network.setCookie", {**cookie, "domain": "127.0.0.1", "path": "/"})
    tools.send("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": width < 600})
    tools.send(
        "Emulation.setEmulatedMedia",
        {"features": [{"name": "prefers-color-scheme", "value": scheme}, {"name": "prefers-reduced-motion", "value": "reduce"}]},
    )
    tools.send("Page.navigate", {"url": url})
    time.sleep(0.5)
    for _ in range(60):
        if evaluate(tools, "document.readyState") == "complete":
            break
        time.sleep(0.1)
    evaluate(
        tools,
        """(() => { for (const img of document.images) img.loading = 'eager';
          const step = Math.max(innerHeight, 1); const limit = document.documentElement.scrollHeight;
          for (let y = 0; y <= limit; y += step) scrollTo(0, y); scrollTo(0, 0); })()""",
    )
    for _ in range(40):
        if evaluate(tools, "[...document.images].filter((img) => !img.complete).length") == 0:
            break
        time.sleep(0.25)
    time.sleep(0.3)
    snap = evaluate(tools, SNAPSHOT)
    box = snap.pop("box")
    if box["width"] > 0 and box["height"] > 0:
        data = tools.send(
            "Page.captureScreenshot",
            {"format": "png", "captureBeyondViewport": True, "clip": {**box, "scale": 1}},
        )
        shot.write_bytes(base64.b64decode(data["data"]))
    return snap


def pixel_ratio(a: Path, b: Path) -> tuple[float, str]:
    from PIL import Image, ImageChops

    if not a.exists() or not b.exists():
        return 1.0, "缺截图"
    left, right = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    note = "" if left.size == right.size else f"尺寸 {left.size[0]}×{left.size[1]} / {right.size[0]}×{right.size[1]}"
    width, height = max(left.width, right.width), max(left.height, right.height)
    canvas = [Image.new("RGB", (width, height), (255, 0, 255)) for _ in range(2)]
    canvas[0].paste(left, (0, 0))
    canvas[1].paste(right, (0, 0))
    # 每个像素取三个通道里差得最多的那个，超过 CHANNEL 算「不同」。
    red, green, blue = ImageChops.difference(*canvas).split()
    widest = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    changed = sum(widest.histogram()[CHANNEL + 1 :])
    return changed / (width * height), note


# --- 主流程 -------------------------------------------------------------------------


def compare(old: dict, new: dict, ratio: float, status: tuple) -> list[str]:
    problems = []
    if status[0] != status[1]:
        problems.append(f"状态 {status[0]} / {status[1]}")
    if old["title"] != new["title"]:
        problems.append(f"标题「{old['title']}」/「{new['title']}」")
    if old["text"] != new["text"]:
        diff = [line for line in difflib.unified_diff(old["text"], new["text"], lineterm="", n=0) if line[:1] in "+-" and line[:3] not in ("+++", "---")]
        problems.append("正文不同：" + "；".join(diff[:6]) + ("…" if len(diff) > 6 else ""))
    if old["links"] != new["links"]:
        gone = sorted(set(old["links"]) - set(new["links"]))
        extra = sorted(set(new["links"]) - set(old["links"]))
        problems.append(f"链接 少 {gone[:5]} 多 {extra[:5]}")
    if old["fields"] != new["fields"]:
        problems.append(f"表单 {old['fields']} / {new['fields']}")
    if new["broken"]:
        problems.append(f"新站坏图 {new['broken'][:3]}")
    if ratio > RATIO_MAX:
        problems.append(f"像素差 {ratio:.2%}")
    return problems


def main(argv: list[str]) -> int:
    only = next((a.split("=", 1)[1].split(",") for a in argv if a.startswith("--only=")), None)
    wide = "--wide" in argv
    strict = "--strict" in argv
    pages = [p for p in PAGES if not only or any(
        prefix and (p[0].startswith(prefix) or p[2].startswith(prefix)) for prefix in only
    )]
    if not pages:
        print("PARITY-ERROR: --only 没有匹配任何页面，不能算通过", file=sys.stderr)
        return 2
    shutil.rmtree(WORK, ignore_errors=True)
    SHOTS.mkdir(parents=True)

    print("== 旧站：迁移、种子数据")
    data = prepare_legacy()
    ports = [screens.free_port() for _ in range(5)]
    old_port, api_port, ssr_port, caddy_port, debug_port = ports
    env = new_env(api_port)
    print("== 新站：迁移、导入、图片母版、会话")
    new_sessions = prepare_new(env)

    procs = []
    try:
        procs.append(
            subprocess.Popen(
                [sys.executable, "manage.py", "runserver", f"127.0.0.1:{old_port}", "--noreload"],
                cwd=ROOT, env=screens.site_env(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        )
        procs.extend(start_new(env, api_port, ssr_port, caddy_port))
        procs.append(
            subprocess.Popen(
                ["chromium", "--headless=new", "--no-sandbox", "--hide-scrollbars",
                 f"--remote-debugging-port={debug_port}", f"--user-data-dir={WORK / 'chromium'}",
                 "--window-size=1280,900", "about:blank"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        )
        screens.wait_for(f"http://127.0.0.1:{old_port}/robots.txt")
        screens.wait_for(f"http://127.0.0.1:{caddy_port}/robots.txt")
        screens.wait_for(f"http://127.0.0.1:{debug_port}/json/version")
        targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{debug_port}/json"))
        tools = screens.DevTools(next(t for t in targets if t.get("type") == "page")["webSocketDebuggerUrl"])
        tools.send("Page.enable")
        tools.send("Network.enable")

        views = [(1280, "light")] + ([(375, "light"), (1280, "dark"), (375, "dark")] if wide else [])
        results = []
        for name, who, template in pages:
            # 中文查询参数要编码成百分号形式，urllib 只收 ASCII（浏览器里也是这样发的）
            path = urllib.parse.quote(template.format(**data), safe="/?=&#%")
            old_cookie = {"name": "sessionid", "value": data["sessions"][who]} if who in data["sessions"] else None
            new_cookie = {"name": "ow_session", "value": new_sessions[who]} if who in new_sessions else None
            status = (
                fetch_status(f"http://127.0.0.1:{old_port}{path}", f"sessionid={old_cookie['value']}" if old_cookie else None),
                fetch_status(f"http://127.0.0.1:{caddy_port}{path}", f"ow_session={new_cookie['value']}" if new_cookie else None),
            )
            row = {"name": name, "who": who, "path": path, "status": status, "views": []}
            for width, scheme in views:
                stem = f"{name}-{who}-{width}-{scheme}"
                old = look(tools, f"http://127.0.0.1:{old_port}{path}", old_cookie, width, scheme, SHOTS / f"{stem}-old.png")
                new = look(tools, f"http://127.0.0.1:{caddy_port}{path}", new_cookie, width, scheme, SHOTS / f"{stem}-new.png")
                ratio, note = pixel_ratio(SHOTS / f"{stem}-old.png", SHOTS / f"{stem}-new.png")
                problems = compare(old, new, ratio, (status[0][0], status[1][0]) if (width, scheme) == views[0] else (0, 0))
                if note:
                    problems.append(note)
                row["views"].append({"view": f"{width}-{scheme}", "ratio": ratio, "problems": problems})
            row["pass"] = all(not v["problems"] for v in row["views"])
            results.append(row)
            mark = "通过" if row["pass"] else "不同"
            print(f"{mark}  {who:8} {path}" + ("" if row["pass"] else "  ← " + "；".join(row["views"][0]["problems"])[:240]))
    finally:
        subprocess.run(["docker", "rm", "-f", "ow-parity-caddy"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for proc in procs:
            proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

    passed = sum(1 for r in results if r["pass"])
    (OUT / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = [
        "# 对拍报告",
        "",
        f"{passed} / {len(results)} 通过（像素差上限 {RATIO_MAX:.1%}，通道差 {CHANNEL}）",
        "",
        "| 结论 | 身份 | 地址 | 状态（旧/新） | 问题 |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        problems = "；".join(p for v in r["views"] for p in v["problems"]).replace("|", "\\|")
        lines.append(f"| {'通过' if r['pass'] else '不同'} | {r['who']} | `{r['path']}` | {r['status'][0][0]} / {r['status'][1][0]} | {problems[:400]} |")
    (OUT / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nPARITY {passed}/{len(results)} 通过；报告 {OUT / 'report.md'}，截图 {SHOTS}")
    return 1 if strict and passed != len(results) else 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    if sys.argv[1:2] == ["seed"]:
        import django

        django.setup()
        print(json.dumps(seed()))
    else:
        sys.exit(main(sys.argv[1:]))
