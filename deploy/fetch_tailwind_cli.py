"""Put the Tailwind CLI where django-tailwind-cli looks for it (round 144).

    python deploy/fetch_tailwind_cli.py VERSION TARGET_DIR

The Dockerfile runs this in its own layer before the code is copied in, so
a code change no longer downloads the 112 MB binary again and a GitHub
hiccup only hurts the first build. ``manage.py tailwind download_cli``
always downloads anew, which is why the image no longer calls it. Standard
library only: the layer comes before the project's dependencies.
"""

from __future__ import annotations

import hashlib
import os
import platform
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = "dobicinaitis/tailwind-cli-extra"
ARCHES = {"x86_64": "x64", "amd64": "x64", "aarch64": "arm64", "arm64": "arm64"}
ATTEMPTS = 5
# The binary runs during the image build, so it is checked first (216, C10).
# From the release page's own digests (GitHub lists one per file); bumping
# TAILWIND_CLI_VERSION means adding its two lines here, or the build stops.
SHA256 = {
    ("2.9.0", "x64"): (
        "eb0cbf7fd1ae873aa8d14702175a2d3854b8c4e4b1f4ca37113404017b6e68e1"
    ),
    ("2.9.0", "arm64"): (
        "869a11ac98d9a5b65223fabbce8e9c8d620fc53f65cbbaa461bc8782b6100fc6"
    ),
}


def arch(machine: str | None = None) -> str:
    machine = (machine or platform.machine()).lower()
    if machine not in ARCHES:
        raise SystemExit(f"不支持的架构：{machine}")
    return ARCHES[machine]


def url(version: str, machine: str | None = None) -> str:
    return (
        f"https://github.com/{REPO}/releases/download/v{version}/"
        f"tailwindcss-extra-linux-{arch(machine)}"
    )


def target_name(version: str, machine: str | None = None) -> str:
    """The file name django-tailwind-cli gives a managed download."""
    return f"tailwindcss-extra-linux-{arch(machine)}-{version}"


def expected_sha256(version: str, machine: str | None = None) -> str:
    try:
        return SHA256[(version, arch(machine))]
    except KeyError:
        raise SystemExit(
            f"没有 Tailwind 命令行 {version}（{arch(machine)}）的 sha256，"
            "先把发布页上的值加进 deploy/fetch_tailwind_cli.py"
        ) from None


def fetch(
    version: str,
    directory: Path,
    *,
    opener=urllib.request.urlopen,
    wait=2.0,
    expected: str | None = None,
):
    expected = expected or expected_sha256(version)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / target_name(version)
    partial = target.with_name(target.name + ".part")
    for attempt in range(1, ATTEMPTS + 1):
        try:
            with opener(url(version), timeout=120) as response:
                partial.write_bytes(response.read())
            break
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if attempt == ATTEMPTS:
                raise SystemExit(f"下载 Tailwind 命令行失败：{exc}") from exc
            print(f"下载失败（{exc}），{wait * attempt:.0f} 秒后重试", file=sys.stderr)
            time.sleep(wait * attempt)
    got = hashlib.sha256(partial.read_bytes()).hexdigest()
    if got != expected:
        partial.unlink()
        raise SystemExit(f"Tailwind 命令行的 sha256 不对：{got}，应为 {expected}")
    partial.replace(target)
    os.chmod(target, 0o755)
    return target


def main(argv):
    version, directory = argv[1], Path(argv[2])
    print(f"Tailwind 命令行在 {fetch(version, directory)}")


if __name__ == "__main__":
    main(sys.argv)
