"""Round 144: the Tailwind CLI is fetched once per version, not per build.

``manage.py tailwind download_cli`` downloads the 112 MB binary anew every
time; when GitHub answered 503 the image build and the checks both failed.
"""

import hashlib
import io
import os
import re
import sys
import urllib.error
from pathlib import Path

import pytest
from django.conf import settings

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "deploy"))
import fetch_tailwind_cli as fetcher  # noqa: E402


def _dockerfile():
    return (ROOT / "Dockerfile").read_text(encoding="utf-8")


def test_the_image_pins_the_same_version_as_the_settings():
    pinned = re.search(r"^ARG TAILWIND_CLI_VERSION=(\S+)$", _dockerfile(), re.M)
    assert pinned and pinned.group(1) == settings.TAILWIND_CLI_VERSION


def test_the_image_fetches_before_the_code_and_never_redownloads():
    dockerfile = _dockerfile()
    assert "tailwind download_cli" not in dockerfile
    assert dockerfile.index("fetch_tailwind_cli.py") < dockerfile.index("COPY . .")


def test_the_check_script_downloads_only_when_missing():
    script = (ROOT / "scripts/check.sh").read_text(encoding="utf-8")
    assert "ls .django_tailwind_cli/tailwindcss* >/dev/null 2>&1 ||" in script


@pytest.mark.skipif(sys.platform != "linux", reason="names are per platform")
def test_names_match_what_django_tailwind_cli_expects():
    from django_tailwind_cli.config import get_config

    config = get_config()
    version = settings.TAILWIND_CLI_VERSION
    assert fetcher.target_name(version) == config.cli_path.name
    assert fetcher.url(version) == config.download_url


def test_names_per_architecture():
    assert fetcher.target_name("2.9.0", "x86_64") == "tailwindcss-extra-linux-x64-2.9.0"
    assert fetcher.url("2.9.0", "aarch64").endswith(
        "/v2.9.0/tailwindcss-extra-linux-arm64"
    )
    with pytest.raises(SystemExit):
        fetcher.arch("sparc")


def test_a_flaky_download_is_retried(tmp_path):
    calls = []

    def opener(url, timeout):
        calls.append(url)
        if len(calls) < 3:
            raise urllib.error.HTTPError(url, 503, "Service Unavailable", {}, None)
        return io.BytesIO(b"binary")

    target = fetcher.fetch(
        "2.9.0",
        tmp_path,
        opener=opener,
        wait=0,
        expected=hashlib.sha256(b"binary").hexdigest(),
    )
    assert len(calls) == 3
    assert target.read_bytes() == b"binary"
    assert os.access(target, os.X_OK) or sys.platform == "win32"


def test_a_binary_that_does_not_match_its_digest_is_refused(tmp_path):
    """216, C10: the build runs what it downloaded; a swapped file on the
    release page (or on the way) must stop the build, and leave nothing."""

    def opener(url, timeout):
        return io.BytesIO(b"something else")

    with pytest.raises(SystemExit, match="sha256 不对"):
        fetcher.fetch("2.9.0", tmp_path, opener=opener, wait=0)
    assert not list(tmp_path.iterdir())


def test_every_architecture_of_the_pinned_version_has_a_digest():
    for machine in ("x86_64", "aarch64"):
        digest = fetcher.expected_sha256(settings.TAILWIND_CLI_VERSION, machine)
        assert re.fullmatch(r"[0-9a-f]{64}", digest)
    with pytest.raises(SystemExit, match="没有 Tailwind 命令行"):
        fetcher.expected_sha256("0.0.1", "x86_64")


def test_giving_up_says_so(tmp_path):
    def opener(url, timeout):
        raise urllib.error.URLError("down")

    with pytest.raises(SystemExit, match="下载 Tailwind 命令行失败"):
        fetcher.fetch("2.9.0", tmp_path, opener=opener, wait=0)
    assert not list(tmp_path.iterdir())
