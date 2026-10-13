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
import sqlite3
import http.server
import threading
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
WORK = Path(os.environ.get("PARITY_WORK", "/tmp/sjtu-ow-parity"))
OUT = WORK / "out"
SHOTS = OUT / "shots"

# 截图逐像素比：同一台机器上抗锯齿也会挪几个边缘像素（238 的口径）；上限等第 10 节第 4 件拍板，
# 先用文档建议的 0.5%。
CHANNEL = 18
RATIO_MAX = 0.005
TEST_SITE_URL = "http://localhost:8000"
TEST_SIGNING_KEY = "parity-signing-key-0123456789-abcdefghij"

spec = importlib.util.spec_from_file_location("ow_screens", ROOT / "scripts/screens.py")
screens = importlib.util.module_from_spec(spec)
spec.loader.exec_module(screens)
screens.WORK = WORK

from page_matrix import PAGES, RESOURCES, negative_probe
from account_scenarios import EXTRA_EMAILS

EMAILS = {
    "member": "member@screens.test",
    "captain": "captain@screens.test",
    "officer": "officer@screens.test",
    **EXTRA_EMAILS,
}


# --- 旧站的种子（在 Django 里跑：parity.py seed） ------------------------------------


def seed(accounts=False) -> dict:
    data = screens.seed()
    from account_scenarios import extend_seed
    extend_seed(data)
    from admin_scenarios import extend_seed as extend_admin_seed
    extend_admin_seed(data)
    # screens.py intentionally makes password-less screenshot identities.
    # Account parity needs ordinary password accounts, as on the real site.
    from accounts.models import User
    from django.test import Client

    for user in User.objects.filter(email__endswith="@screens.test"):
        user.set_password("ParityPassword!2026")
        user.save(update_fields=["password"])
    # Changing the password also invalidates the previously seeded sessions.
    for who in data["sessions"]:
        client = Client()
        client.force_login(User.objects.get(email=f"{who}@screens.test"))
        data["sessions"][who] = client.cookies["sessionid"].value
    from tournaments.models import Registration

    registration = Registration.objects.filter(tournament_id=data["teamcup"]).order_by("pk").first()
    data["registration"] = registration.pk if registration else 0
    from core.models import HeldLetter
    from core.services import unsubscribe_token
    from wagtail.images import get_image_model
    member = User.objects.get(pk=data['member'])
    data['game_account'] = member.game_accounts.first().pk
    data['contact'] = member.contact_methods.first().pk
    data['image'] = get_image_model().objects.order_by('pk').first().pk
    if '--components' in sys.argv:
        # The component oracle explicitly exercises this public cover. Resolve
        # the image first: screens.seed() deliberately does not expose its ID.
        from content.models import ArticlePage
        ArticlePage.objects.filter(pk=data['article']).update(cover_id=data['image'])
    data['front_letter'] = HeldLetter.objects.filter(batch=data['front_letters']).order_by('pk').first().pk
    data['back_letter'] = HeldLetter.objects.filter(batch=data['back_letters']).order_by('pk').first().pk
    from content.models import ArticlePage
    data['revision'] = ArticlePage.objects.get(pk=data['article']).get_latest_revision().pk
    data['unsubscribe'] = unsubscribe_token(member)
    done = User.objects.get(email='captain@screens.test')
    done.accepts_announcements = False
    done.save(update_fields=['accepts_announcements'])
    data['unsubscribe_done'] = unsubscribe_token(done)
    return data


# --- 起两边的服务 ------------------------------------------------------------------


def run(cmd, **kwargs):
    return subprocess.run(cmd, check=True, **kwargs)


def new_env(api_port: int) -> dict:
    return {
        **os.environ,
        "DATA_DIR": str(WORK / "new-data"),
        "MEDIA_DIR": str(WORK / "media"),
        "SITE_URL": TEST_SITE_URL,
        "SIGNING_KEY": TEST_SIGNING_KEY,
        "FIELD_ENCRYPTION_KEY": "parity-field-key-0123456789-abcdefghijk",
        "SJTUOW_HTTP_ADDR": f"127.0.0.1:{api_port}",
    }


def prepare_legacy(accounts=False, components=False) -> dict:
    if not (ROOT / "static/css/app.css").exists():
        screens.manage("tailwind", "build")
    screens.manage("migrate", "--noinput", stdout=subprocess.DEVNULL)
    screens.manage("createcachetable")
    screens.manage("init_site", "--verbosity", "0", stdout=subprocess.DEVNULL)
    seeded = subprocess.run(
        [sys.executable, __file__, "seed"] + (["--accounts"] if accounts else []) + (["--components"] if components else []),
        cwd=ROOT,
        env=screens.site_env(),
        check=False,
        capture_output=True,
        text=True,
    )
    if seeded.returncode:
        raise RuntimeError(seeded.stderr)
    return json.loads(seeded.stdout.strip().splitlines()[-1])


def prepare_new(env: dict) -> dict:
    binary = WORK / "sjtuow"
    run(["go", "build", "-o", str(binary), "./cmd/sjtuow"], cwd=ROOT / "server")
    (WORK / "new-data").mkdir(parents=True, exist_ok=True)
    run([str(binary), "migrate"], env=env, stdout=subprocess.DEVNULL)
    run([str(binary), "import", str(WORK / "db.sqlite3")], env=env, stdout=subprocess.DEVNULL)
    made = subprocess.run([str(binary), "import-media", str(WORK / "media")], env=env, capture_output=True, text=True)
    if made.returncode:
        raise RuntimeError("import-media failed: " + made.stderr)
    print(made.stdout.strip().splitlines()[0] if made.stdout.strip() else made.stderr.strip())
    run([str(binary), "import-fonts", str(WORK / "db.sqlite3"), str(WORK / "media")], env=env, stdout=subprocess.DEVNULL)
    sessions = {}
    for who, email in EMAILS.items():
        out = subprocess.run([str(binary), "session", email], env=env, check=True, capture_output=True, text=True)
        sessions[who] = out.stdout.strip()
    return sessions


