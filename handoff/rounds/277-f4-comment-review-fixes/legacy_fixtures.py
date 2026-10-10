"""Regenerate frozen old-template references, then use the real Go JSON key."""
from pathlib import Path
import json
import runpy

root = Path(__file__).resolve().parents[3]
runpy.run_path(str(root / "handoff/rounds/275-f4-articles-home/legacy_fixtures.py"), run_name="__main__")
p = root / "web/apps/site/src/testdata/legacy-comments.json"
rows = json.loads(p.read_text())
for row in rows:
    thread = row["props"].get("thread")
    if thread and "pageSize" in thread:
        row["props"]["thread"] = {("page_size" if key == "pageSize" else key): value for key, value in thread.items()}
p.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
print(f"LEGACY-COMMENTS Go page_size: {len(rows)} references")
