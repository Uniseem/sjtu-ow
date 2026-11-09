"""Snapshot only this production project; keep all real data on production."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tarfile
import urllib.parse
import urllib.request

os.umask(0o077)
ROOT = Path('/srv/sjtu-ow')
WORK = Path('/root/sjtu-ow-307')
CONFIG = Path('/etc/contabo-apps/sjtu-ow-next.compose.json')
EXPECTED_CONFIG = '711faf6d3baa1b38ad9a9caf7cd55096dc7ffb37102e63bba320c62a5a53320b'

def output(args): return subprocess.check_output(args, text=True)
def digest(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()
def inspect(name): return json.loads(output(['docker', 'inspect', name]))[0]
def request(path, token=''):
    headers = {'Cookie': 'ow_session=' + token} if token else {}
    with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:22887' + path, headers=headers), timeout=20) as response:
        return json.loads(response.read())

assert output(['hostname']).strip() == 'kvm17243'
assert digest(CONFIG) == EXPECTED_CONFIG
assert not output(['git', '-C', str(ROOT), 'status', '--short']).strip()
health = request('/healthz')
assert health['status'] == 'ok' and all(value['ok'] for value in health['checks'].values())
WORK.mkdir(mode=0o700, exist_ok=True)
assert (WORK.stat().st_mode & 0o777) == 0o700
assert not (WORK / 'before.json').exists(), 'Preserve the first snapshot and inspect it before a retry'
configuration = json.loads(CONFIG.read_text())
assert configuration['name'] == 'sjtu-ow-next' and set(configuration['services']) == {'server', 'worker', 'web', 'proxy'}
current = {name: inspect(service['container_name']) for name, service in configuration['services'].items()}
assert all(item['State']['Running'] for item in current.values())
for item in current.values():
    assert item['Config']['Labels']['com.docker.compose.project'] == 'sjtu-ow-next'
    assert item['Config']['Labels']['com.docker.compose.project.config_files'] == str(CONFIG)
env_files = {}
for service in configuration['services'].values():
    for entry in service.get('env_file', []):
        path = Path(entry['path'])
        assert (path.stat().st_mode & 0o777) == 0o600
        env_files[str(path)] = digest(path)
server = current['server']
data_mount = next(mount for mount in server['Mounts'] if mount['Destination'] == '/srv/sjtuow/data')
database = Path(data_mount['Source']) / 'sjtuow.sqlite3'
assert database.is_file()
schema = lambda db: hashlib.sha256(json.dumps(db.execute("SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name").fetchall()).encode()).hexdigest()
with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as db:
    assert db.execute('PRAGMA quick_check').fetchone() == ('ok',)
    assert not db.execute('PRAGMA foreign_key_check').fetchall()
    schema_hash = schema(db)
    counts = {name: db.execute('SELECT count(*) FROM ' + name).fetchone()[0] for name in ['users', 'pages', 'articles', 'teams', 'tournaments', 'scrims', 'images']}
    admin = db.execute("SELECT id,email FROM users WHERE is_active=1 AND is_superuser=1 AND email_verified_at IS NOT NULL ORDER BY id LIMIT 1").fetchone()
    assert admin, 'Need an existing verified administrator; do not fabricate production users'
    paths = ['/', '/news/', '/teams/', '/members/', '/tournaments/', '/scrims/', '/about/', '/terms/', '/privacy/', '/accounts/login/', '/accounts/signup/']
    paths += ['/news/' + urllib.parse.quote(row[0], safe='') + '/' for row in db.execute('SELECT p.slug FROM pages p JOIN articles a ON a.page_id=p.id WHERE p.live=1 AND p.is_public=1 ORDER BY p.id LIMIT 2')]
stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S')
backup = Path('/root/sjtu-ow-backups') / ('release-307-' + stamp)
backup.mkdir(mode=0o700, parents=True)
shutil.copy2(CONFIG, backup / 'production-compose.json')
(backup / 'production-compose.json').chmod(0o600)
rollback = json.loads(CONFIG.read_text())
for name in ['server', 'web']:
    tag = f'sjtu-ow-next-{name}:pre-307-{stamp}'
    subprocess.run(['docker', 'tag', current[name]['Image'], tag], check=True)
    rollback['services'][name]['image'] = tag
    if name == 'server': rollback['services']['worker']['image'] = tag
(backup / 'rollback.compose.json').write_text(json.dumps(rollback, indent=2) + '\n')
archive = backup / 'current-data.tar.gz'
with archive.open('wb') as stream, (backup / 'backup.stderr').open('wb') as error:
    subprocess.run(['docker', 'exec', server['Id'], '/srv/sjtuow/sjtuow', 'backup', '--no-upload', '--out', '-'], check=True, stdout=stream, stderr=error)
with tarfile.open(archive, 'r:gz') as bundle:
    meta = json.load(bundle.extractfile('manifest.json'))
    snapshot = backup / 'verified-snapshot.sqlite3'
    with snapshot.open('wb') as stream: shutil.copyfileobj(bundle.extractfile('sjtuow.sqlite3'), stream)
assert digest(snapshot) == meta['database_checksum']
with sqlite3.connect(snapshot.as_uri() + '?mode=ro', uri=True) as db:
    assert db.execute('PRAGMA quick_check').fetchone() == ('ok',)
    assert not db.execute('PRAGMA foreign_key_check').fetchall()
    assert schema(db) == schema_hash
environ = dict(entry.split('=', 1) for entry in server['Config']['Env'] if '=' in entry)
base = environ['SITE_URL'].rstrip('/')
assert base == 'https://sjtu.ow-shanghaiuniversity.com'
token = output(['docker', 'exec', server['Id'], '/srv/sjtuow/sjtuow', 'session', admin[1]]).strip()
assert len(token) >= 32 and '\n' not in token
session = request('/api/session', token)
assert session['user']['id'] == admin[0] and session['user']['superuser']
(WORK / 'browser-private.json').write_text(json.dumps({'base': base, 'paths': paths, 'token': token, 'userId': admin[0]}))
before = {'backup': str(backup), 'archiveSha256': digest(archive), 'backupManifest': meta, 'schemaSha256': schema_hash, 'counts': counts, 'database': str(database), 'databaseInode': database.stat().st_ino, 'envFiles': env_files, 'configSha256': EXPECTED_CONFIG, 'git': output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD']).strip(), 'containers': {name: {'id': item['Id'], 'image': item['Image'], 'tag': item['Config']['Image'], 'mounts': item['Mounts'], 'ports': item['HostConfig']['PortBindings'], 'networks': list(item['NetworkSettings']['Networks'])} for name, item in current.items()}, 'health': health}
(WORK / 'before.json').write_text(json.dumps(before, indent=2))
print(json.dumps({'phase': 'BACKUP-READY', 'backup': str(backup), 'databaseIntegrity': True, 'foreignKeys': True, 'schemaVersion': meta['schema_version'], 'mediaFiles': meta['media_files_count'], 'backupBytes': archive.stat().st_size, 'counts': counts, 'existingAccountSessionVerified': True}), flush=True)
