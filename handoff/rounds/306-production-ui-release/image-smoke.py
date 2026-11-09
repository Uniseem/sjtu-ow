"""Exercise the exact release images against an isolated fictional database."""
from pathlib import Path
import hashlib
import json
import os
import socket
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
BASE = Path('/srv/build/sjtu-ow')
OUT = BASE / '306-artifacts'
manifest = json.loads((OUT / 'manifest.json').read_text())
prefix = 'sjtu-ow-306-smoke-' + str(int(time.time()))
volumes = {kind: prefix + '-' + kind for kind in ['data', 'media', 'assets']}
containers = []

def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]

api, ssr, proxy = [port() for _ in range(3)]
base = f'http://127.0.0.1:{proxy}'
environment = {
    'SITE_URL': base, 'SIGNING_KEY': '306-fictional-signing-key-0123456789-abcdef',
    'FIELD_ENCRYPTION_KEY': '306-fictional-field-key-0123456789-abcdef',
    'DATA_DIR': '/srv/sjtuow/data', 'MEDIA_DIR': '/srv/sjtuow/media',
    'SJTUOW_HTTP_ADDR': f'127.0.0.1:{api}', 'EMAIL_ALLOWLIST': '.test',
}
go = ['docker', 'run', '--rm', '--network', 'host']
for key, value in environment.items(): go += ['-e', key + '=' + value]
for kind in ['data', 'media']: go += ['-v', volumes[kind] + ':/srv/sjtuow/' + kind]
tag = manifest['images']['server']['tag']
try:
    for name in volumes.values():
        subprocess.run(['docker', 'volume', 'create', '--label', 'sjtuow.round=306', name], check=True, stdout=subprocess.DEVNULL)
    subprocess.run([*go, tag, 'migrate'], check=True, stdout=subprocess.DEVNULL)
    seed = json.loads(subprocess.check_output([*go, tag, 'seed'], text=True))
    server = prefix + '-server'
    command = [*go]
    command.remove('--rm')
    subprocess.run([*command, '-d', '--name', server, tag, 'serve'], check=True, stdout=subprocess.DEVNULL)
    containers.append(server)
    copy = 'mkdir -p /var/assets/img /var/assets/css /var/assets/admin && cp -a /app/web/apps/site/dist/client/. /var/assets/ && cp -a /app/web/apps/admin/dist/. /var/assets/admin/ && cp -a /app/static/img/. /var/assets/img/ && cp /app/static/css/error.css /app/static/css/reader.css /var/assets/css/ && exec node dist/server/server.js'
    web = prefix + '-web'
    subprocess.run(['docker', 'run', '-d', '--name', web, '--network', 'host', '-e', 'NODE_ENV=production', '-e', f'PORT={ssr}', '-e', f'API_BASE=http://127.0.0.1:{api}', '-v', volumes['assets'] + ':/var/assets', manifest['images']['web']['tag'], 'sh', '-ec', copy], check=True, stdout=subprocess.DEVNULL)
    containers.append(web)
    caddy = prefix + '-proxy'
    source = BASE / '306-release-source'
    subprocess.run(['docker', 'run', '-d', '--name', caddy, '--network', 'host', '-e', f'CADDY_SITE_ADDRESS={base}', '-e', f'API_UPSTREAM=127.0.0.1:{api}', '-e', f'SSR_UPSTREAM=127.0.0.1:{ssr}', '-v', str(source / 'deploy/Caddyfile.new') + ':/etc/caddy/Caddyfile:ro', '-v', str(source / 'deploy/error_pages') + ':/srv/error_pages:ro', '-v', volumes['assets'] + ':/var/assets:ro', '-v', volumes['media'] + ':/var/media:ro', 'caddy:2.10-alpine'], check=True, stdout=subprocess.DEVNULL)
    containers.append(caddy)
    deadline = time.monotonic() + 40
    while True:
        try:
            with urllib.request.urlopen(base + '/api/session', timeout=3) as response:
                assert response.status == 200
            break
        except Exception:
            if time.monotonic() >= deadline: raise
            time.sleep(0.2)
    config = OUT / 'smoke-config.json'
    config.write_text(json.dumps({'base': base, 'token': seed['officer'], 'output': str(OUT)}))
    config.chmod(0o600)
    subprocess.run(['node', str(Path(__file__).with_name('image-smoke.mjs')), str(config)], cwd=ROOT, check=True)
    manifest['goBinarySha256'] = hashlib.sha256((OUT / 'sjtuow').read_bytes()).hexdigest()
    manifest['smoke'] = json.loads((OUT / 'smoke-result.json').read_text())
    manifest['testVolumes'] = volumes
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    print('EXACT-IMAGE-SMOKE-OK containers=3 isolated-fictional-data retained-for-audit', flush=True)
finally:
    for name in reversed(containers):
        subprocess.run(['docker', 'stop', '--time', '15', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['docker', 'rm', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
