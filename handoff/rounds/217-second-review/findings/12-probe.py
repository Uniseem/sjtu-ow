"""Round 217 review, block 12 (front end): reproduce a few findings in a real
headless Chromium on a throwaway site seeded by scripts/screens.py.

  A  autosave after a re-login elsewhere: the page keeps the form's old CSRF
     token, so every save is a 403 「登录状态已失效」 even though the visitor
     is signed in again; a fetch with the cookie's token saves fine. After
     that permanent failure, leaving the page is not guarded.
  B  a lost answer to an article save that made a new revision: the retry
     carries the old latest_revision, the server says 「另一个人…改过」, and
     every later save of this page is refused the same way.
  C  aria-describedby written by Django points at ids no template renders.
  D  phone width (375): pages wider than the screen.

  bash scripts/remote-check.sh run uv run python \\
    handoff/rounds/217-second-review/findings/12-probe.py

Prints what it saw; the exit code is always 0 (it records, it does not judge).
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import socket
import struct
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
import screens  # noqa: E402

screens.WORK = Path("/tmp/sjtu-ow-217-12-probe")
WORK = screens.WORK


class Tools(screens.DevTools):
    """screens.DevTools, but events are kept instead of dropped."""

    def __init__(self, url):
        super().__init__(url)
        self.events = []

    def send(self, method, params=None):
        self.next_id += 1
        payload = json.dumps(
            {"id": self.next_id, "method": method, "params": params or {}}
        ).encode()
        header = bytearray([0x81])
        n = len(payload)
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header.append(0x80 | 126)
            header += struct.pack(">H", n)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", n)
        mask = os.urandom(4)
        header += mask
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(bytes(header) + masked)
        while True:
            message = self._receive()
            if message.get("id") == self.next_id:
                if "error" in message:
                    raise RuntimeError(message["error"])
                return message.get("result", {})
            if "method" in message:
                self.events.append(message)


def evaluate(tools, expression, wait=False):
    result = tools.send(
        "Runtime.evaluate",
        {"expression": expression, "returnByValue": True, "awaitPromise": wait},
    )
    return result.get("result", {}).get("value")


def shell(code: str) -> str:
    done = screens.manage("shell", "-c", code, capture_output=True, text=True)
    return done.stdout.strip().splitlines()[-1] if done.stdout.strip() else ""


def main():
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)
    if not (ROOT / "static/css/app.css").exists():
        screens.manage("tailwind", "build")
    screens.manage("migrate", "--noinput", stdout=subprocess.DEVNULL)
    screens.manage("createcachetable")
    screens.manage("init_site", "--verbosity", "0", stdout=subprocess.DEVNULL)
    seeded = subprocess.run(
        [sys.executable, str(ROOT / "scripts/screens.py"), "seed"],
        cwd=ROOT,
        env=screens.site_env(),
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(seeded.stdout.strip().splitlines()[-1])

    port, debug = screens.free_port(), screens.free_port()
    base = f"http://127.0.0.1:{port}"
    server = subprocess.Popen(
        [sys.executable, "manage.py", "runserver", f"127.0.0.1:{port}", "--noreload"],
        cwd=ROOT,
        env=screens.site_env(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    browser = subprocess.Popen(
        [
            "chromium",
            "--headless=new",
            "--no-sandbox",
            "--hide-scrollbars",
            f"--remote-debugging-port={debug}",
            f"--user-data-dir={WORK / 'chromium-profile'}",
            "--window-size=1280,900",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        screens.wait_for(f"{base}/robots.txt")
        screens.wait_for(f"http://127.0.0.1:{debug}/json/version")
        targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{debug}/json"))
        page = next(t for t in targets if t.get("type") == "page")
        tools = Tools(page["webSocketDebuggerUrl"])
        tools.send("Page.enable")
        tools.send("Network.enable")
        tools.send("Network.setCacheDisabled", {"cacheDisabled": True})

        def sign_in(who=None, session=None):
            tools.send("Network.clearBrowserCookies")
            if who or session:
                tools.send(
                    "Network.setCookie",
                    {
                        "name": "sessionid",
                        "value": session or data["sessions"][who],
                        "domain": "127.0.0.1",
                        "path": "/",
                    },
                )

        def go(path, settle=2.5):
            tools.send("Page.navigate", {"url": base + path})
            time.sleep(settle)

        status_js = (
            "(function(){var s=document.querySelector('form[data-autosave] "
            "[data-autosave-status]');return s?s.textContent:'(无状态栏)';})()"
        )
        leave_js = (
            "(function(){var e=new Event('beforeunload',{cancelable:true});"
            "window.dispatchEvent(e);return e.defaultPrevented;})()"
        )

        # --- A: re-login elsewhere, then edit ---------------------------------
        print("== A 在别处重新登录以后，本页的自动保存 ==")
        sign_in("member")
        go("/me/")
        type_js = (
            "(function(v){var f=document.querySelector('form[data-autosave]');"
            "var t=f.querySelector('input[name=nickname]');t.value=v;"
            "t.dispatchEvent(new Event('input',{bubbles:true}));return t.value;})"
        )
        evaluate(tools, type_js + "('截图队员A')")
        time.sleep(3)
        print("基线（没换 Cookie）：状态栏 =", evaluate(tools, status_js))
        print(
            "基线：库里的昵称 =",
            shell(
                "from accounts.models import User;"
                "print(User.objects.get(email='member@screens.test').nickname)"
            ),
        )
        # Signing in again (another tab) gives a new session and, through
        # django.contrib.auth.login -> rotate_token, a new CSRF secret.
        fresh = shell(
            "from django.test import Client; from accounts.models import User;"
            "c=Client(); c.force_login(User.objects.get(email='member@screens.test'));"
            "print(c.cookies['sessionid'].value)"
        )
        sign_in(session=fresh)
        tools.send(
            "Network.setCookie",
            {
                "name": "csrftoken",
                "value": secrets.token_hex(16),
                "domain": "127.0.0.1",
                "path": "/",
            },
        )
        evaluate(tools, type_js + "('截图队员B')")
        time.sleep(3)
        print("换成新会话和新 CSRF Cookie 以后：状态栏 =", evaluate(tools, status_js))
        evaluate(tools, type_js + "('截图队员C')")
        time.sleep(3)
        print("再改一次：状态栏 =", evaluate(tools, status_js))
        print("这时离开页面会不会被拦（beforeunload 被 preventDefault）=", evaluate(tools, leave_js))
        print(
            "库里的昵称 =",
            shell(
                "from accounts.models import User;"
                "print(User.objects.get(email='member@screens.test').nickname)"
            ),
        )
        control = evaluate(
            tools,
            "(function(){var f=document.querySelector('form[data-autosave]');"
            "var m=document.cookie.match(/csrftoken=([^;]+)/);"
            "return fetch(f.getAttribute('action')||location.href,{method:'POST',"
            "body:new FormData(f),credentials:'same-origin',headers:{'X-Autosave':'1',"
            "'X-CSRFToken':m[1],Accept:'application/json'}}).then(function(r){"
            "return r.status+' '+r.headers.get('Content-Type');});})()",
            wait=True,
        )
        print("对照：同一张表单、用 Cookie 里的令牌发 =", control)
        print(
            "对照以后库里的昵称 =",
            shell(
                "from accounts.models import User;"
                "print(User.objects.get(email='member@screens.test').nickname)"
            ),
        )

        # --- B: lost answer on an article save ------------------------------
        print("\n== B 文章保存的回答丢了一次 ==")
        sign_in("officer")
        article = data["article"]
        go(f"/admin/articles/{article}/", settle=4)
        before = evaluate(
            tools, "document.querySelector('input[name=latest_revision]').value"
        )
        print("打开时表单里的 latest_revision =", before)
        tools.send(
            "Fetch.enable",
            {"patterns": [{"urlPattern": "*/admin/articles/*", "requestStage": "Response"}]},
        )
        title_js = (
            "(function(v){var t=document.querySelector('form[data-autosave] "
            "input[name=title]');t.value=t.value+v;"
            "t.dispatchEvent(new Event('input',{bubbles:true}));return t.value;})"
        )
        evaluate(tools, title_js + "('甲')")
        dropped = False
        started = time.monotonic()
        while time.monotonic() - started < 12:
            evaluate(tools, "1")
            pending, tools.events = tools.events, []
            for event in pending:
                if event.get("method") != "Fetch.requestPaused":
                    continue
                params = event["params"]
                if params["request"]["method"] == "POST" and not dropped:
                    dropped = True
                    print(
                        "拦下第一次自动保存的回答（服务器已回",
                        params.get("responseStatusCode"),
                        "），让浏览器当成连接断了",
                    )
                    tools.send(
                        "Fetch.failRequest",
                        {"requestId": params["requestId"], "errorReason": "ConnectionReset"},
                    )
                    tools.send("Fetch.disable")
                else:
                    tools.send("Fetch.continueRequest", {"requestId": params["requestId"]})
            time.sleep(0.3)
        print("重试以后：状态栏 =", evaluate(tools, status_js))
        print(
            "表单里的 latest_revision =",
            evaluate(tools, "document.querySelector('input[name=latest_revision]').value"),
        )
        evaluate(tools, title_js + "('乙')")
        time.sleep(3)
        print("再改一次：状态栏 =", evaluate(tools, status_js))
        print("这时离开页面会不会被拦 =", evaluate(tools, leave_js))
        print(
            "库里最新修订：",
            shell(
                "from content.models import ArticlePage;"
                f"p=ArticlePage.objects.get(pk={article});r=p.latest_revision;"
                "print(r.pk, r.user.nickname, r.content.get('title'))"
            ),
        )

        # --- C: aria-describedby ------------------------------------------------
        print("\n== C aria-describedby 指向的 id 在不在页面上 ==")
        dangling_js = (
            "JSON.stringify(Array.prototype.map.call("
            "document.querySelectorAll('[aria-describedby]'),function(el){"
            "var ids=el.getAttribute('aria-describedby').split(/\\s+/).filter(Boolean);"
            "return [el.name||el.id,ids.filter(function(i){return !document.getElementById(i);})];"
            "}).filter(function(x){return x[1].length;}))"
        )
        for who, path in (
            ("member", "/me/"),
            ("member", "/me/contacts/?new=1"),
            ("officer", "/admin/settings/site/"),
            ("officer", f"/admin/articles/{article}/"),
        ):
            sign_in(who)
            go(path)
            found = json.loads(evaluate(tools, dangling_js) or "[]")
            print(f"{path}：{len(found)} 个控件的 aria-describedby 指向不存在的 id", found[:4])

        # --- D: phone width -------------------------------------------------------
        print("\n== D 375 宽时比屏幕宽的页面 ==")
        tools.send(
            "Emulation.setDeviceMetricsOverride",
            {"width": 375, "height": 812, "deviceScaleFactor": 1, "mobile": True},
        )
        overflow_js = (
            "(function(){var d=document.documentElement,w=d.clientWidth,out=[];"
            "if(d.scrollWidth<=w){return JSON.stringify({sw:d.scrollWidth,w:w,out:out});}"
            "Array.prototype.forEach.call(document.querySelectorAll('body *'),function(el){"
            "var r=el.getBoundingClientRect();if(!r.width||r.right<=w+1){return;}"
            "for(var p=el.parentElement;p&&p!==document.body;p=p.parentElement){"
            "if(/(auto|scroll|hidden|clip)/.test(getComputedStyle(p).overflowX)){return;}}"
            "out.push(el.tagName.toLowerCase()+'.'+String(el.className).split(' ').slice(0,2).join('.')+' right='+Math.round(r.right));});"
            "return JSON.stringify({sw:d.scrollWidth,w:w,out:out.slice(0,5)});})()"
        )
        pages = [(who, path.format(**data)) for _, who, path in screens.PAGES]
        pages += [
            (None, p)
            for p in (
                "/",
                "/news/",
                "/news/screens-guide/",
                "/tournaments/",
                "/scrims/",
                "/teams/",
                "/members/",
                "/search/?q=截图",
                "/about/",
                "/accounts/login/",
                "/accounts/signup/",
            )
        ]
        wide = 0
        for who, path in pages:
            sign_in(who)
            go(path, settle=2)
            seen = json.loads(evaluate(tools, overflow_js) or "{}")
            if seen.get("sw", 0) > seen.get("w", 0):
                wide += 1
                print(f"宽了：{who or '访客'} {path} 页宽 {seen['sw']} > {seen['w']}", seen["out"])
        print(f"{len(pages)} 个页面里 {wide} 个比屏幕宽")
    finally:
        browser.terminate()
        server.terminate()
        shutil.rmtree(WORK / "chromium-profile", ignore_errors=True)


if __name__ == "__main__":
    socket.setdefaulttimeout(120)
    main()
