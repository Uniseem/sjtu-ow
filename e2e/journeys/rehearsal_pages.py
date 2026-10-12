"""Read-only browser checks over an imported private production backup.

No worker is started and no writing UI action is performed: imported SMTP,
S3 and Google credentials cannot cause outbound effects. No identity, page
title, token or screenshot appears in the public output.
"""
from pathlib import Path
import json
import os
import shutil
import sqlite3
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'parity'))
import parity


def main(binary, work):
    work=Path(work)
    root=parity.ROOT
    env=dict(os.environ)
    database=Path(env['DATA_DIR'])/'sjtuow.sqlite3'
    api,ssr,caddy=[parity.screens.free_port() for _ in range(3)]
    base=f'http://127.0.0.1:{caddy}'
    env.update(SITE_URL=base,SJTUOW_HTTP_ADDR=f'127.0.0.1:{api}')
    paths=['/','/news/','/tournaments/','/scrims/','/teams/','/members/','/about/','/terms/','/privacy/']
    sessions=[]
    with sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True) as db:
        for id,slug in db.execute("SELECT p.id,p.slug FROM pages p JOIN articles a ON a.page_id=p.id WHERE p.live=1 AND p.is_public=1 ORDER BY p.id LIMIT 3"):
            paths.append('/news/'+slug+'/')
        for table,prefix in [('teams','teams'),('tournaments','tournaments'),('scrims','scrims')]:
            where='disbanded_at IS NULL' if table=='teams' else "status IN ('published','finished')"
            for (id,) in db.execute(f'SELECT id FROM {table} WHERE {where} ORDER BY id LIMIT 3'):
                paths.append(f'/{prefix}/{id}/')
        choices=db.execute("SELECT email,is_superuser FROM users WHERE is_active=1 AND email_verified_at IS NOT NULL ORDER BY is_superuser DESC,id LIMIT 4").fetchall()
        for email,superuser in choices:
            token=subprocess.run([binary,'session',email],env=env,capture_output=True,text=True,check=True).stdout.strip()
            sessions.append({'token':token,'admin':bool(superuser)})
    assets=work/'browser-assets'
    shutil.copytree(root/'web/apps/site/dist/client',assets)
    shutil.copytree(root/'web/apps/admin/dist',assets/'admin')
    shutil.copytree(root/'static/img',assets/'img')
    (assets/'css').mkdir()
    shutil.copy(root/'static/css/error.css',assets/'css/error.css')
    shutil.copy(root/'web/packages/styles/dist/site.css',assets/'css/reader.css')
    config=work/'private-browser.json'
    config.write_text(json.dumps({'base':base,'paths':paths,'sessions':sessions}))
    config.chmod(0o600)
    processes=[]
    container='sjtuow-rehearsal-browser-'+str(caddy)
    try:
        processes.append(subprocess.Popen([binary,'serve'],env=env,stdout=(work/'private-api.log').open('w'),stderr=subprocess.STDOUT))
        processes.append(subprocess.Popen(['node','dist/server/server.js'],cwd=root/'web/apps/site',env={**os.environ,'NODE_ENV':'production','PORT':str(ssr),'API_BASE':f'http://127.0.0.1:{api}'},stdout=(work/'private-ssr.log').open('w'),stderr=subprocess.STDOUT))
        subprocess.run(['docker','run','-d','--name',container,'--network','host','-e',f'CADDY_SITE_ADDRESS=:{caddy}','-e',f'API_UPSTREAM=127.0.0.1:{api}','-e',f'SSR_UPSTREAM=127.0.0.1:{ssr}','-v',f'{root}/deploy/Caddyfile.new:/etc/caddy/Caddyfile:ro','-v',f'{root}/deploy/error_pages:/srv/error_pages:ro','-v',f'{assets}:/var/assets:ro','-v',f'{env["MEDIA_DIR"]}:/var/media:ro','caddy:2.10-alpine'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        parity.screens.wait_for(base+'/robots.txt')
        subprocess.run(['node',str(root/'e2e/journeys/rehearsal-pages.mjs'),str(config)],cwd=root,check=True)
    finally:
        subprocess.run(['docker','rm','-f',container],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for process in processes:
            process.terminate()
            try:process.wait(timeout=15)
            except subprocess.TimeoutExpired:process.kill();process.wait()


if __name__=='__main__':
    try:main(sys.argv[1],sys.argv[2])
    except Exception:
        print('PRIVATE-REHEARSAL-PAGES-FAILED (details retained only within private work directory)',file=sys.stderr)
        sys.exit(1)
