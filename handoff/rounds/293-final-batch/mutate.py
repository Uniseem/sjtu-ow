"""New boundary mutations; assertion failures required, restore unconditionally."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
CASES = [
    ('provider echo code', 'server/internal/platform/storage/s3.go', r'body.Code = ""', 'body.Code = strings.TrimSpace(body.Code)', ['go','test','./internal/platform/storage','-run','TestProviderCannotEcho','-count=1'], 'server'),
    ('contacts transaction uniqueness', 'server/internal/accounts/service.go', r'if count > 0 \{\s*return api.InvalidFields\(map\[string\]\[\]string\{"type": \{"每种联系方式只能填写一次。"\}\}\)\s*\}', 'if false { return api.InvalidFields(map[string][]string{"type": {"每种联系方式只能填写一次。"}}) }', ['go','test','./internal/accounts','-run','TestContactCreationRechecks','-count=1'], 'server'),
    ('contact actor stays active', 'server/internal/accounts/service.go', r'// Recheck uniqueness under the writer lock\. Concurrent tabs must receive\s*// the ordinary field rejection, not leak a SQLite constraint as a 500\.\s*if err := s.patchActor\(ctx, txCtx, tx\); err != nil \{\s*return err\s*\}', 'if false { return api.Unauthorized("inactive") }', ['go','test','./internal/accounts','-run','TestContactCreationCannotRestoreData','-count=1'], 'server'),
    ('legacy missing-table gate', 'server/internal/ops/reconcile.go', r'stat.Status\s*=\s*"LEGACY_QUERY_FAILED"\s*result.OverallOK\s*=\s*false', 'stat.Status = "LEGACY_QUERY_FAILED"; result.OverallOK = true', ['go','test','./internal/ops','-run','TestReconcileMissingLegacyTables','-count=1'], 'server'),
    ('published article count', 'server/internal/ops/reconcile.go', r'SELECT count\(\*\) FROM articles a JOIN pages p ON p.id=a.page_id WHERE p.live=1', 'SELECT count(*) FROM articles a JOIN pages p ON p.id=a.page_id WHERE 0', ['go','test','./internal/ops','-run','TestReconcilePublishedArticles','-count=1'], 'server'),
    ('unsubscribe status', 'web/apps/site/src/pages/Unsubscribe.vue', r'status: 404, subscription: null', 'status: 200, subscription: null', ['pnpm','exec','vitest','run','src/handle.test.ts'], 'web/apps/site'),
    ('current font CSS is accepted', 'web/packages/shared/src/font-css.ts', r'\|\[a-f0-9\]\{20\}', '', ['pnpm','exec','vitest','run','src/font-css.test.ts'], 'web/apps/site'),
    ('private metadata', 'web/apps/site/src/meta.ts', r'return /\^\\/\(me\|accounts\|letters\|admin\|unsubscribe\)\(\\/\|\$\)/\.test\(path\)', 'return false', ['pnpm','exec','vitest','run','src/meta.test.ts'], 'web/apps/site'),
]


def main():
    for index, (name, filename, pattern, replacement, command, cwd) in enumerate(CASES):
        path=ROOT/filename
        original=path.read_text()
        damaged, count=re.subn(pattern,lambda _:replacement,original)
        if count!=1: raise RuntimeError(f'nonunique mutation {name}: {count}')
        log=Path('/tmp')/f'sjtuow-293-mutation-{index}.log'
        try:
            path.write_text(damaged)
            with log.open('w') as output:
                result=subprocess.run(command,cwd=ROOT/cwd,stdout=output,stderr=subprocess.STDOUT,timeout=240)
            evidence=log.read_text()
            if result.returncode==0 or not ('--- FAIL:' in evidence or 'AssertionError' in evidence) or 'build failed' in evidence:
                raise RuntimeError(f'mutation did not fail assertions: {name}\n'+evidence[-4000:])
            print('MUTATION-CAUGHT '+name,flush=True)
        finally:
            path.write_text(original)
    print('MUTATIONS-293-OK '+str(len(CASES)),flush=True)


if __name__=='__main__': main()
