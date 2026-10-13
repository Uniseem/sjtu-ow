"""Prove delayed unload permission is tested, without a compilation failure."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
path = ROOT / 'web/packages/shared/src/leave.ts'
original = path.read_text()
before = 'programmatic = true\n'
if original.count(before) != 1:
    raise RuntimeError('nonunique unload mutation')
log = ROOT.parent / '298-web-mutation.log'
try:
    path.write_text(original.replace(before, before + '  setTimeout(() => { programmatic = false }, 0)\n'))
    with log.open('w') as output:
        result = subprocess.run(['pnpm', 'exec', 'vitest', 'run', 'packages/shared/leave.test.ts'],
                                cwd=ROOT/'web', stdout=output, stderr=subprocess.STDOUT, timeout=180)
    evidence = log.read_text()
    if result.returncode == 0 or 'AssertionError' not in evidence or 'Transform failed' in evidence:
        raise RuntimeError('delayed unload mutation did not fail assertions: ' + evidence[-2000:])
    print('WEB-MUTATION-CAUGHT delayed mandatory unload')
finally:
    path.write_text(original)
