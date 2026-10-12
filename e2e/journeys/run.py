"""Real Go, persistent worker, captured SMTP, production SSR/admin and Caddy.

Only fictional .test data. The same seed identities and page matrix are used
by visual parity. Each invocation builds a new isolated database.
"""
from pathlib import Path
from email import policy
from email.parser import BytesParser
import json
import os
import re
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'e2e/parity'))
import parity
from page_matrix import PAGES, APPROVED_ADDITIONS
from account_scenarios import ADDRESSES, ROLES


def main(mode, engine):
    work = Path(tempfile.mkdtemp(prefix='sjtuow-real-journey-'))
    parity.WORK = work
    parity.OUT = work / 'out'
    parity.SHOTS = parity.OUT / 'shots'
    parity.screens.WORK = work
    processes = []
    container = 'ow-parity-caddy'
    smtp = None
    success = False

    class Mailbox(socketserver.StreamRequestHandler):
        def handle(self):
            self.wfile.write(b'220 test SMTP\r\n')
            recipient = ''
            while line := self.rfile.readline():
                command = line.decode().strip()
                upper = command.upper()
                if upper.startswith(('EHLO', 'HELO')):
                    self.wfile.write(b'250 localhost\r\n')
                elif upper.startswith('RCPT TO:'):
                    recipient = command.split(':', 1)[1].strip().strip('<>')
                    self.wfile.write(b'250 OK\r\n' if recipient.endswith('.test') else b'550 test addresses only\r\n')
                elif upper == 'DATA':
                    self.wfile.write(b'354 Send message\r\n')
                    parts = []
                    while (part := self.rfile.readline()) not in (b'.\r\n', b''):
                        parts.append(part[1:] if part.startswith(b'..') else part)
                    message = BytesParser(policy=policy.default).parsebytes(b''.join(parts))
                    plain = message.get_body(preferencelist=('plain',))
                    valid = message.get_content_type() == 'multipart/alternative' and bool(plain)
                    codes = re.findall(r'验证码：([0-9]{6})(?![0-9])', plain.get_content() if valid else '')
                    with (work / 'mailbox.jsonl').open('a') as output:
                        output.write(json.dumps({'to': recipient, 'subject': str(message['Subject']), 'valid_mime': valid, 'code': codes[0] if codes else None}) + '\n')
                    self.wfile.write(b'250 accepted\r\n')
                elif upper == 'QUIT':
                    self.wfile.write(b'221 Bye\r\n')
                    break
                else:
                    self.wfile.write(b'250 OK\r\n')

    try:
        parity.SHOTS.mkdir(parents=True)
        os.environ['DJANGO_SECRET_KEY'] = parity.TEST_SIGNING_KEY
        os.environ['SITE_URL'] = parity.TEST_SITE_URL
        data = parity.prepare_legacy(True)
        old, api, ssr, caddy = [parity.screens.free_port() for _ in range(4)]
        env = parity.new_env(api)
        env['SITE_URL'] = f'http://127.0.0.1:{caddy}'
        sessions = parity.prepare_new(env)
        smtp = socketserver.ThreadingTCPServer(('127.0.0.1', 0), Mailbox)
        smtp.daemon_threads = True
        threading.Thread(target=smtp.serve_forever, daemon=True).start()
        env.update(SMTP_HOST='127.0.0.1', SMTP_PORT=str(smtp.server_address[1]), SMTP_FROM='site@example.test', SMTP_SECURITY='plain', SMTP_USER='', SMTP_PASSWORD='', EMAIL_ALLOWLIST='')
        processes.append(subprocess.Popen([str(work / 'sjtuow'), 'worker'], env=env, stdout=(work / 'worker.log').open('w'), stderr=subprocess.STDOUT))
        processes.append(subprocess.Popen([sys.executable, 'manage.py', 'runserver', f'127.0.0.1:{old}', '--noreload'], cwd=ROOT, env=parity.screens.site_env(), stdout=(work / 'old.log').open('w'), stderr=subprocess.STDOUT))
        # start_new must see SMTP env too; all services stay local to this fixture.
        processes.extend(parity.start_new(env, api, ssr, caddy))
        base = env['SITE_URL']
        parity.screens.wait_for(base + '/robots.txt')
        parity.screens.wait_for(f'http://127.0.0.1:{old}/robots.txt')
        pages = []
        account_pages=[(name,role,path) for name,path in ADDRESSES for role in ROLES]
        for name, role, template in PAGES + account_pages:
            path = template.format(**data)
            cookie = 'sessionid=' + data['sessions'][role] if role in data['sessions'] else ''
            reference_path = APPROVED_ADDITIONS[name][1].format(**data) if name in APPROVED_ADDITIONS else path
            status, location = parity.fetch_status(f'http://127.0.0.1:{old}' + __import__('urllib.parse', fromlist=['quote']).quote(reference_path, safe='/?=&#%'), cookie)
            if name in APPROVED_ADDITIONS and 300 <= status < 400:
                location = '/accounts/login/?' + __import__('urllib.parse', fromlist=['urlencode']).urlencode({'next': path})
            if name.startswith('admin-article-revision') and status == 403:
                status = 404
            if name in ('admin-article', 'admin-article-preview') and status == 403:
                status = 404
            pages.append({'name': name, 'role': role, 'path': path, 'status': status, 'location': location})
        config = work / 'config.json'
        config.write_text(json.dumps({'base': base, 'old_base':f'http://127.0.0.1:{old}', 'work':str(work), 'legacy_env':parity.screens.site_env(), 'mailbox': str(work / 'mailbox.jsonl'), 'database': str(work / 'new-data/sjtuow.sqlite3'), 'sessions': sessions, 'data': data, 'pages': pages}))
        subprocess.run(['node', str(ROOT / 'scripts/journey.mjs'), mode, '--fixture=' + str(config), '--engine=' + engine], cwd=ROOT, check=True)
        success = True
    finally:
        subprocess.run(['docker', 'rm', '-f', container], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for process in processes:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        if smtp:
            smtp.shutdown()
            smtp.server_close()
        if success:
            retired = work.with_name(work.name + '-retired')
            work.rename(retired)
            shutil.rmtree(retired)
            print('JOURNEY-FIXTURE-REMOVED', flush=True)
        else:
            print('JOURNEY-FAILED-FIXTURE-KEPT ' + str(work), flush=True)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'newbie', sys.argv[2] if len(sys.argv) > 2 else 'chromium')
