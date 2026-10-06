"""Round 215, F1: does the skeleton go when the state request fails?

A real prerendered homepage, in headless Chromium, with the hint cookie
`ow_logged_in=1` set, so state.js puts up the skeleton and asks
/_fragments/state/. A small server in this script stands in for Caddy: it
serves the prerendered file, passes everything else to the dev server, and
for each case breaks one thing:

  ok        the fragment answers normally (Django's anonymous answer)
  429       the fragment is rate-limited
  500       the fragment fails
  drop      the connection closes with no answer (a network error)
  hang      the fragment answers only after 15 seconds
  no-htmx   htmx.min.js is 404

Each case passes when `ow-state-pending` leaves <html> in time: at once for
the first four, after the 8-second give-up for the last two (not before 7,
so the skeleton did wait for the answer).

  bash scripts/remote-check.sh run uv run python \\
    handoff/rounds/215-caddy-and-prerender/f1_probe.py

`--old-script` serves state.before-215.js instead (the control). The old
script dropped the skeleton only when htmx.ajax resolved; htmx resolves on
429 and 5xx (it just does not swap), and rejects on a network error. So
`drop`, `hang` and `no-htmx` must fail with it, and only those. Exit code 1
if any case fails (with the old script: if the failures differ from that).
"""

from __future__ import annotations

import http.server
import json
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))
import screens  # noqa: E402

screens.WORK = Path("/tmp/sjtu-ow-f1-probe")
WORK = screens.WORK
OLD_SCRIPT = "--old-script" in sys.argv
CASES = {  # name: (earliest, latest) seconds for the skeleton to go
    "ok": (0, 3),
    "429": (0, 3),
    "500": (0, 3),
    "drop": (0, 3),
    "hang": (7, 10),
    "no-htmx": (7, 10),
}
OLD_SCRIPT_FAILS = {"drop", "hang", "no-htmx"}
mode = {"case": "ok"}

shutil.rmtree(WORK, ignore_errors=True)
WORK.mkdir(parents=True)
screens.manage("migrate", "--noinput", stdout=subprocess.DEVNULL)
screens.manage("createcachetable")
screens.manage("init_site", "--verbosity", "0", stdout=subprocess.DEVNULL)
rendered = screens.manage(
    "shell",
    "-c",
    "import sys; from core.prerender import render_html; "
    "sys.stdout.buffer.write(render_html('/'))",
    capture_output=True,
)
PAGE = rendered.stdout
assert b'data-state-filled="0"' in PAGE, "不是预渲染出来的页面"
assert b"data-slot=" in PAGE, "页面上没有占位区域"
OLD = (HERE / "state.before-215.js").read_bytes()

port, front, debug = screens.free_port(), screens.free_port(), screens.free_port()
DJANGO = f"http://127.0.0.1:{port}"


