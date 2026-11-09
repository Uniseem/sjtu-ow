"""Remove the exit phase in an isolated copy; the real unit assertion must fail."""
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]
output = ROOT.parent / "305-toast-mutation.log"
with tempfile.TemporaryDirectory(prefix="305-toast-mutant-", dir=ROOT.parent) as temporary:
    work = Path(temporary)
    source = work / "src"
    source.mkdir()
    site = ROOT / "web/apps/site"
    for name in ["behaviour.test.ts", "loadbar.ts", "contextmenu-entries.ts", "toasts.ts"]:
        shutil.copyfile(site / "src" / name, source / name)
    shutil.copyfile(site / "package.json", work / "package.json")
    (work / "node_modules").symlink_to(site / "node_modules", target_is_directory=True)
    toast = source / "toasts.ts"
    original = toast.read_text()
    target = "leave(); exiting = setTimeout(remove, REMOVE_AFTER)"
    assert original.count(target) == 1
    toast.write_text(original.replace(target, "leave(); remove()"))
    result = subprocess.run(["node", str(site / "node_modules/vitest/vitest.mjs"), "run", "src/behaviour.test.ts"], cwd=work, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output.write_text(result.stdout)
    assert result.returncode == 1 and "a toast appears and leaves on its own" in result.stdout and "expected +0 to be 2" in result.stdout, result.stdout
    print(f"MUTANT-CAUGHT toast immediate removal: test exit={result.returncode}; {output}")
