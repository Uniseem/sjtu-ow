"""Each broken account behavior must build and fail a real SSR contract."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[3]
site = root / 'web/apps/site'
cases = [
    ('extra reset action', 'src/pages/PasswordResetCode.vue', '  </AuthLayout>',
     '    <form><button type="submit">重新发送验证码</button></form>\n  </AuthLayout>', 'reset code page matches'),
    ('guest logout', 'src/pages/Logout.vue', 'if (!(await ctx.viewer()).user)', 'if (false)', 'logout GET redirects'),
    ('authenticated login code', 'src/routes.ts',
     'redirected("/accounts/login/code/confirm/", "/accounts/login/", 302, { guest: true })',
     'redirected("/accounts/login/code/confirm/", "/accounts/login/", 302)', 'unused login-code'),
]
for name, relative, anchor, broken, test_name in cases:
    source = site / relative
    original = source.read_text()
    if anchor not in original:
        raise SystemExit('missing anchor ' + name)
    try:
        source.write_text(original.replace(anchor, broken, 1))
        built = subprocess.run(['pnpm', 'exec', 'vite', 'build', '--ssr', 'server.ts', '--outDir', 'dist/mutation-285'], cwd=site, capture_output=True, text=True)
        if built.returncode:
            raise SystemExit('INVALID mutation: ' + built.stdout + built.stderr)
        result = subprocess.run(['pnpm', 'exec', 'vitest', 'run', 'src/accounts.test.ts', '-t', test_name], cwd=site, capture_output=True, text=True)
        if result.returncode == 0 or 'AssertionError:' not in result.stdout + result.stderr:
            raise SystemExit('SURVIVED/INVALID ' + name + '\n' + result.stdout + result.stderr)
        print('CAUGHT ' + name + ' (valid SSR build)', flush=True)
    finally:
        source.write_text(original)
print('ACCOUNT-WEB-MUTATIONS-OK ' + str(len(cases)), flush=True)
