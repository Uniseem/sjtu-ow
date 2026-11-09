"""Upgrade only the existing project; rollback images/config without replacing data."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import time
import urllib.request

os.umask(0o077)
WORK = Path('/root/sjtu-ow-307')
ROOT = Path('/srv/sjtu-ow')
CONFIG = Path('/etc/contabo-apps/sjtu-ow-next.compose.json')
SOURCE = '564bb9a34a38f1ce630cee476b71c1e5cbe999cf'
before = json.loads((WORK / 'before.json').read_text())
manifest = json.loads((WORK / 'manifest.json').read_text())
database = Path(before['database'])
compose = ['docker', 'compose', '-p', 'sjtu-ow-next', '-f', str(CONFIG), '--env-file', '/dev/null']
phase = 'preflight'
switched = False

def log(name, **values): print(json.dumps({'phase': name, **values}), flush=True)
def digest(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()
def output(args): return subprocess.check_output(args, text=True)
def run(args, name):
    with (WORK / (name + '.log')).open('w') as stream:
        subprocess.run(args, stdout=stream, stderr=subprocess.STDOUT, check=True)
def inspect(name): return json.loads(output(['docker', 'inspect', 'sjtu-ow-next-' + name + '-1']))[0]
def schema():
    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as db:
        rows = db.execute("SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name").fetchall()
        return hashlib.sha256(json.dumps(rows).encode()).hexdigest()
def heartbeat():
    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as db:
        row = db.execute('SELECT started_at,heartbeat_at FROM worker_status WHERE id=1').fetchone()
        return [dt.datetime.fromisoformat(value.replace('Z', '+00:00')) for value in row]
def wait_worker_lock():
    # The existing worker deliberately keeps its 120s lease on shutdown.
    # Wait for the normal takeover gate; do not modify the lock in SQLite.
    deadline = time.monotonic() + 180
    while True:
        with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as db:
            row = db.execute('SELECT heartbeat_at FROM worker_lock WHERE id=1').fetchone()
        if not row: return
        last = dt.datetime.fromisoformat(row[0].replace('Z', '+00:00'))
        remaining = 121 - (dt.datetime.now(dt.timezone.utc) - last).total_seconds()
        if remaining <= 0: return
        if time.monotonic() > deadline: raise RuntimeError('Another writer keeps renewing the worker lease')
        log('WAIT-WORKER-LEASE', secondsRemaining=round(remaining))
        time.sleep(min(30, remaining + 0.1))
def wait_new_worker(since):
    deadline = time.monotonic() + 75
    while time.monotonic() < deadline:
        item = inspect('worker')
        started, beat = heartbeat()
        if item['State']['Running'] and started >= since and beat >= started:
            return {'startedAt': started.isoformat(), 'heartbeatAt': beat.isoformat()}
        time.sleep(1)
    raise RuntimeError('Fresh worker heartbeat did not appear')
def health():
    with urllib.request.urlopen('http://127.0.0.1:22887/healthz', timeout=8) as response:
        value = json.load(response)
        assert response.status == 200 and value['status'] == 'ok' and all(item['ok'] for item in value['checks'].values())
        return value
def wait_healthy():
    deadline = time.monotonic() + 60
    while True:
        try: return health()
        except Exception:
            if time.monotonic() >= deadline: raise
            time.sleep(1)
def install_config(value):
    temp = CONFIG.with_name(CONFIG.name + '.307.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n')
    temp.chmod(0o644)
    os.replace(temp, CONFIG)
def mounts(item):
    return sorted([{key: mount.get(key) for key in ['Type', 'Name', 'Source', 'Destination', 'RW']} for mount in item['Mounts']], key=lambda mount: mount['Destination'])
critical_env = ['SJTUOW_ENV', 'SIGNING_KEY', 'FIELD_ENCRYPTION_KEY', 'BACKUP_ENCRYPTION_KEY', 'SITE_URL', 'DATA_DIR', 'MEDIA_DIR', 'TRUSTED_PROXIES', 'SMTP_HOST', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASSWORD', 'SMTP_FROM', 'SMTP_SECURITY', 'API_BASE', 'PORT', 'NODE_ENV']
def env_hashes(item):
    values = dict(entry.split('=', 1) for entry in item['Config']['Env'] if '=' in entry)
    return {key: hashlib.sha256(values.get(key, '').encode()).hexdigest() for key in critical_env}

try:
    assert output(['hostname']).strip() == 'kvm17243'
    assert manifest['source'] == SOURCE
    assert digest(CONFIG) == before['configSha256']
    for path, expected in before['envFiles'].items(): assert digest(path) == expected
    assert schema() == before['schemaSha256']
    assert database.stat().st_ino == before['databaseInode']
    assert not output(['git', '-C', str(ROOT), 'status', '--short']).strip()
    original = json.loads(CONFIG.read_text())
    desired = json.loads((WORK / CONFIG.name).read_text())
    expected = json.loads(CONFIG.read_text())
    for name in ['server', 'worker', 'web']:
        expected['services'][name]['image'] = manifest['images']['web' if name == 'web' else 'server']['tag']
    assert desired == expected, 'Only the three application image references may change'
    old_runtime = {name: inspect(name) for name in original['services']}
    for name, item in old_runtime.items(): assert item['Image'] == before['containers'][name]['image']
    old_env = {name: env_hashes(item) for name, item in old_runtime.items()}
    archive = WORK / 'images.tar.gz'
    assert digest(archive) == manifest['archiveSha256'] == 'aec94fd0c17980e503ea9400f73bbdb2aa93cd5185885ce843b6f6ae8aec8748'
    phase = 'load-images'
    run(['docker', 'load', '-i', str(archive)], 'image-load')
    for name, image in manifest['images'].items():
        actual = json.loads(output(['docker', 'image', 'inspect', image['tag']]))[0]
        assert actual['Id'] == image['id']
        assert actual['Architecture'] == 'amd64' and actual['Config']['User'] == '10001:10001'
        assert actual['Config']['Labels']['sjtuow.source'] == SOURCE
        assert actual['Config']['Labels']['org.opencontainers.image.revision'] == SOURCE
    run(['docker', 'compose', '-p', 'sjtu-ow-next', '-f', str(WORK / CONFIG.name), '--env-file', '/dev/null', 'config', '--quiet'], 'compose-validate')
    log('IMAGES-VERIFIED', source=SOURCE, archiveSha256=manifest['archiveSha256'])
    phase = 'source-checkout'
    run(['git', '-C', str(ROOT), 'fetch', 'origin'], 'git-fetch')
    run(['git', '-C', str(ROOT), 'merge', '--ff-only', SOURCE], 'git-fast-forward')
    assert output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD']).strip() == SOURCE
    fs = os.statvfs(ROOT)
    assert fs.f_bavail / fs.f_blocks >= 0.25 and fs.f_bavail * fs.f_frsize >= 5 * 1024**3
    phase = 'replace-worker'
    install_config(desired)
    switched = True
    run([*compose, 'stop', '--timeout', '30', 'worker'], 'stop-worker')
    assert not inspect('worker')['State']['Running']
    wait_worker_lock()
    since = dt.datetime.now(dt.timezone.utc)
    run([*compose, 'up', '-d', '--no-build', '--pull', 'never', '--no-deps', 'worker'], 'start-worker')
    fresh_worker = wait_new_worker(since)
    assert inspect('worker')['Image'] == manifest['images']['server']['id']
    log('NEW-WORKER-VERIFIED', **fresh_worker)
    phase = 'replace-server-web'
    run([*compose, 'stop', '--timeout', '30', 'server'], 'stop-server')
    assert not inspect('server')['State']['Running']
    run([*compose, 'up', '-d', '--no-build', '--pull', 'never', '--no-deps', 'server', 'web'], 'start-server-web')
    current_health = wait_healthy()
    current = {name: inspect(name) for name in original['services']}
    for name, item in current.items():
        assert item['State']['Running']
        assert mounts(item) == mounts(old_runtime[name])
        assert (item['HostConfig'].get('PortBindings') or {}) == (old_runtime[name]['HostConfig'].get('PortBindings') or {})
        assert set(item['NetworkSettings']['Networks']) == set(old_runtime[name]['NetworkSettings']['Networks'])
        assert env_hashes(item) == old_env[name]
        if name != 'proxy': assert item['Image'] == manifest['images']['web' if name == 'web' else 'server']['id']
    assert current['proxy']['Id'] == old_runtime['proxy']['Id']
    for path, expected_hash in before['envFiles'].items(): assert digest(path) == expected_hash
    binary_hash = output(['docker', 'exec', current['server']['Id'], 'sha256sum', '/srv/sjtuow/sjtuow']).split()[0]
    assert binary_hash == manifest['goBinarySha256']
    asset_root = Path(next(mount['Source'] for mount in current['web']['Mounts'] if mount['Destination'] == '/var/assets'))
    deadline = time.monotonic() + 45
    while True:
        try:
            for relative, expected_hash in manifest['assets'].items():
                path = (asset_root / relative).resolve()
                assert path.is_relative_to(asset_root.resolve())
                assert digest(path) == expected_hash
            break
        except (AssertionError, FileNotFoundError):
            if time.monotonic() >= deadline: raise
            time.sleep(1)
    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as db:
        assert db.execute('PRAGMA quick_check').fetchone() == ('ok',)
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
        counts = {name: db.execute('SELECT count(*) FROM ' + name).fetchone()[0] for name in before['counts']}
        passwords = db.execute('SELECT id,password_hash FROM users ORDER BY id').fetchall()
    with sqlite3.connect((Path(before['backup']) / 'verified-snapshot.sqlite3').as_uri() + '?mode=ro', uri=True) as snapshot:
        passwords_match = passwords == snapshot.execute('SELECT id,password_hash FROM users ORDER BY id').fetchall()
    assert schema() == before['schemaSha256'] and database.stat().st_ino == before['databaseInode']
    fs = os.statvfs(ROOT)
    after = {'source': SOURCE, 'health': current_health, 'worker': fresh_worker, 'counts': counts, 'schemaUnchanged': True, 'databaseInodeUnchanged': True, 'passwordHashesMatchSnapshot': passwords_match, 'assetsMatched': len(manifest['assets']), 'binaryMatched': True, 'privateEnvironmentsUnchanged': True, 'freeBytes': fs.f_bavail * fs.f_frsize, 'images': {name: item['Image'] for name, item in current.items()}, 'completedAt': dt.datetime.now(dt.timezone.utc).isoformat()}
    (WORK / 'after.json').write_text(json.dumps(after, indent=2))
    log('DEPLOYMENT-HEALTHY', **after)
except Exception as error:
    log('DEPLOYMENT-FAILED', failedPhase=phase, errorType=type(error).__name__)
    if switched and schema() == before['schemaSha256']:
        log('ROLLBACK-IMAGES-ONLY', dataRestored=False)
        run([*compose, 'stop', '--timeout', '30', 'worker'], 'rollback-stop-worker')
        run([*compose, 'stop', '--timeout', '30', 'server'], 'rollback-stop-server')
        rollback = json.loads((Path(before['backup']) / 'rollback.compose.json').read_text())
        install_config(rollback)
        run([*compose, 'up', '-d', '--no-build', '--pull', 'never', '--no-deps', 'server', 'web'], 'rollback-server-web')
        wait_worker_lock()
        since = dt.datetime.now(dt.timezone.utc)
        run([*compose, 'up', '-d', '--no-build', '--pull', 'never', '--no-deps', 'worker'], 'rollback-worker')
        wait_new_worker(since)
        wait_healthy()
        log('ROLLBACK-HEALTHY', dataRestored=False)
    raise
