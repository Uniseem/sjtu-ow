"""Assertion-level probes for this round's confirmed security/state fixes."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
CASES = [
    ('occupied email disclosure', 'server/internal/accounts/service.go',
     'occupied := existing != nil && existing.ID != u.ID',
     'occupied := existing != nil && existing.ID != u.ID && false',
     './internal/accounts', 'TestReauthenticateAndEmailChange'),
    ('Google display name budget', 'server/internal/fonts/package.go',
     'utf8.RuneCountInString(in.DisplayName) > 64',
     'utf8.RuneCountInString(in.DisplayName) > 1000',
     './internal/fonts', 'TestGoogleImportKeepsSelectedWeightsAndDisplayName'),
    ('scheduled approval marker', 'server/internal/content/store.go',
     'UPDATE page_revisions SET approved_go_live_at=? WHERE id=? AND page_id=?',
     'UPDATE page_revisions SET approved_go_live_at=NULL WHERE id=? AND page_id=?',
     './internal/content', 'TestRealArticlePublishApprovesScheduledRevisionAndImmediatePublishClearsIt'),
]
for index, (name, file, before, after, package, test) in enumerate(CASES):
    path = ROOT / file
    original = path.read_text()
    if original.count(before) != 1:
        raise RuntimeError('nonunique mutation: ' + name)
    log = ROOT.parent / f'298-mutation-{index}.log'
    try:
        damaged = original.replace(before, after)
        if name == 'scheduled approval marker':
            # Preserve SQL argument arity while discarding the actual approval.
            damaged = damaged.replace(after, 'UPDATE page_revisions SET approved_go_live_at=NULL WHERE ? IS NOT NULL AND id=? AND page_id=?')
        path.write_text(damaged)
        with log.open('w') as output:
            result = subprocess.run(['go', 'test', package, '-run', test, '-count=1'], cwd=ROOT/'server', stdout=output, stderr=subprocess.STDOUT, timeout=240)
        evidence = log.read_text()
        if result.returncode == 0 or '--- FAIL:' not in evidence or 'build failed' in evidence:
            raise RuntimeError('probe did not fail assertions: ' + name + '\n' + evidence[-2000:])
        print('MUTATION-CAUGHT ' + name, flush=True)
    finally:
        path.write_text(original)
print('MUTATIONS-298-OK ' + str(len(CASES)), flush=True)
