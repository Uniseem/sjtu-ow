"""Loading bar and page swap in a fresh headless Edge, on a slow network.

python loading_probe.py START_URL LINK_SELECTOR OUT_PNG
1. Emulates 1500ms latency, clicks the link, and 600ms later reads the old
   page: is-loading on <html>, the bar's on-screen width; saves a crop of
   the masthead as OUT_PNG.
2. On the new page, lists the view-transition animations that ran.
3. Switches colour mode and reports whether it went through a transition.
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

HOOK = r"""
window.addEventListener('pagereveal', (event) => {
  window.__vt = !!event.viewTransition;
  if (event.viewTransition) {
    event.viewTransition.ready.then(() => {
      window.__anims = document.getAnimations()
        .filter((a) => a.effect && a.effect.pseudoElement)
        .map((a) => a.effect.pseudoElement + ' ' + a.animationName + ' ' + a.effect.getTiming().duration);
    });
  }
});
"""

THEME = r"""(async () => {
  let transitions = 0;
  const real = document.startViewTransition.bind(document);
  document.startViewTransition = (cb) => { transitions += 1; return real(cb); };
  document.querySelector('[data-theme-choice="dark"]').click();
  const during = document.documentElement.classList.contains('is-theme-switch');
  await new Promise((r) => setTimeout(r, 600));
  return {transitions, during, after: document.documentElement.classList.contains('is-theme-switch'),
          theme: document.documentElement.getAttribute('data-theme')};
})()"""


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def evaluate(ws, expression):
    result = ws.send("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
    return result.get("result", {}).get("value")


def main():
    start, selector, out = sys.argv[1], sys.argv[2], sys.argv[3]
    port = free_port()
    profile = tempfile.mkdtemp(prefix="edge-load-")
    edge = subprocess.Popen(
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
        ws = Socket(page["webSocketDebuggerUrl"])
        for method in ("Page.enable", "Runtime.enable", "Network.enable"):
            ws.send(method)
        ws.send("Emulation.setDeviceMetricsOverride", {"width": 1280, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        ws.send("Page.addScriptToEvaluateOnNewDocument", {"source": HOOK})
        ws.send("Page.navigate", {"url": start})
        time.sleep(3)
        script = evaluate(ws, "(async () => (await (await fetch(document.querySelector('script[src*=loading]').src, {cache: 'no-store'})).text()).includes('is-loading'))()")
        box = evaluate(ws, f"""(() => {{
            const a = document.querySelector({json.dumps(selector)});
            a.scrollIntoView({{block: 'center'}});
            const r = a.getBoundingClientRect();
            return {{x: r.left + r.width / 2, y: r.top + r.height / 2, href: a.href}};
        }})()""")
        print("loading.js served:", script, "| link", box["href"])
        ws.send("Network.emulateNetworkConditions", {"offline": False, "latency": 1500, "downloadThroughput": -1, "uploadThroughput": -1})
        for kind in ("mousePressed", "mouseReleased"):
            ws.send("Input.dispatchMouseEvent", {"type": kind, "x": box["x"], "y": box["y"], "button": "left", "clickCount": 1})
        time.sleep(0.6)
        waiting = evaluate(ws, """(() => {
            const bar = document.querySelector('.c-loadbar');
            return {url: location.pathname, loading: document.documentElement.classList.contains('is-loading'),
                    barWidth: Math.round(bar.getBoundingClientRect().width), opacity: getComputedStyle(bar).opacity};
        })()""")
        print("600ms after the click, still on the old page:", waiting)
        shot = ws.send("Page.captureScreenshot", {"format": "png", "clip": {"x": 0, "y": 0, "width": 1280, "height": 140, "scale": 1}})
        with open(out, "wb") as handle:
            handle.write(base64.b64decode(shot["data"]))
        time.sleep(4)
        ws.send("Network.emulateNetworkConditions", {"offline": False, "latency": 0, "downloadThroughput": -1, "uploadThroughput": -1})
        print("new page:", evaluate(ws, "({url: location.pathname, viewTransition: window.__vt, loading: document.documentElement.classList.contains('is-loading'), animations: window.__anims || []})"))
        print("colour mode:", evaluate(ws, THEME))
    finally:
        # The launcher exits early, so close Edge by its profile name.
        script = (
            "Get-CimInstance Win32_Process -Filter \"Name = 'msedge.exe'\" | "
            "Where-Object { $_.CommandLine -like '*" + os.path.basename(profile) + "*' } | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True)
        edge.poll()


main()
