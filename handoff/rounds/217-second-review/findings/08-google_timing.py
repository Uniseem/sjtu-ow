"""217 复核 08-7：「从 Google Fonts 下载」在 web 请求里同步下载全部分片要多久。

照 core.fonts.services.add_google_faces → download_google_slices 的顺序逐个 fetch_bytes，
只计时、不写文件、不碰数据库。gunicorn 没配 --timeout，默认 30 秒。

  bash scripts/remote-check.sh run uv run python \
    handoff/rounds/217-second-review/findings/08-google_timing.py ["Noto Sans SC"] [400,700]
"""

import os
import sys
import time

sys.path.insert(0, os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sjtu_ow.settings.dev")
import django  # noqa: E402

django.setup()

from core.fonts import download  # noqa: E402

family = sys.argv[1] if len(sys.argv) > 1 else "Noto Sans SC"
weights = (sys.argv[2] if len(sys.argv) > 2 else "400,700").split(",")

start = time.monotonic()
css = download.fetch_google_css(family, weights)
faces = download.parse_google_css(css)
urls = {face["url"] for face in faces}
print(f"{family} {weights}：样式表 {time.monotonic() - start:.1f} 秒，"
      f"{len(faces)} 个 @font-face，{len(urls)} 个不同的地址")

total = 0
for index, face in enumerate(faces, 1):
    total += len(download.fetch_bytes(face["url"]))
    elapsed = time.monotonic() - start
    if index % 25 == 0 or index == len(faces):
        print(f"  已下载 {index}/{len(faces)}，{total / 1024 / 1024:.1f} MB，"
              f"累计 {elapsed:.1f} 秒")
print(f"合计 {time.monotonic() - start:.1f} 秒（gunicorn 默认 30 秒超时）")
