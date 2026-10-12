"""D4's sole download-format exception: TTF becomes an importable offline ZIP.

Verify real bytes and reimport via a real isolated Go HTTP process. The global
visual fixture is never changed by the round trip. No outbound service is used.
"""
import base64
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import time
import urllib.request


def check(old_url, new_api, old_cookie, new_cookie, face_id, env, work):
    from fontTools.ttLib import TTFont

    def get(url, cookie):
        with urllib.request.urlopen(urllib.request.Request(url, headers={'Cookie': cookie}), timeout=20) as response:
            return response.read()
    original = get(old_url, old_cookie)
    with TTFont(io.BytesIO(original)) as font:
        if not font.getBestCmap():
            raise RuntimeError('legacy downloaded font cannot be decoded')
    downloaded = json.loads(get(new_api + f'/api/admin/fonts/weights/{face_id}/download', new_cookie))
    package = base64.b64decode(downloaded['data_base64'], validate=True)
    if not package.startswith(b'PK') or not downloaded['filename'].endswith('.zip'):
        raise RuntimeError('D4 download is not an offline font package')
    isolated = Path(tempfile.mkdtemp(prefix='font-download-roundtrip-', dir=work))
    process = None
    try:
        data = isolated / 'data'
        data.mkdir()
        with sqlite3.connect(work / 'new-data/sjtuow.sqlite3') as source, sqlite3.connect(data / 'sjtuow.sqlite3') as target:
            source.backup(target)
        import socket
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        endpoint = f'http://127.0.0.1:{port}'
        clone_env = {**env, 'DATA_DIR': str(data), 'MEDIA_DIR': str(isolated / 'media'), 'SJTUOW_HTTP_ADDR': f'127.0.0.1:{port}'}
        process = subprocess.Popen([str(work / 'sjtuow'), 'serve'], env=clone_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                get(endpoint + '/robots.txt', '')
                break
            except OSError:
                time.sleep(.05)
        else:
            raise RuntimeError('isolated font import server did not start')
        body = json.dumps({'source': 'package', 'package_name': downloaded['filename'], 'package_base64': downloaded['data_base64'], 'license_confirmed': True}).encode()
        request = urllib.request.Request(endpoint + '/api/admin/fonts', data=body, headers={'Content-Type': 'application/json', 'Cookie': new_cookie}, method='POST')
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.load(response)
        if not result.get('font', {}).get('id'):
            raise RuntimeError('downloaded package did not create a real font')
        with sqlite3.connect(data / 'sjtuow.sqlite3') as database:
            faces = database.execute('SELECT slices FROM font_faces WHERE family_id=?', (result['font']['id'],)).fetchall()
        if not faces:
            raise RuntimeError('downloaded package lost its real face')
        for (encoded,) in faces:
            for piece in json.loads(encoded):
                with TTFont(isolated / 'media' / piece['path']) as font:
                    if not font.getBestCmap():
                        raise RuntimeError('reimported slice cannot be decoded')
    finally:
        if process:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        shutil.rmtree(isolated)
    return 'design-next.md D4 / §2：旧TTF下载改离线成品ZIP，真实字节与隔离Go重导入通过'
