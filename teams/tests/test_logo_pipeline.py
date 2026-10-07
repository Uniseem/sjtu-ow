"""The team logo through the one upload pipeline (219).

217 review 07-1: a logo whose EXIF block was broken made every page showing
it a 500, the captain's own manage page included, and left the home page and
the team list stuck on their old static copy. 07-2: no pixel limit. 07-3: the
original, GPS and all, was public. 07-4: QOI named .png was a 500. 07-11: a
replaced or removed logo stayed on the disk.
"""

import io
import json

import pytest
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from PIL import Image
from wagtail.images import get_image_model
from wagtail.models import Collection

from accounts.tests.test_onboarding import _user
from content.services import TEAM_LOGO_COLLECTION
from core import uploads
from core.tests.test_upload_pipeline import (
    SECRET_MAKER,
    _broken_exif_png,
    _jpeg,
    _qoi,
)
from teams import services
from teams.models import Team

AUTOSAVE = {"HTTP_X_AUTOSAVE": "1", "HTTP_ACCEPT": "application/json"}


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


@pytest.fixture
def captain(site, client):
    user = _user("logo-captain@example.com")
    client.force_login(user)
    return user


def _file(data, name="logo.png"):
    return SimpleUploadedFile(name, data)


def _create(client, logo, name="标志队"):
    return client.post(
        reverse("team_create"),
        {"name": name, "description": "", "is_recruiting": "on", "logo_file": logo},
    )


def _profile(team, **changes):
    data = {
        "form": "profile",
        "name": team.name,
        "description": team.description,
        "is_recruiting": "on",
        "member_contact": team.member_contact,
    }
    data.update(changes)
    return data


@pytest.mark.django_db
def test_a_phone_photo_becomes_a_clean_logo_in_its_own_collection(client, captain):
    response = _create(client, _file(_jpeg((900, 600), orientation=6), "IMG_77.jpg"))
    assert response.status_code == 302
    team = Team.objects.get()
    logo = team.logo
    assert logo.collection.name == TEAM_LOGO_COLLECTION
    assert (logo.width, logo.height) == (600, 900)
    logo.file.open("rb")
    stored = logo.file.read()
    logo.file.close()
    assert SECRET_MAKER.encode() not in stored and "IMG_77" not in logo.file.name
    assert not Image.open(io.BytesIO(stored)).getexif().get_ifd(0x8825)


@pytest.mark.django_db
def test_every_page_that_shows_a_logo_answers(client, captain):
    """07-1: the detail page, the list, the manage page, the captain's own
    page, the member list and the home page all show it."""
    _create(client, _file(_jpeg()))
    team = Team.objects.get()
    for url in (
        reverse("team_detail", args=[team.pk]),
        reverse("team_index"),
        reverse("team_manage", args=[team.pk]),
        reverse("member_detail", args=[captain.pk]),
        reverse("members"),
        "/",
    ):
        assert client.get(url).status_code == 200, url


@pytest.mark.django_db
@pytest.mark.parametrize(
    "data, name, message",
    [
        (_broken_exif_png(), "broken.png", "读不出"),
        (_qoi(), "one.png", "JPG、PNG 或 WebP"),
        (b"MZ not a picture", "logo.png", "请上传一张有效的图片"),
    ],
)
def test_a_logo_nobody_can_use_is_a_message_on_the_field(
    client, captain, data, name, message
):
    response = _create(client, _file(data, name))
    assert response.status_code == 200  # the form again, not a 500
    assert message in str(response.context["form"].errors["logo_file"])
    assert not Team.objects.exists() and not get_image_model().objects.exists()


@pytest.mark.django_db
def test_a_logo_of_too_many_pixels_is_refused(client, captain):
    """A grey 7000 x 6000 PNG is a few KB and 42 million pixels."""
    buffer = io.BytesIO()
    Image.new("L", (7000, 6000), 128).save(buffer, "PNG")
    assert len(buffer.getvalue()) < 5 * 1024 * 1024
    response = _create(client, _file(buffer.getvalue()))
    assert response.status_code == 200
    assert "太大" in str(response.context["form"].errors["logo_file"])
    assert not Team.objects.exists()


@pytest.mark.django_db
def test_the_captains_autosave_refuses_a_bad_logo_and_keeps_the_team(client, captain):
    team = services.create_team(user=captain, name="存盘队")
    answer = json.loads(
        client.post(
            reverse("team_manage", args=[team.pk]),
            {**_profile(team), "logo_file": _file(_broken_exif_png())},
            **AUTOSAVE,
        ).content
    )
    assert "logo_file" in answer["errors"] and "logo_file" not in answer["saved"]
    team.refresh_from_db()
    assert team.logo is None


