"""The test run leaves the developer's files alone (round 104)."""

from pathlib import Path

import pytest


@pytest.mark.django_db
def test_uploads_in_tests_never_reach_the_project_media_folder(settings):
    """Images saved by tests piled up in media/ and rode along in a demo
    backup (rounds 101, 102)."""
    from content.tests.test_content import _image

    image = _image("isolation")
    project_media = (Path(settings.BASE_DIR) / "media").resolve()
    saved = Path(image.file.path).resolve()
    assert project_media not in saved.parents
