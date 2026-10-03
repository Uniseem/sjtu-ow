"""Turn the review into work/selection.json.

Folder, in order: the hero named in the picture's file name (alt text);
for sheet b the folder chosen by eye; for sheet a the few maps and posters
listed below, groups otherwise. Near-duplicates (same picture, another
address) are dropped by a 16x9 average hash.
"""
import json
import runpy
from collections import Counter
from pathlib import Path

from PIL import Image

from alt_heroes import hero_for

work = Path("work")
cands = {c["file"]: c for c in json.loads((work / "candidates.json").read_text(encoding="utf-8"))}
review_a = json.loads((work / "review_a.json").read_text(encoding="utf-8"))
review_b = json.loads((work / "review_b.json").read_text(encoding="utf-8"))
keep_b = runpy.run_path(str(work / "keep_b.py"))["KEEP"]
decisions = json.loads((work / "decisions.json").read_text())
SHEET_A = {39: "地图场景", 51: "地图场景", 64: "地图场景", 76: "地图场景", 86: "地图场景",
           72: "海报", 95: "海报", 36: "海报", 65: "海报"}

chosen = []
for index, item in enumerate(review_a[:96]):
    if decisions[item["file"]]:
        chosen.append((item["file"], SHEET_A.get(index, "群像与活动")))
for index, folder in keep_b.items():
    chosen.append((review_b[index]["file"], folder))


def ahash(path):
    with Image.open(path) as im:
        small = im.convert("L").resize((16, 9))
    pixels = list(small.getdata())
    mean = sum(pixels) / len(pixels)
    return sum(1 << i for i, p in enumerate(pixels) if p > mean)


seen, selection, dups = [], [], 0
for name, folder in chosen:
    h = ahash(work / "raw" / name)
    if any(bin(h ^ other).count("1") <= 12 for other in seen):
        dups += 1
        continue
    seen.append(h)
    c = cands[name]
    folder = hero_for(c["alt"]) or folder
    if "RamJuno" in c["alt"]:  # two heroes in one name
        folder = "群像与活动"
    selection.append({"file": name, "folder": folder, "title": c["article"], "source": c["article_url"],
                      "alt": c["alt"], "w": c["w"], "h": c["h"]})
(work / "selection.json").write_text(json.dumps(selection, ensure_ascii=False, indent=1), encoding="utf-8")
print("chosen", len(chosen), "duplicates", dups, "selected", len(selection))
print(Counter(s["folder"] for s in selection).most_common())
