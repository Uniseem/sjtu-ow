#!/usr/bin/env bash
set -euo pipefail
base=${CHECK_DIR:-/srv/build/sjtu-ow}
mkdir -p "$base"
exec 9>"$base/prepare.lock"
flock 9
test "$(uname -m)" = x86_64
export CHECK_DIR="$base"

python3 - <<'PY'
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.request

base = Path(os.environ['CHECK_DIR'])
downloads = base / 'downloads'
downloads.mkdir(exist_ok=True)

def fetch(url):
    with urllib.request.urlopen(url, timeout=90) as response:
        return response.read()

def archive(url, expected):
    target = downloads / url.rsplit('/', 1)[1]
    if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest() != expected:
        target.write_bytes(fetch(url))
    if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
        raise RuntimeError('Archive checksum mismatch')
    return target

if not (base / 'go/bin/go').exists():
    releases = json.loads(fetch('https://go.dev/dl/?mode=json&include=all'))
    release = next(item for item in releases if item['version'] == 'go1.26.10')
    package = next(item for item in release['files'] if item['filename'] == 'go1.26.10.linux-amd64.tar.gz')
    target = archive('https://go.dev/dl/' + package['filename'], package['sha256'])
    subprocess.run(['tar', '-xzf', str(target), '-C', str(base)], check=True)

if not (base / 'node24/bin/node').exists():
    releases = json.loads(fetch('https://nodejs.org/dist/index.json'))
    version = next(item['version'] for item in releases if item['version'].startswith('v24.'))
    name = f'node-{version}-linux-x64.tar.xz'
    checksums = fetch(f'https://nodejs.org/dist/{version}/SHASUMS256.txt').decode()
    checksum = next(line.split()[0] for line in checksums.splitlines() if line.split()[-1] == name)
    target = archive(f'https://nodejs.org/dist/{version}/{name}', checksum)
    subprocess.run(['tar', '-xJf', str(target), '-C', str(base)], check=True)
    (base / 'node24').symlink_to(base / f'node-{version}-linux-x64')

PY

export PATH="$base/node24/bin:$base/go/bin:$base/gobin:$base/uv/bin:$PATH"
export GOROOT="$base/go" GOPATH="$base/gopath" GOCACHE="$base/gocache" GOMODCACHE="$base/gomodcache" GOBIN="$base/gobin"
if ! command -v pnpm >/dev/null; then
  npm install --global --prefix "$base/node24" pnpm@11.20.0
fi
if ! command -v uv >/dev/null; then
  curl --fail --silent --show-error --location --connect-timeout 15 --max-time 90 --retry 2 https://astral.sh/uv/install.sh -o "$base/downloads/uv-install.sh"
  UV_INSTALL_DIR="$base/uv/bin" UV_NO_MODIFY_PATH=1 sh "$base/downloads/uv-install.sh"
fi
if ! command -v chromium >/dev/null; then
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install --yes --no-install-recommends chromium fonts-noto-cjk
fi
if [ ! -d "$base/repo/.git" ]; then
  git clone --quiet --depth=1 --single-branch https://github.com/Uniseem/sjtu-ow.git "$base/repo"
fi
go version
node --version
pnpm --version
uv --version
chromium --version
df -h "$base"
