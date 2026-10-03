"""Each hero page's header art (2600_<Hero>.jpg) from the official site.

python hero_banners.py WORKDIR
"""

import json
import re
import sys
import time
import urllib.request
from pathlib import Path

SLUGS = {
    "ana": "安娜", "anran": "安燃", "ashe": "艾什", "baptiste": "巴蒂斯特", "bastion": "堡垒",
    "brigitte": "布丽吉塔", "cassidy": "卡西迪", "dmon": "D.MON", "domina": "多米娜", "doomfist": "末日铁拳",
    "dva": "D.Va", "echo": "回声", "emre": "伊默", "freja": "弗蕾娅", "genji": "源氏", "hanzo": "半藏",
    "hazard": "骇灾", "illari": "伊拉锐", "jetpack-cat": "火箭猫", "junker-queen": "渣客女王", "junkrat": "狂鼠",
    "juno": "朱诺", "kiriko": "雾子", "lifeweaver": "生命之梭", "lucio": "卢西奥", "mauga": "毛加", "mei": "美",
    "mercy": "天使", "mizuki": "瑞稀", "moira": "莫伊拉", "orisa": "奥丽莎", "pharah": "法老之鹰",
    "ramattra": "拉玛刹", "reaper": "死神", "reinhardt": "莱因哈特", "roadhog": "路霸", "shion": "死怨",
    "sierra": "席艾拉", "sigma": "西格玛", "sojourn": "索杰恩", "soldier-76": "士兵：76", "sombra": "黑影",
    "symmetra": "秩序之光", "torbjorn": "托比昂", "tracer": "猎空", "vendetta": "宿怨", "venture": "探奇",
    "widowmaker": "黑百合", "winston": "温斯顿", "wrecking-ball": "破坏球", "wuyang": "无漾", "zarya": "查莉娅",
    "zenyatta": "禅雅塔",
}
UA = {"User-Agent": "Mozilla/5.0 sjtu-ow-cover-pool"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def main():
    work = Path(sys.argv[1])
    (work / "heroes").mkdir(parents=True, exist_ok=True)
    found = []
    for slug, name in SLUGS.items():
        page = get(f"https://overwatch.blizzard.com/zh-tw/heroes/{slug}/").decode("utf-8", "replace")
        match = re.search(r"https://blz-contentstack-images\.akamaized\.net/[^\"'\s)]+/2600_[^\"'\s)]+\.(?:jpg|png)", page)
        if not match:
            print("no banner:", slug)
            continue
        target = work / "heroes" / f"{slug}{Path(match.group(0)).suffix}"
        if not target.exists():
            target.write_bytes(get(match.group(0)))
        found.append({"slug": slug, "folder": name, "src": match.group(0), "file": f"heroes/{target.name}"})
        time.sleep(0.3)
    (work / "hero_banners.json").write_text(json.dumps(found, ensure_ascii=False, indent=1), encoding="utf-8")
    print("banners:", len(found), "| MB:", round(sum((work / f["file"]).stat().st_size for f in found) / 1e6, 1))


main()
