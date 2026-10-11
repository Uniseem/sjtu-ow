"""Count implementation additions against the opening commit; no generated/test padding."""
from pathlib import Path
import difflib
import json
import subprocess

root = Path(__file__).resolve().parents[3]
baseline = "54f98d2071fe2a7a37396be0e50bc8e6fa89452c"
moves = {
 "web/packages/shared/src/leave.ts": "web/apps/site/src/unsaved.ts",
 "web/packages/shared/src/mutation.ts": "web/apps/site/src/use-mutation.ts",
 "web/packages/shared/src/use-autosave.ts": "web/apps/site/src/use-autosave.ts",
 "web/packages/shared/src/letters.ts": "web/apps/site/src/letters.ts",
 "web/packages/shared/src/letter-schema.ts": "web/apps/site/src/letter-schema.ts",
}
rows = []
for scope in ("server", "web"):
 for path in (root / scope).rglob("*"):
  if not path.is_file() or path.suffix not in (".go", ".sql", ".ts", ".vue", ".css", ".py", ".mjs"): continue
  if any(part in ("node_modules", "dist", ".git", "gen") for part in path.parts): continue
  if any(marker in path.name for marker in ("_test.", ".test.", ".spec.", "browser-check", "budget", "guard")) or path.name.startswith("test_"): continue
  relative = str(path.relative_to(root))
  original = moves.get(relative, relative)
  old = subprocess.run(["git", "show", baseline + ":" + original], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True).stdout.splitlines()
  new = path.read_text().splitlines()
  added = removed = 0
  for tag, left, end_left, right, end_right in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
   if tag in ("replace", "insert"): added += end_right - right
   if tag in ("replace", "delete"): removed += end_left - left
  if added or removed: rows.append({"file": relative, "added_implementation": added, "removed_in_changed_files": removed, "moved_baseline": moves.get(relative)})
rows.sort(key=lambda row: row["file"])
result = {"baseline": baseline, "method": "Actual line additions/rewrites versus opening commit; relocated code compared to original paths. Tests, docs, generated outputs, lockfiles, dependencies and build artifacts excluded. Deleting obsolete stubs does not count toward additions.", "added_implementation": sum(row["added_implementation"] for row in rows), "removed_in_changed_files": sum(row["removed_in_changed_files"] for row in rows), "changed_implementation_files": len(rows), "files": rows}
Path(__file__).with_name("code-lines.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(result["added_implementation"], result["changed_implementation_files"])
