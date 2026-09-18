"""The worker follows collectstatic's manifest across upgrades (round 064)."""

import json
import os

import pytest
from django.templatetags.static import static

from core import prerender

MANIFEST = "staticfiles.json"


@pytest.fixture(
    params=[
        "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
        "whitenoise.storage.CompressedManifestStaticFilesStorage",  # production
    ]
)
def manifest_storage(request, settings, tmp_path, monkeypatch):
    settings.STATIC_ROOT = tmp_path
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": request.param},
    }
    monkeypatch.setattr(prerender, "_manifest_seen", None)
    return tmp_path


def _write(root, digest, bump=0):
    path = root / MANIFEST
    paths = {"css/app.css": f"css/app.{digest}.css"}
    path.write_text(json.dumps({"version": "1.1", "hash": digest, "paths": paths}))
    stamp = 1_800_000_000_000_000_000 + bump
    os.utime(path, ns=(stamp, stamp))


def test_a_new_manifest_is_picked_up_without_a_restart(manifest_storage):
    _write(manifest_storage, "aaaaaaaaaaaa")
    assert static("css/app.css") == "/static/css/app.aaaaaaaaaaaa.css"

    # web's collectstatic on the new version rewrites the manifest.
    _write(manifest_storage, "bbbbbbbbbbbb", bump=1)
    assert static("css/app.css") == "/static/css/app.aaaaaaaaaaaa.css"  # cached

    assert prerender.refresh_static_manifest() is True
    assert static("css/app.css") == "/static/css/app.bbbbbbbbbbbb.css"


def test_an_unchanged_manifest_is_not_reread(manifest_storage):
    _write(manifest_storage, "aaaaaaaaaaaa")
    prerender.refresh_static_manifest()
    assert prerender.refresh_static_manifest() is False


def test_storage_without_a_manifest_is_left_alone(settings, monkeypatch):
    monkeypatch.setattr(prerender, "_manifest_seen", None)
    assert prerender.refresh_static_manifest() is False


@pytest.mark.django_db
def test_every_render_checks_the_manifest_first(monkeypatch):
    calls = []
    monkeypatch.setattr(prerender, "refresh_static_manifest", lambda: calls.append(1))
    with pytest.raises(prerender.PrerenderError):
        prerender.render_html("/no-such-page/")
    assert calls == [1]
