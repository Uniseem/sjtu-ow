"""Crop the chosen pictures to 16:9 with the subject a little off centre.

python make_pool.py SELECTION_JSON IMAGE_ROOT OUT_DIR
SELECTION_JSON: [{"file", "folder", "title", "source", optional "x", "y"}]
x, y (0-1) say where the subject is; without them a rough saliency guess
(where the detail is) stands in. Writes OUT_DIR/<folder>/<n>.jpg (16:9, at
most 2400 wide) and OUT_DIR/pool.json with each picture's focal point.
"""

import json
import sys
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

TARGET_X = 0.58  # the subject sits a little right of centre (design 13.2.5, v6.8)
TARGET_Y = 0.42
MIN_ZOOM = 0.78  # never crop tighter than this share of the widest 16:9 window


def subject(picture):
    """Where the detail is: centre of the strongest edges, after blurring."""
    small = ImageOps.grayscale(picture).copy()
    small.thumbnail((320, 320))
    edges = small.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(6))
    w, h = edges.size
    values = list(edges.getdata())
    cutoff = sorted(values)[int(len(values) * 0.85)]
    sx = sy = total = 0.0
    for i, v in enumerate(values):
        if v >= cutoff and v > 0:
            x, y = i % w, i // w
            # Pictures often carry a logo or a strip of UI along the edges.
            if x < w * 0.03 or x > w * 0.97 or y < h * 0.05 or y > h * 0.95:
                continue
            sx += x * v
            sy += y * v
            total += v
    if not total:
        return 0.5, 0.45
    return sx / total / w, sy / total / h


def crop_box(width, height, sx, sy):
    if width / height > 16 / 9:
        base_w, base_h = height * 16 / 9, height
    else:
        base_w, base_h = width, width * 9 / 16
    target = TARGET_X if sx >= 0.45 else 1 - TARGET_X
    # Zoom in only as far as needed to bring the subject near the target.
    win_w = base_w
    for zoom in (1.0, 0.95, 0.9, 0.85, MIN_ZOOM):
        win_w = base_w * zoom
        left = sx * width - target * win_w
        if 0 <= left <= width - win_w:
            break
    win_h = win_w * 9 / 16
    left = min(max(sx * width - target * win_w, 0), width - win_w)
    top = min(max(sy * height - TARGET_Y * win_h, 0), height - win_h)
    return left, top, left + win_w, top + win_h


def main():
    chosen = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    root, out = Path(sys.argv[2]), Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    pool, counters = [], {}
    for item in chosen:
        with Image.open(root / item["file"]) as picture:
            picture = picture.convert("RGB")
            width, height = picture.size
            sx, sy = (item["x"], item["y"]) if "x" in item else subject(picture)
            box = crop_box(width, height, sx, sy)
            cut = picture.crop(tuple(round(v) for v in box))
            final_w = min(2400, cut.width)
            cut = cut.resize((final_w, round(final_w * 9 / 16)), Image.LANCZOS)
        folder = item["folder"]
        counters[folder] = counters.get(folder, 0) + 1
        target = out / folder / f"{counters[folder]:03d}.jpg"
        target.parent.mkdir(parents=True, exist_ok=True)
        cut.save(target, quality=84, optimize=True, progressive=True)
        # Where the subject ended up, in the cut picture.
        fy = (sy * height - box[1]) / (box[3] - box[1])
        fx = (sx * width - box[0]) / (box[2] - box[0])
        pool.append({
            "path": target.relative_to(out).as_posix(), "folder": folder,
            "title": item.get("title", ""), "source": item.get("source", ""),
            "subject": [round(fx, 3), round(min(max(fy, 0.1), 0.9), 3)],
            "size": [cut.width, cut.height],
        })
    (out / "pool.json").write_text(json.dumps(pool, ensure_ascii=False, indent=1), encoding="utf-8")
    print("pictures:", len(pool), "folders:", len(counters))


main()