def assets_dir() -> Path:
    assets = WORK / "assets"
    shutil.copytree(ROOT / "web/apps/site/dist/client", assets)
    shutil.copytree(ROOT / "web/apps/admin/dist", assets / "admin")
    shutil.copytree(ROOT / "static/img", assets / "img")
    (assets / "css").mkdir()
    shutil.copy(ROOT / "static/css/error.css", assets / "css/error.css")
    shutil.copy(ROOT / "web/packages/styles/dist/site.css", assets / "css/reader.css")
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


class RecordingDevTools(screens.DevTools):
    def __init__(self, url):
        self.browser_errors = []
        self.request_methods = {}
        self.request_urls = {}
        self.request_types = {}
        self.debug_http = 'http://' + urllib.parse.urlsplit(url).netloc
        self.submissions = []
        self.main_navigation_seen = False
        super().__init__(url)

    def _receive(self):
        message = super()._receive()
        method, params = message.get('method'), message.get('params', {})
        if method == 'Page.frameNavigated' and not params.get('frame', {}).get('parentId'):
            self.main_navigation_seen = True
        if method == 'Network.requestWillBeSent':
            self.request_methods[params['requestId']] = params['request']['method']
            self.request_urls[params['requestId']] = params['request']['url']
            self.request_types[params['requestId']] = params.get('type')
        elif method == 'Network.responseReceived':
            response = params.get('response', {})
            if self.request_methods.get(params['requestId']) == 'POST':
                self.submissions.append({'path': urllib.parse.urlsplit(response['url']).path, 'status': response['status']})
        elif method in ('Network.loadingFinished', 'Network.loadingFailed'):
            self.request_methods.pop(params['requestId'], None)
            self.request_urls.pop(params['requestId'], None)
            self.request_types.pop(params['requestId'], None)
        if method == 'Runtime.exceptionThrown':
            self.browser_errors.append('runtime: ' + params.get('exceptionDetails', {}).get('text', 'exception'))
        elif method == 'Runtime.consoleAPICalled' and any(a.get('value') == 'PARITY-CSP' for a in params.get('args', [])):
            self.browser_errors.append('CSP violation')
        elif method == 'Runtime.consoleAPICalled' and params.get('type') in ('error', 'assert'):
            self.browser_errors.append('console error: ' + ' '.join(str(a.get('value', a.get('description', ''))) for a in params.get('args', [])))
        elif method == 'Runtime.consoleAPICalled' and params.get('type') == 'warning':
            detail = ' '.join(str(a.get('value', a.get('description', ''))) for a in params.get('args', []))
            if 'hydration' in detail.lower():
                self.browser_errors.append('hydration warning: ' + detail)
        elif method == 'Network.responseReceived' and params.get('response', {}).get('status', 0) >= 500:
            self.browser_errors.append('HTTP 500+: ' + params['response']['url'])
        return message

    def settle_remote_frames(self):
        # Opaque-origin mail sandboxes move to an out-of-process iframe. Chrome
        # reports the request on this target but its completion on that target.
        # Verify the actual child document before retiring the parent record.
        documents = [(key, url) for key, url in self.request_urls.items() if self.request_types.get(key) == 'Document']
        if not documents:
            return
        targets = json.load(urllib.request.urlopen(self.debug_http + '/json', timeout=5))
        for key, url in documents:
            target = next((item for item in targets if item.get('type') == 'iframe' and item.get('url') == url and item.get('webSocketDebuggerUrl')), None)
            if not target:
                continue
            child = RecordingDevTools(target['webSocketDebuggerUrl'])
            try:
                child.send('Runtime.enable')
                ready = evaluate(child, "document.readyState === 'complete' && document.fonts.status === 'loaded' && [...document.images].every(image => image.complete)")
                if ready:
                    self.browser_errors.extend(child.browser_errors)
                    self.request_methods.pop(key, None)
                    self.request_urls.pop(key, None)
                    self.request_types.pop(key, None)
            finally:
                child.sock.close()


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
        if location:
            target = urllib.parse.urlsplit(urllib.parse.urljoin(url, location))
            origin = urllib.parse.urlsplit(url)
            if (target.scheme, target.netloc) == (origin.scheme, origin.netloc):
                location = urllib.parse.urlunsplit(('', '', target.path, target.query, target.fragment))
            else:
                location = target.geturl()
        return err.code, location


