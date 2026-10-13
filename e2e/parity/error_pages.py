"""Real SSR error triggers against frozen Django error-template documents.

The 500 trigger damages only a newly created fixture database. It is restored
before the next case. Maintenance is triggered by stopping only this fixture's
Go child. No production process or database is touched.
"""
import http.server
import importlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error
import parity


def main():
    os.environ.update(DJANGO_SETTINGS_MODULE='sjtu_ow.settings.dev', DJANGO_SECRET_KEY=parity.TEST_SIGNING_KEY, SITE_URL=parity.TEST_SITE_URL)
    if parity.WORK.exists():
        parity.WORK.rename(parity.WORK.with_name('sjtu-ow-parity-prev-' + str(time.time_ns())))
    parity.SHOTS.mkdir(parents=True)
    data = parity.prepare_legacy(True)
    old_port, api_port, ssr_port, caddy_port, debug_port = [parity.screens.free_port() for _ in range(5)]
    env = parity.new_env(api_port)
    sessions = parity.prepare_new(env)
    os.environ.update(parity.screens.site_env())
    import django
    django.setup()
    from django.template.loader import render_to_string
    documents = {code: render_to_string(f'errors/{code}.html') for code in (403, 404, 429, 500)}
    documents[503] = (parity.ROOT / 'deploy/error_pages/maintenance.html').read_text()

    class Reference(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith('/error/'):
                code = int(self.path.split('/')[2])
                self.send_response(code)
                self.send_header('Content-Type','text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(documents[code].encode())
            else:
                relative = self.path.removeprefix('/static/')
                allowed = parity.ROOT / 'static' / relative
                if not allowed.resolve().is_relative_to((parity.ROOT/'static').resolve()) or not allowed.is_file():
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header('Content-Type','text/css' if allowed.suffix=='.css' else 'image/svg+xml')
                self.end_headers()
                self.wfile.write(allowed.read_bytes())
        def log_message(self,*args): pass
    server = http.server.ThreadingHTTPServer(('127.0.0.1',old_port),Reference)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    processes = []
    results = []
    try:
        processes.extend(parity.start_new(env,api_port,ssr_port,caddy_port))
        processes.append(subprocess.Popen(['chromium','--headless=new','--no-sandbox',f'--remote-debugging-port={debug_port}',f'--user-data-dir={parity.WORK/"error-browser"}','about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL))
        parity.screens.wait_for(f'http://127.0.0.1:{caddy_port}/robots.txt')
        parity.screens.wait_for(f'http://127.0.0.1:{debug_port}/json/version')
        targets=json.load(urllib.request.urlopen(f'http://127.0.0.1:{debug_port}/json'))
        tools=parity.RecordingDevTools(next(item for item in targets if item.get('type')=='page')['webSocketDebuggerUrl'])
        for method in ('Page.enable','Network.enable','Runtime.enable'): tools.send(method)
        for code,path,role in [(403,'/admin/users/','member'),(404,'/no/such/','visitor'),(429,'/search/?q=limit','visitor'),(500,'/news/screens-guide/','visitor'),(503,'/','visitor')]:
            if code==429:
                for _ in range(100):
                    if parity.fetch_status(f'http://127.0.0.1:{caddy_port}/api/search?q=limit',None)[0]==429: break
                else: raise RuntimeError('real search bucket did not fill')
            if code==500:
                with sqlite3.connect(parity.WORK/'new-data/sjtuow.sqlite3') as database:
                    database.execute('ALTER TABLE articles RENAME TO broken_articles')
            if code==503:
                processes[0].terminate()
                processes[0].wait(timeout=15)
            try:
                cookie=[{'name':'ow_session','value':sessions[role]}] if role in sessions else []
                new_url=f'http://127.0.0.1:{caddy_port}'+__import__('urllib.parse',fromlist=['quote']).quote(path,safe='/?=&#%')
                actual=parity.fetch_status(new_url,'; '.join(item['name']+'='+item['value'] for item in cookie))[0]
                if code == 403:
                    # Independent SPA shell200 is approved; the real Go gate
                    # returns403 and the settled browser paints its standalone doc.
                    gate = parity.fetch_status(f'http://127.0.0.1:{caddy_port}/api/admin/users', '; '.join(item['name']+'='+item['value'] for item in cookie))[0]
                    if gate != 403: raise RuntimeError(f'admin403 gate returned {gate}')
                elif actual!=code: raise RuntimeError(f'error trigger {code} returned {actual}')
                for width,scheme in [(1280,'light'),(375,'light'),(1280,'dark'),(375,'dark')]:
                    if code == 429:
                        # Keep the real IP bucket full across a minute boundary
                        # and use the same query as the visual navigation.
                        for _ in range(100):
                            if parity.fetch_status(f'http://127.0.0.1:{caddy_port}/api/search?q=limit',None)[0]==429: break
                        else: raise RuntimeError('real search bucket did not refill')
                    stem=f'error-{code}-{width}-{scheme}'
                    old=parity.look(tools,f'http://127.0.0.1:{old_port}/error/{code}/',None,width,scheme,parity.SHOTS/f'{stem}-old.png')
                    new=parity.look(tools,new_url,cookie,width,scheme,parity.SHOTS/f'{stem}-new.png')
                    if new['effective_status'] != code: raise RuntimeError(f'error document {code} painted {new["effective_status"]}')
                    # Expected top-level 500/503 navigation is the trigger itself;
                    # this document has no scripts or dependent API requests.
                    for snap in (old,new):
                        snap['browser_errors']=[error for error in snap['browser_errors'] if not error.startswith('HTTP 500+:')]
                    ratio,note=parity.pixel_ratio(parity.SHOTS/f'{stem}-old.png',parity.SHOTS/f'{stem}-new.png')
                    problems=parity.compare(old,new,ratio,(0,0))
                    if note: problems.append(note)
                    if parity.evaluate(tools,"document.scripts.length")!=0: problems.append('error document contains script')
                    results.append({'status':code,'view':f'{width}-{scheme}','ratio':ratio,'problems':problems})
            finally:
                if code==500:
                    with sqlite3.connect(parity.WORK/'new-data/sjtuow.sqlite3') as database:
                        database.execute('ALTER TABLE broken_articles RENAME TO articles')
        (parity.OUT/'error-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
        failed=[row for row in results if row['problems']]
        print('ERROR-PAGES',len(results)-len(failed),'/',len(results),flush=True)
        for row in failed: print(row,flush=True)
        if failed: raise SystemExit(1)
    finally:
        subprocess.run(['docker','rm','-f','ow-parity-caddy'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for process in processes:
            process.terminate()
            try: process.wait(timeout=15)
            except subprocess.TimeoutExpired: process.kill();process.wait()
        server.shutdown();server.server_close()


if __name__=='__main__': main()
