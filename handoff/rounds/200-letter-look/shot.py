"""Round 200: screenshots of a few letters as mail clients would draw them.

Renders sample letters (core.email_samples), points their cid: pictures at the
files under static/img/email/, and has headless Chromium shoot them at desktop
and phone widths into /tmp/sjtu-ow-letters/.

bash scripts/remote-check.sh run uv run python handoff/rounds/200-letter-look/shot.py
scp "sjtu-ow-test:/tmp/sjtu-ow-letters/*.png" 本机目录
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sjtu_ow.settings.dev")

import django  # noqa: E402

django.setup()

from core import email_art  # noqa: E402
from core.email_samples import samples  # noqa: E402

OUT = Path("/tmp/sjtu-ow-letters")
KEYS = ("entered", "verify", "patrol")
SIZES = {"desktop": (720, 1500), "phone": (390, 1700)}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    by_key = {sample.key: sample for sample in samples()}
    for key in KEYS:
        html = by_key[key].html
        for cid, name in email_art.ART.items():
            html = html.replace(f"cid:{cid}", (email_art.folder() / name).as_uri())
        page = OUT / f"{key}.html"
        page.write_text(html, encoding="utf-8")
        for label, (width, height) in SIZES.items():
            target = OUT / f"{key}-{label}.png"
            subprocess.run(
                [
                    "chromium",
                    "--headless=new",
                    "--no-sandbox",
                    "--disable-gpu",
                    "--hide-scrollbars",
                    "--allow-file-access-from-files",
                    f"--window-size={width},{height}",
                    f"--screenshot={target}",
                    page.as_uri(),
                ],
                check=True,
                capture_output=True,
            )
            print("shot", target)


if __name__ == "__main__":
    main()
