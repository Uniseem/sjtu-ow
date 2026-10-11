"""Run only on the test machine; restore every mutation before returning."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[3]
cases = [
    ('changed fields only', 'web/packages/shared/src/autosave.ts',
     'body: { base_version: this.version, changes },',
     'body: { base_version: this.version, changes: copy(this.values) },'),
    ('same retry key', 'web/packages/shared/src/autosave.ts',
     'this.options.transport(copy(flight.body), flight.key, flight.controller.signal)',
     'this.options.transport(copy(flight.body), this.newKey(), flight.controller.signal)'),
    ('missing version blocks writes', 'web/packages/shared/src/autosave.ts',
     'if (this.options.available && !this.options.available())',
     'if (false)'),
    ('pixel limit before decode', 'web/apps/site/src/image-inspect.ts',
     'if (width * height > MAX_PIXELS)', 'if (false)'),
    ('receipt contradictions rejected', 'web/packages/shared/src/save-receipt.ts',
     'if (saved.some((name) => fields[name]?.length)) invalid()',
     'if (false) invalid()'),
]
for number, (name, relative, before, after) in enumerate(cases):
    path = root / relative
    original = path.read_text()
    if original.count(before) != 1:
        raise RuntimeError('mutation target is not unique: ' + name)
    log = Path('/tmp/sjtuow-289-mutation-%d.log' % number)
    try:
        path.write_text(original.replace(before, after))
        with log.open('w') as output:
            result = subprocess.run(
                ['pnpm', 'exec', 'vitest', 'run', 'src/autosave.test.ts',
                 'src/image-inspect.test.ts', 'src/personal.test.ts'],
                cwd=root / 'web/apps/site', stdout=output,
                stderr=subprocess.STDOUT, timeout=90,
            )
        if result.returncode == 0:
            raise RuntimeError('mutation escaped: ' + name)
        if 'FAIL' not in log.read_text():
            raise RuntimeError('mutation did not fail an assertion: ' + name)
        print('MUTATION-CAUGHT ' + name, flush=True)
    finally:
        path.write_text(original)
print('MUTATIONS-OK 5', flush=True)
