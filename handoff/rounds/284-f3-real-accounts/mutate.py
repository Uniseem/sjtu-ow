"""Run the real journey against valid builds with two broken account rules."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[3]
runner = Path(__file__).with_name('run_real_accounts.py')
cases = [
    ('third signup attempt', 'server/internal/accounts/service.go',
     'if c.Attempts+1 >= 3 {', 'if c.Attempts+1 >= 30 {',
     'Error: third wrong signup code is discarded:'),
    ('other password sessions', 'server/internal/accounts/service.go',
     's.sessions.DeleteOthersTx(txCtx, tx, u.ID, ctx.SessionToken)',
     's.sessions.DeleteOthersTx(txCtx, tx, -u.ID, ctx.SessionToken)',
     'Error: password change retains current and revokes others:'),
]
for name, relative, old, new, expected in cases:
    source = root / relative
    original = source.read_text()
    if old not in original:
        raise SystemExit('missing mutation anchor: ' + name)
    try:
        source.write_text(original.replace(old, new, 1))
        result = subprocess.run(['uv', 'run', 'python', str(runner)], cwd=root,
                                capture_output=True, text=True)
        output = result.stdout + result.stderr
        Path(__file__).with_name('mutation-' + name.replace(' ', '-') + '.log').write_text(output)
        # An infrastructure/compile failure does not count as caught.
        if result.returncode == 0 or expected not in output:
            raise SystemExit('SURVIVED/INVALID ' + name + '\n' + output[-5000:])
        print('CAUGHT REAL ' + name, flush=True)
    finally:
        source.write_text(original)
source = root / 'server/internal/platform/mail/message.go'
original = source.read_text()
old = 'h.Set("Content-Type", contentType)'
if old not in original:
    raise SystemExit('missing MIME mutation anchor')
try:
    source.write_text(original.replace(old, 'h.Set("X-Broken-Content-Type", contentType)', 1))
    result = subprocess.run(['go', 'test', './internal/platform/mail', '-run',
                             '^TestBuildHasParseableAlternativeRelatedMIME$', '-count=1'],
                            cwd=root / 'server', capture_output=True, text=True)
    output = result.stdout + result.stderr
    if result.returncode == 0 or 'top-level MIME header missing or invalid:' not in output:
        raise SystemExit('SURVIVED/INVALID MIME header\n' + output)
    print('CAUGHT MIME top-level header', flush=True)
finally:
    source.write_text(original)
print('REAL-ACCOUNT-MUTATIONS-OK ' + str(len(cases) + 1), flush=True)
