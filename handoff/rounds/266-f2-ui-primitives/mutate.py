"""Every changed display rule must turn the old-template tests red."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
UI = ROOT / "web/packages/ui/src"
SHARED = ROOT / "web/packages/shared/src"
mutations = [
    (UI / "CAvatar.vue", '  if (props.person.is_active === false) return ""', '', 'stopped avatar'),
    (UI / "CAvatar.vue", 'props.size === "md" || props.size === "lg"', 'false', 'large avatar rendition'),
    (UI / "CEmpty.vue", 'actionUrl && actionLabel', 'actionUrl', 'empty action missing label'),
    (UI / "CField.vue", 'errors[0]', 'errors[1]', 'first error'),
    (UI / "CField.vue", 'role="alert"', 'role="status"', 'error alert'),
    (UI / "CPager.vue", 'pages > 1', 'pages > 0', 'single page pager'),
    (UI / "CPager.vue", 'params.delete("page")', '// keep old page', 'query page replacement'),
    (UI / "CRank.vue", "label === '未定级'", "label === '不存在'", 'unranked fallback'),
    (UI / "CRoleIcon.vue", 'v-if="tank"', 'v-if="support"', 'role selection'),
    (UI / "CPlay.vue", 'profile.main_rank.stale', 'false', 'stale rank'),
    (UI / "CPlay.vue", 'profile.is_flex && !compact', 'false', 'flex roles'),
    (UI / "CProfileGaps.vue", 'v-if="gaps.length"', 'v-if="true"', 'empty gaps'),
    (UI / "CStatus.vue", 'success: "ok"', 'success: "done"', 'status alias'),
    (UI / "CRegStatus.vue", 'pending: "warn"', 'pending: "off"', 'registration status'),
    (SHARED / "display.ts", 'Math.min(need, 24)', 'need', 'seat cap'),
    (SHARED / "display.ts", 'roundEven(got * cells / need)', 'Math.round(got * cells / need)', 'seat halfway rounding'),
]
command = ['pnpm', '--filter', '@sjtu-ow/site', 'exec', 'vitest', 'run', 'src/ui.test.ts']
def run():
    return subprocess.run(command, cwd=ROOT / 'web', text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
base = run()
if base.returncode:
    print(base.stdout)
    raise SystemExit('baseline failed')
for path, old, new, name in mutations:
    original = path.read_text()
    assert original.count(old) >= 1, (name, old)
    try:
        path.write_text(original.replace(old, new))
        result = run()
        # Compiler failures do not demonstrate the assertion protects a rule.
        if result.returncode == 0 or 'Tests ' not in result.stdout or 'FAIL ' not in result.stdout:
            print(result.stdout)
            raise SystemExit(f'NOT CAUGHT: {name}')
        print(f'CAUGHT {name}', flush=True)
    finally:
        path.write_text(original)
final = run()
if final.returncode:
    print(final.stdout)
    raise SystemExit('restored baseline failed')
print(f'MUTATIONS-OK {len(mutations)}; restored baseline green')
