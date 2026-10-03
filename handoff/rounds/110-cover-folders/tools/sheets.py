"""Contact sheets for reviewing pictures: 6 x 5 thumbnails, each with its
number and current folder written on it.

python sheets.py LIST_JSON IMAGE_ROOT OUT_DIR [per_sheet]
LIST_JSON: [{"file": relative path, "folder": "...", ...}] in review order.
"""

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 22)
TW, TH, COLS = 300, 169, 8


def main():
    items = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    root, out = Path(sys.argv[2]), Path(sys.argv[3])
    per = int(sys.argv[4]) if len(sys.argv) > 4 else 48
    out.mkdir(parents=True, exist_ok=True)
    for start in range(0, len(items), per):
        chunk = items[start : start + per]
        rows = (len(chunk) + COLS - 1) // COLS
        sheet = Image.new("RGB", (COLS * TW, rows * TH), "black")
        draw = ImageDraw.Draw(sheet)
        for k, item in enumerate(chunk):
            x, y = (k % COLS) * TW, (k // COLS) * TH
            try:
                with Image.open(root / item["file"]) as picture:
                    picture = picture.convert("RGB")
                    picture.thumbnail((TW, TH))
                    sheet.paste(picture, (x + (TW - picture.width) // 2, y + (TH - picture.height) // 2))
            except Exception as error:
                draw.text((x + 10, y + 100), f"ERR {error}"[:40], fill="red", font=FONT)
            label = f"{start + k} {item.get('folder', '')}"
            draw.rectangle([x, y, x + 12 + draw.textlength(label, font=FONT), y + 26], fill=(0, 0, 0))
            draw.text((x + 6, y + 2), label, fill=(255, 220, 90), font=FONT)
        sheet.save(out / f"sheet_{start // per + 1:02d}.jpg", quality=78)
    print("sheets:", (len(items) + per - 1) // per)


main()
