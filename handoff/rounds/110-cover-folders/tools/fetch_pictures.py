"""Size up the crawled pictures, download the usable ones, label them.

python fetch_pictures.py NEWS_JSON WORKDIR
- reads each picture's first 128 KB to learn its size (no full download yet)
- keeps landscape pictures at least 1500 wide, ratio 1.25-2.7
- downloads those to WORKDIR/raw/, writes WORKDIR/candidates.json with a
  first guess at the folder (hero, map, group or poster) from the words
"""

import hashlib
import json
import re
import struct
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 sjtu-ow-cover-pool"}

# Traditional names on the site -> folder names (simplified, as on the club's site).
HEROES = {
    "安娜": "安娜", "安燃": "安燃", "艾西": "艾什", "巴帝斯特": "巴蒂斯特", "壁壘機兵": "堡垒",
    "碧姬": "布丽吉塔", "卡西迪": "卡西迪", "D.MON": "D.MON", "多米娜": "多米娜", "毀滅拳王": "末日铁拳",
    "D.VA": "D.Va", "D.Va": "D.Va", "迴音": "回声", "伊默": "伊默", "弗蕾亞": "弗蕾娅", "源氏": "源氏",
    "半藏": "半藏", "災害": "骇灾", "伊拉里": "伊拉锐", "火箭貓": "火箭猫", "垃圾鎮女王": "渣客女王",
    "炸彈鼠": "狂鼠", "朱諾": "朱诺", "霧子": "雾子", "織命": "生命之梭", "路西歐": "卢西奥", "莫加": "毛加",
    "小美": "美", "慈悲": "天使", "瑞稀": "瑞稀", "莫伊拉": "莫伊拉", "歐瑞莎": "奥丽莎", "法拉": "法老之鹰",
    "拉瑪塔": "拉玛刹", "死神": "死神", "萊因哈特": "莱因哈特", "攔路豬": "路霸", "死怨": "死怨",
    "席艾拉": "席艾拉", "席格馬": "西格玛", "索潔恩": "索杰恩", "士兵76": "士兵：76", "士兵：76": "士兵：76",
    "駭影": "黑影", "辛梅塔": "秩序之光", "托比昂": "托比昂", "閃光": "猎空", "宿怨": "宿怨", "無畏": "探奇",
    "奪命女": "黑百合", "溫斯頓": "温斯顿", "火爆鋼球": "破坏球", "無漾": "无漾", "札莉雅": "查莉娅",
    "禪亞塔": "禅雅塔",
}
HERO_RE = re.compile("|".join(sorted(map(re.escape, HEROES), key=len, reverse=True)))
MAP_RE = re.compile(r"地圖|戰場|城市|基地|地點|場景|街道|港口|神殿|競技場|努巴尼|國王大道|好萊塢|花村|漓江塔|伊利歐斯|尼泊爾|綠洲城|直布羅陀|多拉多|哈瓦那|渣客鎮|里亞托|中城|帕萊索|新皇后街|羅馬|艾斯佩蘭薩|釜山|南極|薩摩亞|蘇拉瓦薩|新渣客城|艾興瓦爾德|阿德勒堡|時代廣場|盧納薩皮|湧泉|希望之城|運動會")


def get(url, byte_range=None):
    headers = dict(UA)
    if byte_range:
        headers["Range"] = f"bytes=0-{byte_range - 1}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def size_of(head: bytes):
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", head[16:24])
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        chunk = head[12:16]
        if chunk == b"VP8X":
            w = 1 + int.from_bytes(head[24:27], "little")
            h = 1 + int.from_bytes(head[27:30], "little")
            return w, h
        if chunk == b"VP8 ":
            w, h = struct.unpack("<HH", head[26:30])
            return w & 0x3FFF, h & 0x3FFF
        if chunk == b"VP8L":
            bits = int.from_bytes(head[21:25], "little")
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if head[:2] == b"\xff\xd8":
        i = 2
        while i < len(head) - 9:
            if head[i] != 0xFF:
                i += 1
                continue
            marker = head[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", head[i + 5 : i + 9])
                return w, h
            length = struct.unpack(">H", head[i + 2 : i + 4])[0]
            i += 2 + length
    return None


def probe(src):
    for attempt in range(3):
        try:
            return src, size_of(get(src, 131072))
        except Exception:
            time.sleep(1 + attempt)
    return src, None


def guess(texts):
    heroes = []
    for text in texts:
        for match in HERO_RE.findall(text or ""):
            name = HEROES[match]
            if name not in heroes:
                heroes.append(name)
    if len(heroes) == 1:
        return heroes[0]
    if len(heroes) > 1:
        return "群像与活动"
    if any(MAP_RE.search(t or "") for t in texts):
        return "地图场景"
    return "海报"


def main():
    news = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    work = Path(sys.argv[2])
    (work / "raw").mkdir(parents=True, exist_ok=True)
    seen, items = set(), []
    for article in news:
        for image in article.get("images", []):
            if image["src"] in seen:
                continue
            seen.add(image["src"])
            items.append(image | {"article": article["title"], "article_url": article["url"]})
    print("unique pictures:", len(items))
    with ThreadPoolExecutor(8) as pool:
        sizes = dict(pool.map(probe, [i["src"] for i in items]))
    usable = []
    for item in items:
        size = sizes.get(item["src"])
        if not size:
            continue
        w, h = size
        if w >= 1500 and 1.25 <= w / h <= 2.7:
            usable.append(item | {"w": w, "h": h})
    print("usable by size:", len(usable))

    def download(item):
        name = hashlib.sha1(item["src"].encode()).hexdigest()[:12] + Path(item["src"]).suffix.lower()
        target = work / "raw" / name
        if not target.exists():
            for attempt in range(3):
                try:
                    target.write_bytes(get(item["src"]))
                    break
                except Exception:
                    time.sleep(2 + attempt)
        return item | {"file": name, "folder": guess([item["alt"], item["near"]]) if (item["alt"] or item["near"]) else guess([item["article"]]),
                       "folder_from_title": guess([item["article"]])}

    with ThreadPoolExecutor(6) as pool:
        done = [d for d in pool.map(download, usable) if (work / "raw" / d["file"]).exists()]
    (work / "candidates.json").write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum((work / "raw" / d["file"]).stat().st_size for d in done)
    print("downloaded:", len(done), "| MB:", round(total / 1e6, 1))
    from collections import Counter
    print(Counter(d["folder"] for d in done).most_common(40))


main()
