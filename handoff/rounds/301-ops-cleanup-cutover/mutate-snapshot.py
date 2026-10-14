"""Confirm the WAL regression fails when standalone snapshot conversion is removed."""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[3]
target = root / "deploy/rehearsal_input.py"
original = target.read_text()
block = """            if new.execute('PRAGMA journal_mode=DELETE').fetchone() != ('delete',):
                raise ValueError('snapshot journal conversion failed')
"""
if original.count(block) != 1:
    raise SystemExit("Expected one snapshot conversion")
try:
    target.write_text(original.replace(block, "", 1))
    result = subprocess.run([sys.executable, str(root / "deploy/test_rehearsal_input.py")], cwd=root, capture_output=True, text=True)
    Path("/srv/sjtu-ow-check/ops-301-images/snapshot-mutation.log").write_text(result.stdout + result.stderr)
    if result.returncode == 0 or "FAIL: test_snapshot_includes_committed_wal" not in result.stderr:
        raise SystemExit("Snapshot conversion mutation was not caught")
    print("SNAPSHOT-WAL-MUTATION-CAUGHT", flush=True)
finally:
    target.write_text(original)
    if target.read_text() != original:
        raise SystemExit("Snapshot helper was not restored")
print("SNAPSHOT-SOURCE-RESTORED", flush=True)
