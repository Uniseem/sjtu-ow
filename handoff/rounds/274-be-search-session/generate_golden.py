"""Generate independent search examples with the frozen Django implementation."""
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
from search.services import excerpt, matches, parse_query

samples = [
    ("  截图  社区  ", "截图\n社区 **文字**"),
    ("STRASSE", "<b>Straße</b>社团"),
    ("Σίσυφοσ", "Σίσυφος"),
    ("İ", "İstanbul"),
    ("ﬃ", "OFFICE ffi"),
    ("关键词", "前" * 60 + "关键词" + "后" * 70),
    ("不存在", "开头" * 55),
    ("关键词", "短句关键词"),
    ("后 前", "前" * 45 + "后" * 80),
    ("alpha bravo charlie delta echo ignored", "ALPHA bravo charlie delta echo"),
    ("词" * 51, "词" * 50),
    ("\x1cDVA\x1f", " Dva <em>少女</em> &amp;  战队 "),
    ("\t \n", "任何内容"),
]
rows = []
for raw, text in samples:
    terms = parse_query(raw)
    rows.append({"raw":raw,"text":text,"query":raw.strip()[:50],"terms":terms,"excerpt":excerpt(text,terms),"matches":matches(text,terms)})
p = root / "server/internal/search/testdata/legacy_search.json"
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
print(f"LEGACY-GOLDEN {len(rows)}")