SNAPSHOT = """(() => {
  const main = document.querySelector('#main') || document.querySelector('main') || document.body;
  const text = main.innerText.split('\\n').map((l) => l.replace(/\\s+/g, ' ').trim()).filter(Boolean);
  const links = [...new Set([...main.querySelectorAll('a[href]')].map((a) => {
    const u = new URL(a.getAttribute('href'), location.href);
    return u.origin === location.origin ? u.pathname + u.search + u.hash : u.href;
  }))].sort();
  const fields = [...main.querySelectorAll('input,select,textarea,button')]
    .filter((el) => el.type !== 'hidden' && el.name !== 'csrfmiddlewaretoken' && el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden')
    .map((el) => `${el.tagName.toLowerCase()}:${el.tagName === 'BUTTON' ? 'action' : el.type || ''}:${el.name || ''}`).sort();
  const broken = [...document.images].filter((img) => img.complete && img.naturalWidth === 0).map((img) => img.getAttribute('src'));
  const box = main.getBoundingClientRect();
  const images = [...main.querySelectorAll('img')].filter(img => img.getClientRects().length).map(img => {
    const rect=img.getBoundingClientRect();
    return {alt:img.alt,x:rect.left-box.left,y:rect.top-box.top,width:rect.width,height:rect.height};
  });
  const samples = [...main.querySelectorAll('[data-sample],[data-real-image-sample],[data-default-image-sample]')].map(node => {
    const rect=node.getBoundingClientRect();
    return {x:rect.left-box.left,y:rect.top-box.top,width:rect.width,height:rect.height};
  });
  const frames = [...main.querySelectorAll('iframe')].filter(frame => frame.getClientRects().length).map(frame => {
    const rect=frame.getBoundingClientRect();
    return {src:new URL(frame.src,location.href).pathname,x:rect.left-box.left,y:rect.top-box.top,width:rect.width,height:rect.height};
  });
  const regions = [...main.querySelectorAll('[data-setup-list]')].map(node => {
    const rect=node.getBoundingClientRect();
    return {kind:'setup',x:rect.left-box.left,y:rect.top-box.top,width:rect.width,height:rect.height};
  });
  const shell = ['body','#app','.c-masthead','#main','.c-footer'].map(selector => {
    const node=document.querySelector(selector); if (!node) return {selector};
    const css=getComputedStyle(node),rect=node.getBoundingClientRect();
    return {selector,height:rect.height,top:rect.top,display:css.display,minHeight:css.minHeight,flex:css.flex,padding:css.padding,margin:css.margin,font:css.font,children:[...node.children].map(child=>({tag:child.tagName,class:child.className,height:child.getBoundingClientRect().height}))};
  });
  return { title: document.title, text, links, fields, broken, images, samples, frames, regions, shell,
           effective_status: Number((main.querySelector('[data-page-status]') || main).dataset.pageStatus || main.querySelector('.code')?.textContent || 200), path: location.pathname + location.search,
           box: { x: box.left + scrollX, y: box.top + scrollY, width: box.width, height: box.height } };
})()"""


def look(tools, url: str, cookie: dict | list[dict] | None, width: int, scheme: str, shot: Path, invalid=None, invalid_new=False) -> dict:
    tools.send("Network.clearBrowserCookies")
    for item in (cookie if isinstance(cookie, list) else [cookie] if cookie else []):
        tools.send("Network.setCookie", {**item, "domain": "127.0.0.1", "path": "/"})
    tools.send("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": width < 600})
    tools.send(
        "Emulation.setEmulatedMedia",
        {"features": [{"name": "prefers-color-scheme", "value": scheme}, {"name": "prefers-reduced-motion", "value": "reduce"}]},
    )
    tools.browser_errors.clear()
    # A cancelled request from a previous document is not pending work for the
    # next page. Keep tracking all requests generated by this navigation.
    tools.request_methods.clear()
    tools.request_urls.clear()
    tools.request_types.clear()
    tools.main_navigation_seen = False
    tools.send("Page.navigate", {"url": url})
    for _ in range(60):
        if evaluate(tools, "document.readyState") == "complete" and tools.main_navigation_seen:
            break
        time.sleep(0.1)
    # Do not change lazy-image attributes while Vue is still hydrating them.
    # readyState=complete can precede router.isReady()/mount for lazy routes.
    if evaluate(tools, "!!document.getElementById('ow-state')"):
        for _ in range(100):
            if evaluate(tools, "document.documentElement.classList.contains('js-ready')"):
                break
            time.sleep(0.1)
        else:
            raise RuntimeError('SSR page never hydrated: ' + url)
    evaluate(
        tools,
        """(() => { for (const item of document.querySelectorAll('img,iframe')) item.loading = 'eager';
          const step = Math.max(innerHeight, 1); const limit = document.documentElement.scrollHeight;
          for (let y = 0; y <= limit; y += step) scrollTo(0, y); scrollTo(0, 0); })()""",
    )
    for _ in range(40):
        if evaluate(tools, "[...document.images].filter((img) => !img.complete).length") == 0:
            break
        time.sleep(0.25)
    if urllib.parse.urlsplit(url).path.startswith('/admin/'):
        # Wait for session, lazy route and its page request; an empty shell is never a page.
        previous = None
        stable = 0
        for _ in range(120):
            current = evaluate(tools, "JSON.stringify({path:location.pathname,text:(document.querySelector('#main')??document.body)?.innerText??'',busy:!!document.querySelector('[aria-busy=true]')})")
            value = json.loads(current)
            if value['text'].strip() and not value['busy'] and value['text'] not in ('加载中…', '正在加载…'):
                stable = stable + 1 if current == previous else 0
                if stable >= 3:
                    break
            else:
                stable = 0
            previous = current
            time.sleep(0.1)
        else:
            raise RuntimeError('admin page never settled: ' + url)
    # Await actual network completion, including legacy fragments and lazy
    # specimen frames, instead of paying a fixed delay on every settled page.
    # Runtime RPCs also pump the CDP event queue; two idle observations ensure
    # late page/route requests cannot be mistaken for a completed document.
    idle = 0
    for _ in range(200):
        evaluate(tools, "document.readyState")
        tools.settle_remote_frames()
        idle = idle + 1 if not tools.request_methods else 0
        if idle >= 2: break
        time.sleep(0.05)
    else:
        raise RuntimeError('page requests never settled: ' + url + ' pending=' + repr(list(tools.request_urls.values())))
    # Font loading can outlive readyState/image completion, especially on long
    # Chinese pages. Capture the layout after its fonts and next paint frames.
    if evaluate(tools, "document.scripts.length === 0"):
        # CSP sandbox intentionally disables in-document script scheduling.
        # System-font mail documents can be polled synchronously; screenshots
        # force a compositor paint, without weakening the real mail sandbox.
        for _ in range(60):
            if evaluate(tools, "document.fonts.status") == 'loaded': break
            time.sleep(0.1)
        else: raise RuntimeError('mail fonts never loaded')
    else:
        evaluate(tools, "document.fonts.ready.then(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))")
    if invalid:
        from account_errors import submit
        submission = submit(tools, invalid, evaluate, invalid_new)
        stable = 0
        for _ in range(120):
            try:
                ready = evaluate(tools, "document.readyState==='complete'")
                stable = stable + 1 if ready else 0
                if stable >= 2: break
            except RuntimeError as failure:
                if 'navigated or closed' not in str(failure): raise
                stable = 0
            time.sleep(0.05)
        else:
            raise RuntimeError('submitted account document did not settle: ' + invalid)
        for _ in range(40):
            try:
                evaluate(tools, "document.fonts.ready.then(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))))")
                break
            except RuntimeError as failure:
                if 'navigated or closed' not in str(failure): raise
                time.sleep(0.05)
        else:
            raise RuntimeError('submitted account fonts did not settle: ' + invalid)
    if urllib.parse.urlsplit(url).path == '/_styleguide/':
        evaluate(tools, "document.querySelector('[aria-labelledby=sg-components]')?.remove()")
    if evaluate(tools, "document.querySelectorAll('iframe').length"):
        # Chromium does not paint offscreen out-of-process sandbox frames into
        # a beyond-viewport screenshot merely because their network is idle.
        # Visit every real frame and allow compositor paints before capture.
        evaluate(tools, """(async () => {
          const paint = () => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
          for (const frame of document.querySelectorAll('iframe')) {
            frame.scrollIntoView({block: 'center'}); await paint();
          }
          scrollTo(0, 0); await paint();
        })()""")
    snap = evaluate(tools, SNAPSHOT)
    if invalid:
        snap['submission'] = submission
    snap['browser_errors'] = list(tools.browser_errors)
    box = snap.pop("box")
    if box["width"] > 0 and box["height"] > 0:
        data = tools.send(
            "Page.captureScreenshot",
            {"format": "png", "captureBeyondViewport": True, "clip": {**box, "scale": 1}},
        )
        shot.write_bytes(base64.b64decode(data["data"]))
    return snap


