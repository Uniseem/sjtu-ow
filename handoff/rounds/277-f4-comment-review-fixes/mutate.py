"""Run on the test machine. Each frontend mutant must build, then fail a
meaningful SSR or Chromium regression. Infrastructure timeouts aren't caught
mutations. Restore source and the production build before the final baseline.
"""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[3]
site = root / "web/apps/site"
mutations = [
    ("like event", "web/apps/site/src/pages/ArticleDetail.vue", '@like="onLike"', "", "browser"),
    ("native confirmation", "web/packages/shared/src/confirm.ts", "window.confirm(message)", "false", "browser"),
    ("Go pagination key", "web/packages/ui/src/CComments.vue", "props.thread.page_size", "props.thread.pageSize", "ssr"),
    ("reset thread on navigation", "web/apps/site/src/pages/ArticleDetail.vue", "thread.value = data?.thread ?? { total: 0, page: 1, page_size: 20, comments: [] }", "thread.value = thread.value", "browser"),
    ("old response guard", "web/apps/site/src/pages/ArticleDetail.vue", "if (started !== epoch || sequence !== readSequence) return", "if (false) return", "browser"),
    ("pending submit guard", "web/packages/ui/src/CCommentComposer.vue", "if (pending.value) return", "if (false) return", "browser"),
    ("empty article render guard", "web/apps/site/src/pages/ArticleDetail.vue", '<main v-if="article"', '<main v-if="true"', "browser"),
    ("live header count", "web/apps/site/src/pages/ArticleDetail.vue", "{{ thread.total }}", "{{ data.thread.total }}", "browser"),
]
for name, rel, old, new, kind in mutations:
    p = root / rel
    baseline = p.read_text()
    if old not in baseline:
        raise SystemExit(f"Missing mutation anchor: {name}")
    try:
        p.write_text(baseline.replace(old, new))
        build = subprocess.run(["pnpm", "build"], cwd=site, capture_output=True, text=True)
        if build.returncode:
            raise SystemExit(f"INVALID BUILD {name}\n{build.stderr[-2500:]}")
        command = ["pnpm", "exec", "vitest", "run", "src/content.test.ts", "src/ui.test.ts"] if kind == "ssr" else ["node", "comments-browser-check.mjs", "/usr/bin/chromium"]
        result = subprocess.run(command, cwd=site, capture_output=True, text=True, timeout=100)
        if result.returncode == 0:
            raise SystemExit(f"SURVIVED {name}")
        if "CDP timeout" in result.stderr:
            raise SystemExit(f"INFRASTRUCTURE FAILURE {name}\n{result.stderr}")
        print(f"CAUGHT {name}", flush=True)
        reasons = [line for line in (result.stdout + result.stderr).splitlines() if line.startswith("FAIL ") or "wait failed:" in line or "AssertionError" in line]
        print("\n".join(reasons[-3:]), flush=True)
    finally:
        p.write_text(baseline)
# Never leave a mutant dist bundle for the following smoke tests.
subprocess.run(["pnpm", "build"], cwd=site, check=True, stdout=subprocess.DEVNULL)
print(f"MUTATIONS-OK {len(mutations)}", flush=True)
