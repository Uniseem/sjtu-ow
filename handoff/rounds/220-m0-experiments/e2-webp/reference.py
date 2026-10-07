"""libwebp (through Pillow, C) on the very JPEG the Go benchmark used: the
reference for E2. Usage: python reference.py upload.jpg [runs]"""

import io
import statistics
import sys
import time

from PIL import Image

runs = int(sys.argv[2]) if len(sys.argv) > 2 else 5
upload = Image.open(sys.argv[1])
ts = []
for _ in range(runs):
    t = time.perf_counter()
    big = Image.open(sys.argv[1]).convert("RGB")
    big.load()
    ts.append(time.perf_counter() - t)
print(f"decode JPEG {big.size}: median {statistics.median(ts) * 1000:.0f} ms")
for side, method in ((4000, 4), (2560, 4), (2560, 2)):
    im = big if side == 4000 else big.resize((side, side * 3 // 4), Image.LANCZOS)
    ts = []
    for _ in range(runs):
        b = io.BytesIO()
        t = time.perf_counter()
        im.save(b, "WEBP", quality=90, method=method)
        ts.append(time.perf_counter() - t)
    print(
        f"master {side} wide q90 method {method}: median {statistics.median(ts) * 1000:.0f} ms, {b.tell() // 1024} KB"
    )
th = big.resize((2400, 1350), Image.LANCZOS)
ts = []
for _ in range(runs):
    b = io.BytesIO()
    t = time.perf_counter()
    th.save(b, "WEBP", quality=80, method=4)
    ts.append(time.perf_counter() - t)
print(f"thumb 2400x1350 q80 method 4 (encode only): median {statistics.median(ts) * 1000:.0f} ms, {b.tell() // 1024} KB")