def pixel_ratio(a: Path, b: Path, image_masks=None) -> tuple[float, str]:
    from PIL import Image, ImageChops, ImageDraw

    if not a.exists() or not b.exists():
        return 1.0, "缺截图"
    left, right = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    note = "" if left.size == right.size else f"尺寸 {left.size[0]}×{left.size[1]} / {right.size[0]}×{right.size[1]}"
    width, height = max(left.width, right.width), max(left.height, right.height)
    canvas = [Image.new("RGB", (width, height), (255, 0, 255)) for _ in range(2)]
    canvas[0].paste(left, (0, 0))
    canvas[1].paste(right, (0, 0))
    if image_masks:
        # The old image backend and new private WebP renderer intentionally
        # encode different bytes. Compare every image's presence and geometry,
        # then exclude only its compressed pixels from the page threshold.
        for target, masks in zip(canvas, image_masks):
            draw = ImageDraw.Draw(target)
            for item in masks:
                x, y = round(item['x']), round(item['y'])
                draw.rectangle((x, y, x + round(item['width']), y + round(item['height'])), fill=(127, 127, 127))
    # 每个像素取三个通道里差得最多的那个，超过 CHANNEL 算「不同」。
    red, green, blue = ImageChops.difference(*canvas).split()
    widest = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    changed = sum(widest.histogram()[CHANNEL + 1 :])
    return changed / (width * height), note


def component_pixel_ratio(a: Path, b: Path, old: dict, new: dict) -> tuple[float, str]:
    """Compare each specimen in its own aligned slot.

    A one-pixel height difference near the top of a 33k composite must not
    shift every later, otherwise identical, component. Section dimensions are
    still compared through the magenta padding in each aligned slot.
    """
    from PIL import Image, ImageChops, ImageDraw
    left, right = Image.open(a).convert('RGB'), Image.open(b).convert('RGB')
    for target, masks in ((left, old.get('images', [])), (right, new.get('images', []))):
        draw = ImageDraw.Draw(target)
        for item in masks:
            x, y = round(item['x']), round(item['y'])
            draw.rectangle((x, y, x + round(item['width']), y + round(item['height'])), fill=(127,127,127))
    old_samples, new_samples = old.get('samples', []), new.get('samples', [])
    if len(old_samples) != len(new_samples) or not old_samples:
        return 1.0, f'组件样本数量 {len(old_samples)} / {len(new_samples)}'
    ratios = []
    crops = []
    for index, (old_box, new_box) in enumerate(zip(old_samples,new_samples)):
        width=max(round(old_box['width']),round(new_box['width']))
        height=max(round(old_box['height']),round(new_box['height']))
        canvases=[Image.new('RGB',(width,height),(255,0,255)) for _ in range(2)]
        for source,box,canvas in ((left,old_box,canvases[0]),(right,new_box,canvases[1])):
            x,y,w,h=(round(box[key]) for key in ('x','y','width','height'))
            canvas.paste(source.crop((x,y,x+w,y+h)),(0,0))
        crops.append(canvases)
        red,green,blue=ImageChops.difference(*canvases).split()
        widest=ImageChops.lighter(ImageChops.lighter(red,green),blue)
        changed=sum(widest.histogram()[CHANNEL+1:])
        ratios.append((changed/(width*height),index))
    worst=max(ratios)
    failing=sorted((item for item in ratios if item[0]>RATIO_MAX),reverse=True)[:8]
    for _ratio,index in failing:
        crops[index][0].save(a.with_name(a.stem+f'-sample-{index}.png'))
        crops[index][1].save(b.with_name(b.stem+f'-sample-{index}.png'))
    note='组件差异样本 ' + ', '.join(f'{index}:{ratio:.2%}' for ratio,index in failing) if failing else ''
    return worst[0], note


def prefix_pixel_ratio(a: Path, b: Path, old_height: float, new_height: float) -> tuple[float, str]:
    from PIL import Image
    left, right = Image.open(a).convert('RGB'), Image.open(b).convert('RGB')
    left = left.crop((0,0,left.width,max(1,round(old_height))))
    right = right.crop((0,0,right.width,max(1,round(new_height))))
    scratch = OUT / '.prefix-old.png', OUT / '.prefix-new.png'
    left.save(scratch[0]); right.save(scratch[1])
    try: return pixel_ratio(*scratch)
    finally:
        for path in scratch: path.unlink(missing_ok=True)


