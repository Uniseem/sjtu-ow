"""Remove only private build-cache records linked to identified SJTU-OW steps."""
import json
from pathlib import Path
import re
import shutil
import subprocess

root = Path("/srv/sjtu-ow")
before = shutil.disk_usage(root)
rows = [json.loads(line) for line in Path("/root/sjtu-ow-301-build-cache.jsonl").read_text().splitlines()]
by_id = {row["ID"]: row for row in rows}
markers = ("@sjtu-ow/", "/srv/sjtuow", "/app/web/apps/site", "fetch_tailwind_cli.py", "/app/deploy/entrypoint-web.sh", "COPY web/", "COPY server/")
linked = {row["ID"] for row in rows if any(marker in row["Description"] for marker in markers)}
while True:
    expanded = linked | {parent for key in linked for parent in (by_id.get(key, {}).get("Parents") or [])}
    expanded |= {row["ID"] for row in rows if set(row.get("Parents") or []) & linked}
    if expanded == linked:
        break
    linked = expanded
selected = sorted(key for key in linked if key in by_id and by_id[key]["Reclaimable"] and not by_id[key]["Shared"])
if not selected:
    raise SystemExit("No confirmed project-private cache records")
for key in selected:
    row = by_id[key]
    print("PROJECT-CACHE", key, row["Size"], row["Description"], flush=True)
Path("/root/sjtu-ow-301-cache-selection.json").write_text(json.dumps([by_id[key] for key in selected], indent=2))
# Protect the actual live legacy images before any space cleanup.
for service in ("web", "worker"):
    ids = subprocess.check_output(["docker", "ps", "-q", "--filter", "label=com.docker.compose.project=sjtu-ow", "--filter", "label=com.docker.compose.service=" + service], text=True).split()
    if len(ids) != 1:
        raise SystemExit("Expected one live legacy " + service)
    image = subprocess.check_output(["docker", "inspect", "--format", "{{.Image}}", ids[0]], text=True).strip()
    subprocess.run(["docker", "tag", image, "sjtu-ow-" + service + ":legacy"], check=True)
pattern = "id~=^(" + "|".join(re.escape(key) for key in selected) + ")$"
subprocess.run(["docker", "buildx", "prune", "--force", "--all", "--filter", pattern], check=True)
after = shutil.disk_usage(root)
print("PROJECT-CLEANUP-RESULT", json.dumps({"records_selected": len(selected), "free_before": before.free, "free_after": after.free, "reclaimed": after.free - before.free, "free_percent": round(after.free / after.total * 100, 2), "gate": after.free / after.total >= .25 and after.free >= 5 * 1024**3}), flush=True)
