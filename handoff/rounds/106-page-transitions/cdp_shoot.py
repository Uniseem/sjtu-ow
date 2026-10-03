"""Full-page screenshots through headless Edge's DevTools port (stdlib only).

python shoot.py OUT_DIR WIDTH HEIGHT SCHEME name=url [name=url ...]
SCHEME is light or dark. Each page is captured whole (captureBeyondViewport)
with the viewport at WIDTH x HEIGHT, so 100svh is HEIGHT.
"""

import base64
import json
import os
import socket
import struct
import subprocess
import sys
import time
import urllib.request

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 9333


class Socket:
    def __init__(self, url):
        rest = url.split("://", 1)[1]
        hostport, path = rest.split("/", 1)
        host, port = hostport.split(":")
        self.sock = socket.create_connection((host, int(port)), timeout=60)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall(
            (
                f"GET /{path} HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\n"
                f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
                "Sec-WebSocket-Version: 13\r\n\r\n"
            ).encode()
        )
        head = b""
        while b"\r\n\r\n" not in head:
            head += self.sock.recv(1)
        self.next_id = 0

    def _read(self, n):
        data = b""
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                raise ConnectionError("closed")
            data += chunk
        return data

    def send(self, method, params=None):
        self.next_id += 1
        payload = json.dumps({"id": self.next_id, "method": method, "params": params or {}}).encode()
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
        self.sock.sendall(bytes(header) + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))
        wanted = self.next_id
        while True:
            message = json.loads(self.receive())
            if message.get("id") == wanted:
                if "error" in message:
                    raise RuntimeError(message["error"])
                return message.get("result", {})

    def receive(self):
        parts = b""
        while True:
            b1, b2 = self._read(2)
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
            data = self._read(n)
            if b1 & 0x0F == 0x8:
                raise ConnectionError("closed")
            if b1 & 0x0F in (0x9, 0xA):
                continue
            parts += data
            if b1 & 0x80:
                return parts.decode("utf-8")


def main():
    out_dir, width, height, scheme = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    jobs = [arg.split("=", 1) for arg in sys.argv[5:]]
    profile = os.path.abspath(os.path.join(out_dir, "edge-cdp-profile"))
    edge = subprocess.Popen(
        [
            EDGE, "--headless=new", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
            "--hide-scrollbars", f"--remote-debugging-port={PORT}", f"--user-data-dir={profile}",
            f"--window-size={width},{height}", "about:blank",
        ],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(50):
            try:
                pages = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json"))
                page = next(p for p in pages if p.get("type") == "page")
                break
            except Exception:
                time.sleep(0.2)
        ws = Socket(page["webSocketDebuggerUrl"])
        ws.send("Page.enable")
        ws.send("Emulation.setDeviceMetricsOverride", {
            "width": width, "height": height, "deviceScaleFactor": 1, "mobile": width < 600,
        })
        ws.send("Emulation.setEmulatedMedia", {
            "features": [{"name": "prefers-color-scheme", "value": scheme}],
        })
        for name, url in jobs:
            ws.send("Page.navigate", {"url": url})
            time.sleep(3.5)
            metrics = ws.send("Page.getLayoutMetrics")
            full = metrics.get("cssContentSize") or metrics["contentSize"]
            shot = ws.send("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": True,
                "clip": {"x": 0, "y": 0, "width": width, "height": full["height"], "scale": 1},
            })
            path = os.path.join(out_dir, f"{name}.png")
            with open(path, "wb") as handle:
                handle.write(base64.b64decode(shot["data"]))
            print(name, int(full["height"]), os.path.getsize(path))
    finally:
        subprocess.run(["taskkill", "/PID", str(edge.pid), "/T", "/F"], capture_output=True)


main()