# --- 主流程 -------------------------------------------------------------------------


def compare(old: dict, new: dict, ratio: float, status: tuple) -> list[str]:
    problems = []
    if any(code >= 500 for code in status):
        problems.append(f"服务器错误 {status}")
    if status[0] != status[1]:
        problems.append(f"状态 {status[0]} / {status[1]}")
    if old["title"] != new["title"]:
        problems.append(f"标题「{old['title']}」/「{new['title']}」")
    if old["text"] != new["text"]:
        diff = [line for line in list(difflib.unified_diff(old["text"], new["text"], lineterm="", n=0))[2:] if line[:1] in "+-"]
        problems.append("正文不同：" + "；".join(diff[:6]) + ("…" if len(diff) > 6 else ""))
    if old["links"] != new["links"]:
        gone = sorted(set(old["links"]) - set(new["links"]))
        extra = sorted(set(new["links"]) - set(old["links"]))
        problems.append(f"链接 少 {gone[:5]} 多 {extra[:5]}")
    if old["fields"] != new["fields"]:
        problems.append(f"表单 {old['fields']} / {new['fields']}")
    if new["broken"]:
        problems.append(f"新站坏图 {new['broken'][:3]}")
    for label, value in (('旧站', old), ('新站', new)):
        if value.get('browser_errors'):
            problems.append(label + '浏览器异常：' + str(value['browser_errors']))
    if ratio > RATIO_MAX:
        problems.append(f"像素差 {ratio:.2%}")
    return problems


def canonical_location(location):
    target = urllib.parse.urlsplit(location)
    return (target.scheme.lower(), target.netloc.lower(), target.path,
            urllib.parse.parse_qsl(target.query, keep_blank_values=True), target.fragment)


def resource_response(url, cookie):
    request = urllib.request.Request(url, headers={"Cookie": cookie} if cookie else {})
    try:
        response = urllib.request.urlopen(request, timeout=20)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        payload = response.read()
        kind = response.headers.get('Content-Type', '').lower()
        # Same fictional SITE_URL, distinct ephemeral ports. Replace only the
        # concrete server origin, never paths, fields or resource content.
        if 'text/' in kind or 'xml' in kind:
            origin = urllib.parse.urlsplit(url)
            payload = payload.replace(f'{origin.scheme}://{origin.netloc}'.encode(), TEST_SITE_URL.encode())
        if urllib.parse.urlsplit(url).path == '/sitemap.xml' and response.status == 200:
            # XML declaration spelling and template indentation are not sitemap
            # semantics. Compare every expanded tag, attribute, value and order.
            import xml.etree.ElementTree as ET
            def node(element):
                return (element.tag, sorted(element.attrib.items()), (element.text or '').strip(),
                        [(node(child), (child.tail or '').strip()) for child in element])
            payload = node(ET.fromstring(payload))
        return response.status, kind, payload


def redirect_problems(status):
    old, new = status
    if old[0] != new[0] or canonical_location(old[1]) != canonical_location(new[1]):
        return [f"状态/跳转 {old} / {new}"]
    return []


def approved_redirect(name, who, status):
    # Explicit decision in frontend-migration 10, item 5 (266), implemented
    # in 268. Only this exact authenticated entrance difference is allowed.
    if name == 'password-set' and who != 'visitor' and status == ((302, '/accounts/password/change/'), (301, '/me/security/')):
        return 'docs/frontend-migration.md §10 #5（266）：未使用的设密码入口301回账号安全'
    return None


