"""Destination equality is semantic, but may not drop origins or next values."""
from pathlib import Path
import importlib.util
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / 'e2e/parity'))
spec = importlib.util.spec_from_file_location('parity_under_test', root / 'e2e/parity/parity.py')
parity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parity)
assert not parity.redirect_problems(((302, '/accounts/login/?next=/me/'), (302, '/accounts/login/?next=%2Fme%2F')))
assert parity.redirect_problems(((302, '/accounts/login/?next=/me/'), (302, '/accounts/login/?next=/admin/'))), 'changed next was accepted'
assert parity.redirect_problems(((302, '/me/'), (302, 'https://external.test/me/'))), 'external destination was accepted'
assert parity.redirect_problems(((301, '/me/'), (302, '/me/'))), 'different redirect code was accepted'
empty = {'title': '', 'text': [], 'links': [], 'fields': [], 'broken': []}
assert parity.compare(empty, empty, 0, (500, 500)), 'two identical 500s were accepted'
with_error = {**empty, 'browser_errors': ['CSP violation']}
assert parity.compare(empty, with_error, 0, (200, 200)), 'new browser error was accepted'
assert parity.compare(with_error, empty, 0, (200, 200)), 'old browser error was accepted'
allowed = ((302, '/accounts/password/change/'), (301, '/me/security/'))
assert parity.approved_redirect('password-set', 'member', allowed)
assert not parity.approved_redirect('password-set', 'visitor', allowed)
assert not parity.approved_redirect('password-set', 'member', ((302, '/accounts/password/change/'), (301, '/admin/')))
assert not parity.approved_redirect('password-change', 'member', allowed)

class RedirectServer(BaseHTTPRequestHandler):
    def do_GET(self):
        target = 'https://external.test/target/' if self.path == '/external' else f'http://127.0.0.1:{self.server.server_port}/target/?next=/me/'
        self.send_response(302)
        self.send_header('Location', target)
        self.end_headers()

    def log_message(self, *_args):
        pass

server = ThreadingHTTPServer(('127.0.0.1', 0), RedirectServer)
threading.Thread(target=server.serve_forever, daemon=True).start()
try:
    base = f'http://127.0.0.1:{server.server_port}'
    assert parity.fetch_status(base + '/internal', None) == (302, '/target/?next=/me/')
    assert parity.fetch_status(base + '/external', None) == (302, 'https://external.test/target/'), 'external Location origin stripped'
finally:
    server.shutdown()
    server.server_close()
print('PARITY-GUARDS-OK destinations/encoding/origin/server-errors', flush=True)

if '--mutate' in sys.argv:
    source = root / 'e2e/parity/parity.py'
    original = source.read_text()
    cases = [
        ('destination', 'canonical_location(old[1]) != canonical_location(new[1])', 'False', 'changed next was accepted'),
        ('external origin', 'if (target.scheme, target.netloc) == (origin.scheme, origin.netloc):', 'if True:', 'external Location origin stripped'),
        ('two server errors', 'any(code >= 500 for code in status)', 'False', 'two identical 500s were accepted'),
        ('browser errors', "value.get('browser_errors')", 'False', 'new browser error was accepted'),
    ]
    for name, anchor, broken, expected in cases:
        assert anchor in original
        try:
            source.write_text(original.replace(anchor, broken, 1))
            result = subprocess.run([sys.executable, __file__], capture_output=True, text=True)
            if result.returncode == 0 or expected not in result.stderr:
                raise SystemExit('SURVIVED/INVALID ' + name + '\n' + result.stdout + result.stderr)
            print('CAUGHT ' + name, flush=True)
        finally:
            source.write_text(original)
