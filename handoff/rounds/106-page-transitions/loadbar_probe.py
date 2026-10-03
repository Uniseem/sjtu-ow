"""Is the loading bar there while the next page is held back?

python loadbar_probe.py START_URL LINK_SELECTOR OUT_DIR [dark]
Pauses the request for the link's page (CDP Fetch), clicks the link, and
reads the old page at 100ms (before the bar's delay), 700ms and 1800ms;
saves a masthead crop at 700ms and 1800ms; then lets the request through.
Edge is closed by its profile name, since the launcher process exits early.
"""

import base64
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

_shoot = {}
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cdp_shoot.py"), encoding="utf-8") as _f:
    exec(_f.read().rsplit("\nmain()", 1)[0], _shoot)
EDGE, Socket = _shoot["EDGE"], _shoot["Socket"]


class Recording(Socket):
    def __init__(self, url):
        super().__init__(url)
        self.events = []

    def receive(self):
        raw = super().receive()
        message = json.loads(raw)
        if "method" in message:
            self.events.append(message)
        return raw


def kill_profile(profile):
    name = os.path.basename(profile)
    script = (
        "Get-CimInstance Win32_Process -Filter \"Name = 'msedge.exe'\" | "
        "Where-Object { $_.CommandLine -like '*" + name + "*' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def evaluate(ws, expression):
    result = ws.send("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
    return result.get("result", {}).get("value")


STATE = """(() => {
  const bar = document.querySelector('.c-loadbar');
  return {old: window.__old === 1, url: location.pathname, loading: document.documentElement.classList.contains('is-loading'),
          barWidth: Math.round(bar.getBoundingClientRect().width), opacity: getComputedStyle(bar).opacity};
})()"""


def main():
    start, selector, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    dark = len(sys.argv) > 4 and sys.argv[4] == "dark"
    port = free_port()
    profile = tempfile.mkdtemp(prefix="edge-load-")
    subprocess.Popen(
        [EDGE, "--headless=new", f"--remote-debugging-port={port}", f"--user-data-dir={profile}",
         "--window-size=1280,900", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(50):
            try:
                pages = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json"))
                page = next(p for p in pages if p.get("type") == "page")
                break
            except Exception:
                time.sleep(0.2)
        ws = Recording(page["webSocketDebuggerUrl"])
        ws.send("Page.enable")
        ws.send("Runtime.enable")
        ws.send("Emulation.setDeviceMetricsOverride", {"width": 1280, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        if dark:
            ws.send("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": "dark"}]})
        ws.send("Page.navigate", {"url": start})
        time.sleep(3)
        box = evaluate(ws, f"""(() => {{
            const a = document.querySelector({json.dumps(selector)});
            a.setAttribute('data-no-prerender', '');  // force a real network load
            a.scrollIntoView({{block: 'center'}});
            const r = a.getBoundingClientRect();
            return {{x: r.left + r.width / 2, y: r.top + r.height / 2, href: a.href}};
        }})()""")
        target = box["href"].split("://", 1)[1].split("/", 1)[1]
        # loading.js listens on document; this runs after it and keeps the page here.
        evaluate(ws, "window.addEventListener('click', (e) => e.preventDefault())")
        evaluate(ws, "window.__old = 1")
        print("link", box["href"])
        clicked = time.time()
        for kind in ("mousePressed", "mouseReleased"):
            ws.send("Input.dispatchMouseEvent", {"type": kind, "x": box["x"], "y": box["y"], "button": "left", "clickCount": 1})
        for at, shot in ((0.1, None), (0.7, "loadbar-700ms.png"), (1.8, "loadbar-1800ms.png")):
            time.sleep(max(0, at - (time.time() - clicked)))
            asked = time.time() - clicked
            state = evaluate(ws, STATE)
            print(f"{int(at * 1000)}ms (asked {asked:.2f}s, answered {time.time() - clicked:.2f}s):", state)
            if shot:
                top = evaluate(ws, "window.scrollY") or 0
                data = ws.send("Page.captureScreenshot", {"format": "png", "clip": {"x": 0, "y": top, "width": 1280, "height": 110, "scale": 1}})
                with open(os.path.join(out_dir, shot), "wb") as handle:
                    handle.write(base64.b64decode(data["data"]))
        time.sleep(3)
        print("after release:", evaluate(ws, STATE))
    finally:
        kill_profile(profile)


main()
