"""Temporary real Go API + production SSR + real Caddy; no production data."""
from pathlib import Path
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request

root=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(root))
from scripts import screens
work=Path(tempfile.mkdtemp(prefix='sjtuow-real-comments-'))
ports=[screens.free_port() for _ in range(3)]
api_port,ssr_port,caddy_port=ports
binary=work/'sjtuow'
env={**os.environ,'DATA_DIR':str(work/'data'),'MEDIA_DIR':str(work/'media'),'SITE_URL':f'http://127.0.0.1:{caddy_port}','SIGNING_KEY':'real-comments-test-signing-key-32chars','FIELD_ENCRYPTION_KEY':'real-comments-test-field-key-32chars'}
procs=[]
container=f'ow-real-comments-{caddy_port}'
try:
 subprocess.run(['go','build','-o',str(binary),'./cmd/sjtuow'],cwd=root/'server',check=True)
 subprocess.run([str(binary),'migrate'],env=env,check=True,stdout=subprocess.DEVNULL)
 seeded=subprocess.run([str(binary),'seed'],env=env,check=True,capture_output=True,text=True)
 sessions=json.loads(seeded.stdout.strip().splitlines()[-1])
 banned=subprocess.run([str(binary),'session','mate@screens.test'],env=env,check=True,capture_output=True,text=True).stdout.strip()
 with sqlite3.connect(work/'data/sjtuow.sqlite3') as db:
  now='2026-10-11T00:00:00Z'
  db.executescript("""INSERT INTO pages (id,kind,slug,title,live,created_at,updated_at) VALUES
  (1000,'news_index','news','资讯',1,'2026-10-11','2026-10-11'),
  (1001,'article','real-comments','真实评论旅程',1,'2026-10-11','2026-10-11'),
  (1002,'article','closed-comments','关闭评论',1,'2026-10-11','2026-10-11'),
  (1003,'article','private-comments','私密评论',1,'2026-10-11','2026-10-11');
  INSERT INTO news_index VALUES (1000,'');
  INSERT INTO articles (page_id,body_html,comments_enabled,author_id) VALUES
  (1001,'<p>真实Go接口旅程。</p>',1,1),(1002,'<p>关闭评论。</p>',0,1),(1003,'<p>私密。</p>',1,1);
  UPDATE pages SET parent_id=1000 WHERE kind='article';
  UPDATE pages SET is_public=0 WHERE id=1003;
  INSERT INTO feature_user_rules (user_id,feature,denied,created_at) VALUES (3,'article_comment',1,'2026-10-11');""")
  for ident in range(1,26):
   owner=3 if ident==25 else 1
   db.execute('INSERT INTO comments (id,article_id,user_id,content,created_at,updated_at) VALUES (?,1001,?,?,?,?)',(ident,owner,f'Seed comment {ident}',f'2026-10-11T00:00:{ident:02d}Z',f'2026-10-11T00:00:{ident:02d}Z'))
 config=work/'config.json'
 config.write_text(json.dumps({'base':env['SITE_URL'],'database':str(work/'data/sjtuow.sqlite3'),'member':sessions['member'],'other':sessions['captain'],'moderator':sessions['officer'],'banned':banned,'article':1001}))
 procs.append(subprocess.Popen([str(binary),'serve'],env={**env,'SJTUOW_HTTP_ADDR':f'127.0.0.1:{api_port}'},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL))
 procs.append(subprocess.Popen(['node','dist/server/server.js'],cwd=root/'web/apps/site',env={**os.environ,'NODE_ENV':'production','PORT':str(ssr_port),'API_BASE':f'http://127.0.0.1:{api_port}'},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL))
 assets=work/'assets';shutil.copytree(root/'web/apps/site/dist/client',assets);shutil.copytree(root/'static/img',assets/'img');(assets/'css').mkdir();shutil.copy(root/'static/css/error.css',assets/'css/error.css')
 subprocess.run(['docker','run','-d','--name',container,'--network','host','-e',f'CADDY_SITE_ADDRESS=:{caddy_port}','-e',f'API_UPSTREAM=127.0.0.1:{api_port}','-e',f'SSR_UPSTREAM=127.0.0.1:{ssr_port}','-v',f'{root}/deploy/Caddyfile.new:/etc/caddy/Caddyfile:ro','-v',f'{root}/deploy/error_pages:/srv/error_pages:ro','-v',f'{assets}:/var/assets:ro','-v',f'{work}/media:/var/media:ro','caddy:2.10-alpine'],check=True,stdout=subprocess.DEVNULL)
 screens.wait_for(env['SITE_URL']+'/news/real-comments/')
 subprocess.run(['node',str(root/'web/apps/site/real-comments-journey.mjs'),str(config),'/usr/bin/chromium'],cwd=root/'web/apps/site',check=True,env=os.environ)
finally:
 subprocess.run(['docker','rm','-f',container],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 for proc in procs:proc.terminate()
 for proc in procs:proc.wait(timeout=15)
 # Leave the temporary DB for inspecting failed evidence; never remove a live DB.
 print(f'REAL-COMMENTS-WORK {work}',flush=True)