def main(argv: list[str]) -> int:
    # Calendar addresses must be signed under identical fictional configuration
    # on both sides; comparing different host names or keys is not page parity.
    os.environ["SITE_URL"] = TEST_SITE_URL
    os.environ["DJANGO_SECRET_KEY"] = TEST_SIGNING_KEY
    only = next((a.split("=", 1)[1].split(",") for a in argv if a.startswith("--only=")), None)
    wide = "--wide" in argv
    strict = "--strict" in argv
    errors = "--account-errors" in argv
    components = "--components" in argv
    accounts = "--accounts" in argv or errors
    if accounts:
        from account_scenarios import PAGES as account_pages, EXTRA_EMAILS
        EMAILS.update(EXTRA_EMAILS)
        if errors:
            from account_errors import PAGES as account_pages
    if components:
        account_pages = [("component-specimen", "officer", "/_styleguide/components/")]
    negative_probe(compare)
    print("PARITY-MATRIX-NEGATIVE-PROBES-OK", flush=True)
    pages = [p for p in (account_pages if accounts or components else PAGES) if not only or any(
        prefix and (p[0].startswith(prefix) or p[2].startswith(prefix)) for prefix in only
    )]
    if not pages:
        print("PARITY-ERROR: --only 没有匹配任何页面，不能算通过", file=sys.stderr)
        return 2
    if WORK.exists():
        WORK.rename(WORK.with_name('sjtu-ow-parity-prev-' + str(time.time_ns())))
    SHOTS.mkdir(parents=True)

    print("== 旧站：迁移、种子数据")
    data = prepare_legacy(accounts, components)
    ports = [screens.free_port() for _ in range(5)]
    old_port, api_port, ssr_port, caddy_port, debug_port = ports
    reference = None
    env = new_env(api_port)
    os.environ["PARITY_API_BASE"] = f"http://127.0.0.1:{api_port}"
    print("== 新站：迁移、导入、图片母版、会话")
    new_sessions = prepare_new(env)
    from account_scenarios import validate_import
    validate_import(WORK)
    from admin_scenarios import validate_import as validate_admin_import
    validate_admin_import(WORK, data)

    procs = []
    # DEBUG's technical404 is not the production oracle. Render the frozen
    # standalone templates, while keeping the real old endpoint status gate.
    os.environ.update(screens.site_env())
    import django
    django.setup()
    from django.template.loader import render_to_string
    error_documents = {code: render_to_string(f'errors/{code}.html').encode() for code in (403,404,429)}
    from datetime import datetime, date, timezone as datetime_timezone
    from unittest.mock import patch
    from django.test import override_settings
    from core.email_samples import samples as legacy_mail_samples
    with override_settings(SITE_URL='https://example.invalid'), patch('django.utils.timezone.localdate', return_value=date(2026, 10, 3)), patch('django.utils.timezone.now', return_value=datetime(2026, 10, 3, 6, 20, tzinfo=datetime_timezone.utc)):
        mail_samples = legacy_mail_samples()
        mail_list = render_to_string('core/styleguide_emails.html', {'samples': mail_samples})
    from core.email_art import for_browser
    mail_documents = {sample.key: for_browser(sample.html).encode() for sample in mail_samples}
    component_payload = b''
    if components:
        from component_reference import document
        component_payload = document(ROOT, f'http://127.0.0.1:{old_port}', data).encode()
    class Reference(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if urllib.parse.urlsplit(self.path).path.startswith('/__error/'):
                code=int(self.path.split('/')[2])
                self.send_response(code)
                self.send_header('Content-Type','text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(error_documents[code])
                return
            if components and urllib.parse.urlsplit(self.path).path == '/_styleguide/components/':
                self.send_response(200)
                self.send_header('Content-Type','text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(component_payload)
                return
            path = urllib.parse.urlsplit(self.path).path
            # Access was checked against the real legacy endpoint before the
            # visual oracle is selected. Only dates/site root are fixed input.
            if path == '/_styleguide/emails/':
                self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.end_headers()
                self.wfile.write(mail_list.encode()); return
            if path.startswith('/_styleguide/emails/') and path.strip('/').split('/')[-1] in mail_documents:
                self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.end_headers()
                self.wfile.write(mail_documents[path.strip('/').split('/')[-1]]); return
            try:
                upstream=urllib.request.urlopen(f'http://127.0.0.1:{old_port}'+self.path,timeout=20)
            except urllib.error.HTTPError as error:
                upstream=error
            with upstream:
                self.send_response(upstream.status)
                self.send_header('Content-Type',upstream.headers.get('Content-Type','application/octet-stream'))
                self.end_headers()
                self.wfile.write(upstream.read())
        def log_message(self,*args): pass
    reference=http.server.ThreadingHTTPServer(('127.0.0.1',0),Reference)
    threading.Thread(target=reference.serve_forever,daemon=True).start()
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
        tools = RecordingDevTools(next(t for t in targets if t.get("type") == "page")["webSocketDebuggerUrl"])
        tools.send("Page.enable")
        tools.send("Network.enable")
        tools.send("Runtime.enable")
        tools.send("Page.addScriptToEvaluateOnNewDocument", {'source': "document.addEventListener('securitypolicyviolation',()=>console.error('PARITY-CSP'))"})
        evaluate(tools, "new Promise(resolve=>{setTimeout(()=>{throw new Error('PARITY-NEGATIVE-PROBE')},0);setTimeout(()=>resolve(true),40)})")
        if not any(e.startswith('runtime:') for e in tools.browser_errors):
            raise RuntimeError('browser runtime guard did not observe its negative probe')
        probe = look(tools, f'http://127.0.0.1:{caddy_port}/accounts/login/', None, 1280, 'light', SHOTS / 'csp-probe-before.png')
        if probe['browser_errors']:
            raise RuntimeError('login before CSP probe had browser errors: ' + str(probe['browser_errors']))
        evaluate(tools, "new Promise(resolve=>{const script=document.createElement('script');script.textContent='window.__parity_bad_inline=true';document.head.append(script);setTimeout(()=>resolve(true),50)})")
        if 'CSP violation' not in tools.browser_errors or evaluate(tools, 'window.__parity_bad_inline===true'):
            raise RuntimeError('browser CSP guard did not observe a blocked inline script')
        print('PARITY-BROWSER-ERROR-PROBES-OK runtime/CSP (intentional, before page comparisons)', flush=True)

        views = [(1280, "light")] + ([(375, "light"), (1280, "dark"), (375, "dark")] if wide else [])
        results = []
        for name, who, template in pages:
            # 中文查询参数要编码成百分号形式，urllib 只收 ASCII（浏览器里也是这样发的）
            path = urllib.parse.quote(template.format(**data), safe="/?=&#%")
            old_cookie = [{"name": "sessionid", "value": data["sessions"][who]}] if who in data["sessions"] else []
            new_cookie = [{"name": "ow_session", "value": new_sessions[who]}] if who in new_sessions else []
            if accounts and not errors:
                from account_scenarios import context
                old_cookie, new_cookie, suffix = context(name, who, data, new_sessions, WORK, screens.site_env())
                path += suffix
            if errors:
                from account_errors import context as error_context
                old_cookie, new_cookie, suffix = error_context(name, data, new_sessions, WORK, screens.site_env())
                path = template + suffix
            if name.startswith('unsubscribe-'):
                # Visual specimens repeat a GET five times per role. Each role
                # starts a fresh visual quota; real saturation is tested separately.
                with sqlite3.connect(WORK / 'new-data/sjtuow.sqlite3') as db:
                    db.execute("DELETE FROM rate_counters WHERE bucket LIKE 'unsubscribe|%'")
            cookies = lambda items: "; ".join(c["name"] + "=" + c["value"] for c in items)
            old_url = f"http://127.0.0.1:{reference.server_address[1] if components else old_port}{path}"
            status = (
                fetch_status(old_url, cookies(old_cookie)),
                fetch_status(f"http://127.0.0.1:{caddy_port}{path}", cookies(new_cookie)),
            )
            if path.startswith('/_styleguide/emails/') and status[0][0] == 200:
                old_url = f'http://127.0.0.1:{reference.server_address[1]}{path}'
            if status[0][0] in (403,404,429) and not name.startswith('unsubscribe-'):
                old_url=f'http://127.0.0.1:{reference.server_address[1]}/__error/{status[0][0]}/'
            row = {"name": name, "who": who, "path": path, "status": status, "views": []}
            if name == 'admin-prerender-redirect':
                # 266 explicitly retired this entrance. Verify the real HTTP
                # 301 and the destination's existing gate for every identity.
                problems = []
                if status[1] != (301, '/admin/settings/'):
                    problems.append(f'预渲染入口未真正301到设置：{status[1]}')
                gate = fetch_status(f'http://127.0.0.1:{old_port}/admin/settings/site/', cookies(old_cookie))
                for width, scheme in views:
                    new = look(tools, f'http://127.0.0.1:{caddy_port}{path}', new_cookie, width, scheme, SHOTS / f'{name}-{who}-{width}-{scheme}-new.png')
                    failures = list(problems) + list(new['browser_errors'])
                    if 300 <= gate[0] < 400:
                        expected = '/accounts/login/?' + urllib.parse.urlencode({'next': '/admin/settings/'})
                        if canonical_location(new['path']) != canonical_location(expected):
                            failures.append('设置入口登录去向错误')
                    elif new['effective_status'] != gate[0]:
                        failures.append(f'设置入口权限 {new["effective_status"]} / {gate[0]}')
                    elif gate[0] == 200 and ('全站设置' not in new['title'] or not new['fields'] or new['broken']):
                        failures.append('设置入口内容不完整')
                    row['views'].append({'view': f'{width}-{scheme}', 'ratio': None, 'problems': failures})
                row['approved_difference'] = 'frontend-migration.md §10 #5（266）：预渲染入口301到设置'
                row['pass'] = all(not view['problems'] for view in row['views'])
                results.append(row)
                (OUT / 'progress.json').write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding='utf-8')
                print(('通过' if row['pass'] else '不同') + f' approved-redirect {who} {path}', flush=True)
                continue
            if name == 'admin-font-download' and status[0][0] == 200:
                try:
                    from font_download import check as check_font_download
                    approval = check_font_download(f'http://127.0.0.1:{old_port}{path}', f'http://127.0.0.1:{api_port}', cookies(old_cookie), cookies(new_cookie), data['font_face'], env, WORK)
                    row['approved_difference'] = approval
                    problems = []
                except Exception as failure:
                    problems = [f'D4 字体下载验收失败：{failure}']
                row['views'] = [{'view': 'real-download-roundtrip', 'ratio': 0, 'problems': problems}]
                row['pass'] = not problems
                results.append(row)
                (OUT / "progress.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
                print(('通过' if row['pass'] else '不同') + ' D4 download ' + who + ' ' + path + ('；'.join(problems) if problems else ''), flush=True)
                continue
            if name in {item[0] for item in RESOURCES}:
                left = resource_response(f'http://127.0.0.1:{old_port}{path}', cookies(old_cookie))
                right = resource_response(f'http://127.0.0.1:{caddy_port}{path}', cookies(new_cookie))
                problems = []
                if left != right:
                    problems = ['资源状态/类型/正文不同（已跟随图标跳转）']
                row['views'] = [{'view': 'resource', 'ratio': 0, 'problems': problems}]
                row['pass'] = not problems
                results.append(row)
                (OUT / "progress.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
                print(('通过' if row['pass'] else '不同') + ' resource ' + path, flush=True)
                continue
            from page_matrix import APPROVED_ADDITIONS
            additions = APPROVED_ADDITIONS
            if name in additions:
                # 295 user-approved additions have no frozen visual counterpart.
                # Keep every identity/viewport; compare their gate with the old
                # article editor or admin entrance, and inspect the actual page.
                title, gate_template = additions[name]
                gate_path = gate_template.format(**data)
                gate = fetch_status(f'http://127.0.0.1:{old_port}{gate_path}', cookies(old_cookie))
                # The new private revision resource hides inaccessible objects
                # with 404 (frontend-migration I2); old editor access determines
                # the allowed identities, not a nonexistent revision's status.
                expected_status = 404 if name.startswith('admin-article-revision') and gate[0] == 403 else gate[0]
                row['approved_difference'] = 'design-next.md §7.7：295用户批准新增修订/后台邮件样张页面'
                for width, scheme in views:
                    new = look(tools, f'http://127.0.0.1:{caddy_port}{path}', new_cookie, width, scheme, SHOTS / f'{name}-{who}-{width}-{scheme}-new.png')
                    problems = list(new['browser_errors'])
                    if 300 <= gate[0] < 400:
                        expected = '/accounts/login/?' + urllib.parse.urlencode({'next': path})
                        if canonical_location(new['path']) != canonical_location(expected):
                            problems.append('新增页未转到带原地址的登录页')
                    elif new['effective_status'] != expected_status:
                        problems.append(f'新增页权限结果 {new["effective_status"]} / {expected_status}')
                    elif expected_status == 200:
                        if title not in new['title'] or not new['text'] or new['broken']:
                            problems.append('新增页标题/内容/图片不完整')
                        if 'revisions' in path and not any('/admin/articles/' in link for link in new['links']):
                            problems.append('修订页缺少实际文章/修订链接')
                        if name == 'admin-mail-samples' and not any('/admin/settings/email-samples/' in link for link in new['links']):
                            problems.append('样张列表缺少单封入口')
                    row['views'].append({'view': f'{width}-{scheme}', 'ratio': None, 'problems': problems})
                row['pass'] = all(not view['problems'] for view in row['views'])
                results.append(row)
                (OUT / 'progress.json').write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding='utf-8')
                print(('通过' if row['pass'] else '不同') + f' approved-addition {who} {path}', flush=True)
                continue
            admin_shell = path.startswith('/admin/') and status[1][0] == 200
            expected_old_status = status[0][0]
            if name in ('admin-article', 'admin-article-preview') and status[0][0] == 403:
                expected_old_status = 404
                old_url = f'http://127.0.0.1:{reference.server_address[1]}/__error/404/'
                row['approved_difference'] = 'design-next.md §7.8：295用户批准私有文章无权访问隐藏为404'
            # The approved independent SPA sends its static shell before its
            # real Go gate. Compare the settled result, not a misleading 200.
            if admin_shell and 300 <= status[0][0] < 400:
                new = look(tools, f'http://127.0.0.1:{caddy_port}{path}', new_cookie, 1280, 'light', SHOTS / f'{name}-{who}-gate.png')
                actual = new['path']
                if canonical_location(actual) != canonical_location(status[0][1]):
                    problems = [f'SPA登录跳转 {actual} / {status[0][1]}']
                else:
                    problems = list(new['browser_errors'])
                row['approved_difference'] = '12-architecture.md §6.8：静态SPA shell后经真实接口决定登录去向'
                row['views'] = [{'view': 'spa-redirect', 'ratio': 0, 'problems': problems}]
            if 300 <= status[0][0] < 400 or 300 <= status[1][0] < 400:
                allowed = approved_redirect(name, who, status) if not errors else None
                if allowed:
                    row['approved_difference'] = allowed
                problems = ['错误态夹具未进入可提交表单'] if errors else ([] if allowed else redirect_problems(status))
                if not row['views']:
                    row["views"] = [{"view": "redirect", "ratio": 0, "problems": problems}]
            for width, scheme in ([] if row["views"] else views):
                stem = f"{name}-{who}-{width}-{scheme}"
                if errors:
                    from account_errors import context as error_context
                    old_cookie, new_cookie, suffix = error_context(name, data, new_sessions, WORK, screens.site_env())
                    path = template + suffix
                try:
                    old = look(tools, old_url, old_cookie, width, scheme, SHOTS / f"{stem}-old.png", name if errors else None, False)
                    if errors and (name.endswith('-limit') or name == 'error-resend-cooldown'):
                        submission = old['submission']
                        old = look(tools, f'http://127.0.0.1:{reference.server_address[1]}/__error/429/', None, width, scheme, SHOTS / f"{stem}-old.png")
                        old['submission'] = submission
                    new = look(tools, f"http://127.0.0.1:{caddy_port}{path}", new_cookie, width, scheme, SHOTS / f"{stem}-new.png", name if errors else None, True)
                except Exception as failure:
                    row["views"].append({"view": f"{width}-{scheme}", "ratio": 1, "problems": [f"页面采集失败：{failure}"]})
                    continue
                approved_home = name == 'admin-home' and who == 'officer' and old.get('regions') and new.get('regions')
                if components:
                    ratio, note = component_pixel_ratio(SHOTS / f"{stem}-old.png", SHOTS / f"{stem}-new.png", old, new)
                elif approved_home:
                    ratio, note = prefix_pixel_ratio(SHOTS / f"{stem}-old.png", SHOTS / f"{stem}-new.png", old['regions'][0]['y'], new['regions'][0]['y'])
                else:
                    masks = (old.get('frames', []), new.get('frames', [])) if name == 'email-samples' else None
                    ratio, note = pixel_ratio(SHOTS / f"{stem}-old.png", SHOTS / f"{stem}-new.png", masks)
                effective = new['effective_status'] if admin_shell else status[1][0]
                compared_old = old
                if approved_home:
                    compared_old = {**old, 'text': [line.replace('5 项建议做','4 项建议做').replace('建议做的 5 项','建议做的 4 项') for line in old['text'] if '异地备份' not in line]}
                    row['approved_difference'] = '296 用户决定不考虑异地备份：上线清单不再显示 R2 项'
                problems = compare(compared_old, new, ratio, (expected_old_status, effective) if (width, scheme) == views[0] else (0, 0))
                if components:
                    layout = lambda page: [(image['alt'], round(image['x']), round(image['y']), round(image['width']), round(image['height'])) for image in page.get('images', [])]
                    if layout(old) != layout(new):
                        problems.append('组件图片数量、替代文字或显示几何不同')
                if name == 'email-samples':
                    frame_layout = lambda page: [(frame['src'],round(frame['x']),round(frame['y']),round(frame['width']),round(frame['height'])) for frame in page.get('frames', [])]
                    if frame_layout(old) != frame_layout(new):
                        problems.append('邮件样张框数量、地址或显示几何不同')
                if admin_shell:
                    if new['effective_status'] != expected_old_status:
                        problems.append(f'SPA权限结果 {new["effective_status"]} / {expected_old_status}')
                if note:
                    problems.append(note)
                view = {"view": f"{width}-{scheme}", "ratio": ratio, "problems": problems}
                if problems:
                    view['shell'] = {'old': old.get('shell'), 'new': new.get('shell')}
                if errors:
                    view['submissions'] = {'old': old['submission'], 'new': new['submission']}
                row["views"].append(view)
            row["pass"] = all(not v["problems"] for v in row["views"])
            results.append(row)
            (OUT / "progress.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
            mark = "通过" if row["pass"] else "不同"
            print(f"{mark}  {who:8} {path}" + ("" if row["pass"] else "  ← " + "；".join(row["views"][0]["problems"])[:240]), flush=True)
    finally:
        if reference:
            reference.shutdown(); reference.server_close()
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
        if r.get('approved_difference'):
            problems = '已批准差异：' + r['approved_difference'] + ('；' + problems if problems else '')
        lines.append(f"| {'通过' if r['pass'] else '不同'} | {r['who']} | `{r['path']}` | {r['status'][0][0]} / {r['status'][1][0]} | {problems[:400]} |")
    (OUT / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nPARITY {passed}/{len(results)} 通过；报告 {OUT / 'report.md'}，截图 {SHOTS}")
    return 1 if strict and passed != len(results) else 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    if sys.argv[1:2] == ["seed"]:
        import django

        django.setup()
        print(json.dumps(seed("--accounts" in sys.argv)))
    else:
        sys.exit(main(sys.argv[1:]))