@pytest.mark.django_db
def test_the_days_pictures_count_for_logos_too(client, captain, monkeypatch):
    monkeypatch.setattr(uploads, "UPLOADS_PER_DAY", 1)
    assert _create(client, _file(_jpeg()), "第一队").status_code == 302
    response = _create(client, _file(_jpeg()), "第二队")
    assert response.status_code == 200
    assert uploads.TOO_MANY in str(response.context["form"].errors["logo_file"])
    assert Team.objects.count() == 1


# --- a logo nobody uses any more goes (07-11) --------------------------------------


def _files_of(image):
    names = [image.file.name]
    names += [rendition.file.name for rendition in image.renditions.all()]
    return names


def _queued_for_deletion():
    """Wagtail 8 deletes a picture's files in a task the worker runs, not at
    once: these are the paths queued so far."""
    from django_tasks_db.models import DBTaskResult

    return {
        row.args_kwargs["args"][1]
        for row in DBTaskResult.objects.filter(
            task_path="wagtail.tasks.delete_file_from_storage_task"
        )
    }


def _run_queued_deletions():
    """What the worker does with them."""
    from django_tasks_db.models import DBTaskResult
    from wagtail.tasks import delete_file_from_storage_task

    for row in DBTaskResult.objects.filter(
        task_path="wagtail.tasks.delete_file_from_storage_task"
    ):
        delete_file_from_storage_task.func(*row.args_kwargs["args"])


@pytest.mark.django_db(transaction=True)
def test_a_replaced_logo_takes_its_file_and_thumbnails_with_it(client, captain):
    _create(client, _file(_jpeg()))
    team = Team.objects.get()
    client.get(reverse("team_detail", args=[team.pk]))  # makes the thumbnails
    old = team.logo
    old_files = _files_of(old)
    assert len(old_files) > 1 and all(default_storage.exists(n) for n in old_files)

    client.post(
        reverse("team_manage", args=[team.pk]),
        {**_profile(team), "logo_file": _file(_jpeg((200, 200)))},
    )
    team.refresh_from_db()
    assert team.logo_id != old.pk
    assert not get_image_model().objects.filter(pk=old.pk).exists()
    # The worker deletes the files; until it runs they are only queued.
    assert set(old_files) <= _queued_for_deletion()
    _run_queued_deletions()
    assert not any(default_storage.exists(n) for n in old_files)


@pytest.mark.django_db(transaction=True)
def test_a_removed_logo_goes_and_so_does_one_replaced_by_autosave(client, captain):
    _create(client, _file(_jpeg()))
    team = Team.objects.get()
    first = team.logo
    client.post(
        reverse("team_manage", args=[team.pk]),
        {**_profile(team), "logo_file": _file(_jpeg((120, 120)))},
        **AUTOSAVE,
    )
    team.refresh_from_db()
    second = team.logo
    assert second.pk != first.pk and not get_image_model().objects.filter(pk=first.pk)
    assert first.file.name in _queued_for_deletion()
    client.post(
        reverse("team_manage", args=[team.pk]),
        _profile(team, remove_logo="on"),
        **AUTOSAVE,
    )
    team.refresh_from_db()
    assert team.logo is None
    assert not get_image_model().objects.filter(pk=second.pk).exists()
    assert second.file.name in _queued_for_deletion()


@pytest.mark.django_db(transaction=True)
def test_a_picture_that_is_not_ours_to_delete_stays(client, captain, site):
    """A logo chosen from the shared library, or one two teams use, is not
    removed when a team lets go of it."""
    root = Collection.get_first_root_node()
    library = get_image_model().objects.create(
        title="资料库里的图",
        file=_file(_jpeg(), "lib.jpg"),
        collection=root,
    )
    team = services.create_team(user=captain, name="选图队", logo=library)
    services.update_team(
        team=team,
        user=captain,
        name=team.name,
        description="",
        logo=None,
        is_recruiting=True,
    )
    assert get_image_model().objects.filter(pk=library.pk).exists()
    assert library.file.name not in _queued_for_deletion()

    _create(client, _file(_jpeg()), "共用队甲")
    mine = Team.objects.get(name="共用队甲")
    shared = mine.logo
    other_captain = _user("other-logo@example.com")
    other = services.create_team(user=other_captain, name="共用队乙", logo=shared)
    services.update_team(
        team=mine,
        user=captain,
        name=mine.name,
        description="",
        logo=None,
        is_recruiting=True,
    )
    assert get_image_model().objects.filter(pk=shared.pk).exists()
    assert shared.file.name not in _queued_for_deletion()
    other.refresh_from_db()
    assert other.logo_id == shared.pk
