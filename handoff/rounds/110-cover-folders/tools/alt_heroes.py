"""Hero folder from the English file name in a picture's alt text."""
import json
import re
from pathlib import Path

banners = json.loads(Path("work/hero_banners.json").read_text(encoding="utf-8"))
NAMES = {b["slug"].replace("-", ""): b["folder"] for b in banners}
NAMES.update({
    "dva": "D.Va", "soldier76": "士兵：76", "soldier": "士兵：76", "seventysix": "士兵：76", "rein": "莱因哈特",
    "life": "生命之梭", "fist": "末日铁拳", "torb": "托比昂", "jq": "渣客女王", "junkerqueen": "渣客女王",
    "hammond": "破坏球", "wreckingball": "破坏球", "zen": "禅雅塔", "widow": "黑百合", "sym": "秩序之光",
    "cass": "卡西迪", "mccree": "卡西迪", "bap": "巴蒂斯特", "brig": "布丽吉塔", "rama": "拉玛刹",
    "sombra": "黑影", "kiri": "雾子", "illari": "伊拉锐", "reinhardt": "莱因哈特",
})
GROUP = re.compile(r"bundle|lineup|line_up|group|collection|duo|trio|squad|team|heroes|battlepass|allheroes|cast", re.I)
WORD = re.compile(r"[A-Za-z0-9]+")


def heroes_in(alt):
    found = []
    text = alt.replace("Soldier_76", "Soldier76").replace("Soldier-76", "Soldier76").replace("Junker_Queen", "JunkerQueen")
    text = text.replace("Wrecking_Ball", "WreckingBall").replace("WreckingBall", "WreckingBall")
    split = re.sub(r"([A-Z])([A-Z][a-z])", r"\1_\2", re.sub(r"([a-z])([A-Z])", r"\1_\2", text))
    for word in WORD.findall(split) + WORD.findall(text):
        name = NAMES.get(word.lower())
        if name and name not in found:
            found.append(name)
    # Longer names also inside run-together words (CyberDJLucio2, Jetpack%20Cat).
    flat = re.sub(r"%20|[^a-z]", "", alt.lower())
    for key, name in NAMES.items():
        if len(key) >= 5 and key in flat and name not in found:
            found.append(name)
    return found


def hero_for(alt):
    if GROUP.search(alt):
        return None
    found = heroes_in(alt)
    return found[0] if len(found) == 1 else None
