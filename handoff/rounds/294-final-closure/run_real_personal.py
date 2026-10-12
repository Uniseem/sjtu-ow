"""Temporary real Go API + production SSR + real Caddy; no production data."""
from pathlib import Path
import json
import os
import shutil
import socketserver
import threading
import re
from email import policy
from email.parser import BytesParser
import subprocess
import sys
import tempfile

root=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(root))
from scripts import screens
work=Path(tempfile.mkdtemp(prefix='sjtuow-real-personal-294-'))
ports=[screens.free_port() for _ in range(3)]
api_port,ssr_port,caddy_port=ports
binary=work/'sjtuow'
env={**os.environ,'DATA_DIR':str(work/'data'),'MEDIA_DIR':str(work/'media'),'SITE_URL':f'http://127.0.0.1:{caddy_port}','SIGNING_KEY':'real-personal-294-test-signing-key-32chars','FIELD_ENCRYPTION_KEY':'real-personal-294-test-field-key-32chars'}
procs=[]
class Mailbox(socketserver.StreamRequestHandler):
 def handle(self):
  self.wfile.write(b'220 localhost test SMTP\r\n')
  recipient=''
  while line:=self.rfile.readline():
   command=line.decode().strip()
   upper=command.upper()
   if upper.startswith('EHLO') or upper.startswith('HELO'):
    self.wfile.write(b'250 localhost\r\n')
   elif upper.startswith('RCPT TO:'):
    recipient=command.split(':',1)[1].strip().strip('<>')
    if not recipient.endswith('@example.test'):
     self.wfile.write(b'550 test addresses only\r\n');continue
    self.wfile.write(b'250 OK\r\n')
   elif upper=='DATA':
    self.wfile.write(b'354 Send data\r\n')
    raw=[]
    while (part:=self.rfile.readline()) not in (b'.\r\n',b''):
     raw.append(part[1:] if part.startswith(b'..') else part)
    message=BytesParser(policy=policy.default).parsebytes(b''.join(raw))
    body=message.get_body(preferencelist=('plain',))
    valid_mime=message.get_content_type()=='multipart/alternative' and message.is_multipart()
    codes=re.findall(r'验证码：([0-9]{6})(?![0-9])',body.get_content() if valid_mime and body else '')
    with (work/'mailbox.jsonl').open('a') as output:
     output.write(json.dumps({'to':recipient,'subject':str(message['Subject']),'code':codes[0] if codes else None,'valid_mime':valid_mime})+'\n')
    self.wfile.write(b'250 accepted\r\n')
   elif upper=='QUIT':
    self.wfile.write(b'221 Bye\r\n');break
   else:self.wfile.write(b'250 OK\r\n')

smtp=None
container=f'ow-real-personal-294-{caddy_port}'
try:
 subprocess.run(['go','build','-o',str(binary),'./cmd/sjtuow'],cwd=root/'server',check=True)
 subprocess.run([str(binary),'migrate'],env=env,check=True,stdout=subprocess.DEVNULL)
 config=work/'config.json'
 config.write_text(json.dumps({'base':env['SITE_URL'],'database':str(work/'data/sjtuow.sqlite3'),'mailbox':str(work/'mailbox.jsonl')}))
 smtp=socketserver.ThreadingTCPServer(('127.0.0.1',0),Mailbox)
 smtp.daemon_threads=True
 threading.Thread(target=smtp.serve_forever,daemon=True).start()
 env.update(SMTP_HOST='127.0.0.1',SMTP_PORT=str(smtp.server_address[1]),SMTP_FROM='site@example.test',SMTP_USER='',SMTP_PASSWORD='',SMTP_SECURITY='plain',EMAIL_ALLOWLIST='')
 procs.append(subprocess.Popen([str(binary),'worker'],env=env,stdout=(work/'worker.log').open('w'),stderr=subprocess.STDOUT))
 procs.append(subprocess.Popen([str(binary),'serve'],env={**env,'SJTUOW_HTTP_ADDR':f'127.0.0.1:{api_port}'},stdout=(work/'api.log').open('w'),stderr=subprocess.STDOUT))
 procs.append(subprocess.Popen(['node','dist/server/server.js'],cwd=root/'web/apps/site',env={**os.environ,'NODE_ENV':'production','PORT':str(ssr_port),'API_BASE':f'http://127.0.0.1:{api_port}'},stdout=(work/'ssr.log').open('w'),stderr=subprocess.STDOUT))
 assets=work/'assets';shutil.copytree(root/'web/apps/site/dist/client',assets);shutil.copytree(root/'static/img',assets/'img');(assets/'css').mkdir();shutil.copy(root/'static/css/error.css',assets/'css/error.css')
 subprocess.run(['docker','run','-d','--name',container,'--network','host','-e',f'CADDY_SITE_ADDRESS=:{caddy_port}','-e',f'API_UPSTREAM=127.0.0.1:{api_port}','-e',f'SSR_UPSTREAM=127.0.0.1:{ssr_port}','-v',f'{root}/deploy/Caddyfile.new:/etc/caddy/Caddyfile:ro','-v',f'{root}/deploy/error_pages:/srv/error_pages:ro','-v',f'{assets}:/var/assets:ro','-v',f'{work}/media:/var/media:ro','caddy:2.10-alpine'],check=True,stdout=subprocess.DEVNULL)
 screens.wait_for(env['SITE_URL']+'/accounts/signup/')
 subprocess.run(['node',str(root/'handoff/rounds/294-final-closure/personal-journey.mjs'),str(config),'/usr/bin/chromium'],cwd=root/'web/apps/site',check=True,env=os.environ)
finally:
 subprocess.run(['docker','rm','-f',container],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 for proc in procs:proc.terminate()
 for proc in procs:proc.wait(timeout=15)
 # Leave the temporary DB for inspecting failed evidence; never remove a live DB.
 if smtp:smtp.shutdown();smtp.server_close()
 print(f'REAL-PERSONAL-294-WORK {work}',flush=True)
