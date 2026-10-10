"""Check that the old-template references protect the new display rules."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
UI = ROOT / 'web/packages/ui/src'
SHARED = ROOT / 'web/packages/shared/src'
mutations = [
    (SHARED / 'pictures.ts', 'tournament: 13', 'tournament: 0', 'tournament cover offset'),
    (SHARED / 'pictures.ts', '"cover-33.svg"', '"cover-01.svg"', 'members night picture'),
    (SHARED / 'time.ts', '+08:00`', '+00:00`', 'Shanghai datetime offset'),
    (UI / 'PostCard.vue', 'summary && article.summary', 'article.summary', 'summary opt-in'),
    (UI / 'PostCard.vue', 'pinned || article.pinned', 'false', 'pinned article tag'),
    (UI / 'TeamTile.vue', 'v-else-if="showClosed"', 'v-else-if="true"', 'closed team opt-in'),
    (UI / 'CTournamentCard.vue', 'approved != null', 'approved', 'zero approved count'),
    (UI / 'CTournamentCard.vue', "tournament.takes_individuals ? '已编成' : '已通过'", "'已通过'", 'individual teams wording'),
    (UI / 'CScrimRow.vue', "scrim.status === 'cancelled'", 'false', 'cancelled signup priority'),
    (UI / 'CStartsAt.vue', 'v-if="startsAt"', 'v-if="true"', 'unknown starting time'),
    (UI / 'MeLayout.vue', 'v-if="item.available"', 'v-if="true"', 'unavailable personal navigation'),
    (UI / 'MeLayout.vue', 'v-if="waiting"', 'v-if="false"', 'waiting letters reminder'),
    (UI / 'MeLayout.vue', 'v-if="gaps.length"', 'v-if="false"', 'incomplete profile warning'),
]
command = ['pnpm', '--filter', '@sjtu-ow/site', 'exec', 'vitest', 'run', 'src/ui.test.ts']
def run():
    return subprocess.run(command, cwd=ROOT / 'web', text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
base = run()
if base.returncode:
    print(base.stdout)
    raise SystemExit('baseline failed')
for path, old, new, name in mutations:
    original = path.read_text()
    assert old in original, (name, old)
    try:
        path.write_text(original.replace(old, new))
        result = run()
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
