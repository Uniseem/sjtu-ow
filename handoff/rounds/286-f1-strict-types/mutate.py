"""Runtime/security regressions must detect valid builds with broken rules."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[3]
cases = [
    ('password hash serialization', 'server/internal/accounts/model.go', 'string `json:"-"`', 'string',
     ['go', 'test', './internal/accounts', '-run', '^TestUserDetailJSONOmitsPasswordHash$', '-count=1'], root/'server', 'user detail JSON exposed the password hash'),
    ('comment article slug', 'server/internal/comments/store.go', "COALESCE(p.slug, '')", "''",
     ['go', 'test', './internal/comments', '-run', '^TestAdminCommentProjectionHasActualArticleSlug$', '-count=1'], root/'server', 'admin comment link projection incorrect'),
    ('user roles projection', 'server/internal/accounts/service.go', 'Roles:            roles,', 'Roles:            roles[:0],',
     ['go', 'test', './internal/accounts', '-run', 'TestAdmin', '-count=1'], root/'server', 'user list omitted assigned roles'),
]
for name, relative, anchor, broken, command, cwd, expected in cases:
    source = root / relative
    original = source.read_text()
    if anchor not in original:
        raise SystemExit('missing anchor ' + name)
    try:
        source.write_text(original.replace(anchor, broken, 1))
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
        if result.returncode == 0 or expected not in result.stdout + result.stderr:
            raise SystemExit('SURVIVED/INVALID ' + name + '\n' + result.stdout + result.stderr)
        print('CAUGHT ' + name, flush=True)
    finally:
        source.write_text(original)
print('TYPE-RUNTIME-MUTATIONS-OK ' + str(len(cases)), flush=True)