class Front(http.server.BaseHTTPRequestHandler):
    """Stands in for Caddy, with one thing broken per case."""

    def log_message(self, *args):
        pass

    def answer(self, status, body=b"", kind="text/plain"):
        try:
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # the browser moved on (the 15-second case)

    def do_GET(self):
        case, path = mode["case"], self.path
        if path == "/":
            return self.answer(200, PAGE, "text/html; charset=utf-8")
        if path.startswith("/_fragments/state/"):
            if case == "429":
                return self.answer(429)
            if case == "500":
                return self.answer(500)
            if case == "drop":
                self.close_connection = True
                self.connection.close()
                return None
            if case == "hang":
                time.sleep(15)
        if case == "no-htmx" and "htmx" in path:
            return self.answer(404)
        if OLD_SCRIPT and path.split("?")[0].endswith("/js/state.js"):
            return self.answer(200, OLD, "text/javascript")
        request = urllib.request.Request(
            DJANGO + path, headers={"Cookie": self.headers.get("Cookie", "")}
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                kind = response.headers.get("Content-Type", "text/plain")
                return self.answer(response.status, response.read(), kind)
        except urllib.error.HTTPError as error:
            return self.answer(error.code, error.read())


server = subprocess.Popen(
    [sys.executable, "manage.py", "runserver", f"127.0.0.1:{port}", "--noreload"],
    cwd=ROOT,
    env=screens.site_env(),
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
proxy = http.server.ThreadingHTTPServer(("127.0.0.1", front), Front)
threading.Thread(target=proxy.serve_forever, daemon=True).start()
browser = subprocess.Popen(
    [
        "chromium",
        "--headless=new",
        "--no-sandbox",
        f"--remote-debugging-port={debug}",
        f"--user-data-dir={WORK / 'chromium-profile'}",
        "about:blank",
    ],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
failed: list[str] = []
try:
    screens.wait_for(f"{DJANGO}/robots.txt")
    screens.wait_for(f"http://127.0.0.1:{debug}/json/version")
    targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{debug}/json"))
    page = next(t for t in targets if t.get("type") == "page")
    tools = screens.DevTools(page["webSocketDebuggerUrl"])
    tools.send("Page.enable")
    tools.send("Network.enable")
    tools.send("Network.setCacheDisabled", {"cacheDisabled": True})

    # A failed request drops the skeleton within milliseconds, faster than
    # polling from here can see; the page notes the moments itself.
    tools.send(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": (
                "window.__skeleton = {shown: null, gone: null};"
                "new MutationObserver(function () {"
                "  var html = document.documentElement, s = window.__skeleton;"
                "  if (!html) { return; }"
                "  var on = html.className.indexOf('ow-state-pending') !== -1;"
                "  var t = performance.now() / 1000;"
                "  if (on && s.shown === null) { s.shown = t; }"
                "  if (!on && s.shown !== null && s.gone === null) { s.gone = t; }"
                "}).observe(document, {attributes: true, subtree: true,"
                "  attributeFilter: ['class']});"
            )
        },
    )

    def evaluate(expression):
        result = tools.send("Runtime.evaluate", {"expression": expression})
        return result.get("result", {}).get("value")

    print("state.js：" + ("改之前的（对照）" if OLD_SCRIPT else "这一轮的") + "\n")
    for case, (earliest, latest) in CASES.items():
        mode["case"] = case
        tools.send("Page.navigate", {"url": "about:blank"})
        time.sleep(0.3)
        tools.send("Network.clearBrowserCookies")
        tools.send(
            "Network.setCookie",
            {"name": "ow_logged_in", "value": "1", "url": f"http://127.0.0.1:{front}/"},
        )
        started = time.monotonic()
        tools.send("Page.navigate", {"url": f"http://127.0.0.1:{front}/"})
        seen = {}
        while time.monotonic() - started < latest + 2:
            seen = evaluate("JSON.stringify(window.__skeleton || {})") or "{}"
            seen = json.loads(seen)
            if seen.get("gone") is not None:
                break
            time.sleep(0.2)
        saw_skeleton = seen.get("shown") is not None
        gone_after = seen.get("gone")  # seconds since the page started loading
        shown = evaluate(
            "(function(){var n=document.querySelector('[data-slot] > *');"
            "return n ? getComputedStyle(n).visibility : 'none';})()"
        )
        ok = (
            saw_skeleton
            and gone_after is not None
            and earliest <= gone_after <= latest
            and shown == "visible"
        )
        if not ok:
            failed.append(case)
        when = f"{gone_after:.1f} 秒后去掉" if gone_after is not None else "一直没去掉"
        if not saw_skeleton:
            when = "没看到骨架"
        print(
            ("ok   " if ok else "FAIL ")
            + f"{case:8} 骨架{when}（要求 {earliest}–{latest} 秒），"
            + f"占位区内容 {shown}"
        )
finally:
    browser.terminate()
    server.terminate()
    proxy.shutdown()
    shutil.rmtree(WORK / "chromium-profile", ignore_errors=True)

print(f"\n{len(CASES) - len(failed)} 种情况通过，{len(failed)} 种失败")
if OLD_SCRIPT:
    as_expected = set(failed) == OLD_SCRIPT_FAILS
    print("对照：" + ("符合预期" if as_expected else "不符合预期"))
    sys.exit(0 if as_expected else 1)
sys.exit(1 if failed else 0)
