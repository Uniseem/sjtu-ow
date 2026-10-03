"""Does the loading bar run to the end and fade on the next page?

python finish_probe.py START_URL LINK_SELECTOR OUT_DIR
Clicks a link (kept out of speculation rules, so it really loads) on a
network with 1500ms latency. The old page's bar shows and notes where it got
to; a hook on the new page samples the bar every animation frame for 900ms.
Prints the note, then the samples (time, width share, opacity). Uses the
stdlib DevTools client in ../106-page-transitions/cdp_shoot.py.
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

HERE = os.path.dirname(os.path.abspath(__file__))
_shoot = {}
with open(os.path.join(HERE, "..", "106-page-transitions", "cdp_shoot.py"), encoding="utf-8") as _f:
    exec(_f.read().rsplit("\nmain()", 1)[0], _shoot)
EDGE, Socket = _shoot["EDGE"], _shoot["Socket"]

HOOK = r"""
window.__samples = [];
window.__note = sessionStorage.getItem('ow-loading');
let t0 = null;  // the first frame: on a slow network that is well after the document starts
function sample() {
  const now = performance.now();
  if (t0 === null) t0 = now;
  const bar = document.querySelector('.c-loadbar');
  if (bar) {
    const m = /^matrix\(([^,]+),/.exec(getComputedStyle(bar).transform) || [0, '0'];
    window.__samples.push([Math.round(now - t0), Number(Number(m[1]).toFixed(3)),
                           Number(Number(getComputedStyle(bar).opacity).toFixed(2))]);
  }
  if (now - t0 < 900) requestAnimationFrame(sample);
}
requestAnimationFrame(sample);
"""


def kill_profile(profile):
    script = (
        "Get-CimInstance Win32_Process -Filter \"Name = 'msedge.exe'\" | "
        "Where-Object { $_.CommandLine -like '*" + os.path.basename(profile) + "*' } | "
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


def main():
    start, selector, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    port = free_port()
    profile = tempfile.mkdtemp(prefix="edge-finish-")
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
        ws = Socket(page["webSocketDebuggerUrl"])
        for method in ("Page.enable", "Runtime.enable", "Network.enable"):
            ws.send(method)
        ws.send("Emulation.setDeviceMetricsOverride", {"width": 1280, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        ws.send("Page.navigate", {"url": start})
        time.sleep(3)
        box = evaluate(ws, f"""(() => {{
            const a = document.querySelector({json.dumps(selector)});
            a.setAttribute('data-no-prerender', '');
            a.scrollIntoView({{block: 'center'}});
            const r = a.getBoundingClientRect();
            return {{x: r.left + r.width / 2, y: r.top + r.height / 2, href: a.href}};
        }})()""")
        print("link", box["href"])
        ws.send("Page.addScriptToEvaluateOnNewDocument", {"source": HOOK})
        ws.send("Network.emulateNetworkConditions", {"offline": False, "latency": 1500, "downloadThroughput": -1, "uploadThroughput": -1})
        for kind in ("mousePressed", "mouseReleased"):
            ws.send("Input.dispatchMouseEvent", {"type": kind, "x": box["x"], "y": box["y"], "button": "left", "clickCount": 1})
        time.sleep(4)
        ws.send("Network.emulateNetworkConditions", {"offline": False, "latency": 0, "downloadThroughput": -1, "uploadThroughput": -1})
        result = evaluate(ws, """({url: location.pathname, note: window.__note,
            from: document.documentElement.style.getPropertyValue('--loadbar-from'),
            arriving: document.documentElement.classList.contains('is-arriving'),
            left: sessionStorage.getItem('ow-loading'), samples: window.__samples})""")
        samples = result.pop("samples") or []
        print(json.dumps(result, ensure_ascii=False))
        for row in samples[::3]:
            print("  t=%4dms  width=%.3f  opacity=%.2f" % tuple(row))
        if samples:
            print("  last:", samples[-1])
        top = evaluate(ws, "window.scrollY") or 0
        shot = ws.send("Page.captureScreenshot", {"format": "png", "clip": {"x": 0, "y": top, "width": 1280, "height": 110, "scale": 1}})
        with open(os.path.join(out_dir, "after-arrival.png"), "wb") as handle:
            handle.write(base64.b64decode(shot["data"]))
    finally:
        kill_profile(profile)


main()
