"""Build immutable release images on the compiler worker, never on production."""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BASE = Path('/srv/build/sjtu-ow')
SOURCE = '564bb9a34a38f1ce630cee476b71c1e5cbe999cf'
OUT = BASE / '306-artifacts'
CONTEXT = BASE / '306-release-source'
OUT.mkdir(exist_ok=True)
if shutil.disk_usage(BASE).free < 6 * 1024**3:
    raise SystemExit('Need 6GiB free before building; inspect project caches first')
subprocess.run(['git', 'cat-file', '-e', SOURCE + '^{commit}'], cwd=ROOT, check=True)
if not CONTEXT.exists():
    CONTEXT.mkdir()
    with (OUT / 'source.tar').open('wb') as stream:
        subprocess.run(['git', 'archive', SOURCE], cwd=ROOT, stdout=stream, check=True)
    subprocess.run(['tar', '-xf', str(OUT / 'source.tar'), '-C', str(CONTEXT)], check=True)
    (CONTEXT / '.release-source').write_text(SOURCE + '\n')
assert (CONTEXT / '.release-source').read_text().strip() == SOURCE
manifest = {'source': SOURCE, 'images': {}}
for service in ['server', 'web']:
    tag = f'sjtu-ow-next-{service}:306-{SOURCE[:7]}'
    with (OUT / f'{service}-build.log').open('w') as log:
        subprocess.run(['docker', 'build', '--pull', '--label', f'sjtuow.source={SOURCE}', '--label', f'org.opencontainers.image.revision={SOURCE}', '-f', f'deploy/Dockerfile.{service}', '-t', tag, '.'], cwd=CONTEXT, stdout=log, stderr=subprocess.STDOUT, check=True)
    image = json.loads(subprocess.check_output(['docker', 'image', 'inspect', tag], text=True))[0]
    assert image['Config']['Labels']['sjtuow.source'] == SOURCE
    assert image['Config']['User'] == '10001:10001'
    manifest['images'][service] = {'tag': tag, 'id': image['Id'], 'size': image['Size'], 'architecture': image['Architecture'], 'user': image['Config']['User']}
    print(f'IMAGE-BUILT {service} {image["Id"]} source={SOURCE}', flush=True)

volume = 'sjtu-ow-306-assets-probe'
container = 'sjtu-ow-306-binary-probe'
subprocess.run(['docker', 'volume', 'create', '--label', 'sjtuow.round=306', volume], check=True, stdout=subprocess.DEVNULL)
try:
    copy = 'mkdir -p /var/assets/img /var/assets/css /var/assets/admin && cp -a /app/web/apps/site/dist/client/. /var/assets/ && cp -a /app/web/apps/admin/dist/. /var/assets/admin/ && cp -a /app/static/img/. /var/assets/img/ && cp /app/static/css/error.css /app/static/css/reader.css /var/assets/css/ && test -s /var/assets/admin/index.html && test -s /var/assets/css/reader.css && test "$(id -u)" = 10001'
    subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'sh', '-v', volume + ':/var/assets', manifest['images']['web']['tag'], '-ec', copy], check=True)
    hashes = '''import {readdirSync,readFileSync} from "node:fs";import{join,relative}from"node:path";import{createHash}from"node:crypto";const out={};function scan(p){for(const e of readdirSync(p,{withFileTypes:true})){const f=join(p,e.name);if(e.isDirectory())scan(f);else if(e.isFile())out[relative('/var/assets',f)]=createHash('sha256').update(readFileSync(f)).digest('hex')}}scan('/var/assets');console.log(JSON.stringify(out))'''
    manifest['assets'] = json.loads(subprocess.check_output(['docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'node', '-v', volume + ':/var/assets:ro', manifest['images']['web']['tag'], '--input-type=module', '-e', hashes], text=True))
    subprocess.run(['docker', 'create', '--name', container, manifest['images']['server']['tag']], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(['docker', 'cp', container + ':/srv/sjtuow/sjtuow', str(OUT / 'sjtuow')], check=True)
    version = subprocess.check_output(['go', 'version', '-m', str(OUT / 'sjtuow')], text=True)
    (OUT / 'go-version.txt').write_text(version)
    matched = re.search(r': go(\d+)\.(\d+)\.(\d+)', version)
    assert matched and tuple(map(int, matched.groups())) >= (1, 26, 10)
    manifest['goVersion'] = matched.group(0)[2:]
    print(f'NONROOT-ASSETS-PROBE-OK files={len(manifest["assets"])} go={manifest["goVersion"]}', flush=True)
finally:
    subprocess.run(['docker', 'rm', '-f', container], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(['docker', 'volume', 'rm', volume], stdout=subprocess.DEVNULL, check=True)

archive = OUT / 'images.tar.gz'
with archive.open('wb') as stream:
    save = subprocess.Popen(['docker', 'save', *[item['tag'] for item in manifest['images'].values()]], stdout=subprocess.PIPE)
    compressed = subprocess.run(['gzip', '-1'], stdin=save.stdout, stdout=stream)
    save.stdout.close()
    assert save.wait() == 0 and compressed.returncode == 0
with archive.open('rb') as stream:
    manifest['archiveSha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
manifest['archiveBytes'] = archive.stat().st_size
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2))
print(f'RELEASE-READY bytes={manifest["archiveBytes"]} sha256={manifest["archiveSha256"]}', flush=True)
