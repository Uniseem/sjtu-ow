"""The 默认头像 pool (design-details 2.4, v6.9, round 111).

People without a picture take a face from the Wagtail collection 「默认头像」
by ID mod size; their own picture wins; closed accounts and an empty pool
keep the 底图 and the initial. One look at the pool per page, and changes to
the pool or to whether an account is open regenerate the pages.
"""

from io import BytesIO
from pathlib import Path
from unittest import mock

import pytest
from django.conf import settings as django_settings
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.template.loader import render_to_string
from PIL import Image as PILImage

from core.avatars import DEFAULT_AVATAR_COLLECTION
from core.tests.test_chapter15_audit import assert_no_n_plus_one, make_user


@pytest.fixture(autouse=True)
def _media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


def _pool():
    from wagtail.models import Collection

    return Collection.objects.get(name=DEFAULT_AVATAR_COLLECTION)


def _face(collection, name="face"):
    from wagtail.images.models import Image

    buffer = BytesIO()
    PILImage.new("RGBA", (64, 64), (200, 120, 40, 255)).save(buffer, "PNG")
    return Image.objects.create(
        title=name,
        width=64,
        height=64,
        collection=collection,
        file=ContentFile(buffer.getvalue(), name=f"{name}.png"),
    )


def _bare(index):
    """Someone who never set a picture."""
    user = make_user(index)
    user.avatar = None
    user.save()
    return user


def _verified(user):
    from allauth.account.models import EmailAddress

    EmailAddress.objects.create(
        user=user, email=user.email, verified=True, primary=True
    )
    return user


def _render(user, **extra):
    return render_to_string("components/avatar.html", {"person": user, **extra})


# --- who gets which face -----------------------------------------------------------


@pytest.mark.django_db
def test_init_site_makes_the_pool(site):
    assert _pool().name == DEFAULT_AVATAR_COLLECTION


@pytest.mark.django_db
def test_someone_without_a_picture_gets_a_pool_face(site):
    faces = [_face(_pool(), f"face{index}") for index in range(3)]
    user = _bare(5)
    face = faces[user.pk % 3]
    html = _render(user, size="md")
    assert face.get_rendition("fill-176x176").url in html
    assert 'loading="lazy"' in html
    assert "审" not in html  # no initial over the face
    small = _render(user, size="sm")
    assert face.get_rendition("fill-88x88").url in small


@pytest.mark.django_db
def test_each_person_keeps_their_own_face(site):
    from core import avatars

    faces = [_face(_pool(), f"face{index}") for index in range(3)]
    first, second = _bare(6), _bare(7)
    assert avatars.pick(first, faces) != avatars.pick(second, faces)
    assert avatars.pick(first, faces) == faces[first.pk % 3]


@pytest.mark.django_db
def test_their_own_picture_wins(site):
    from core import avatars

    faces = [_face(_pool(), "face")]
    user = make_user(8)  # has a picture of their own
    assert avatars.pick(user, faces) is None
    html = _render(user, size="md")
    assert user.avatar.get_rendition("fill-176x176").url in html
    assert faces[0].get_rendition("fill-176x176").url not in html


@pytest.mark.django_db
def test_closed_accounts_keep_the_initial(site):
    from accounts.services import delete_account

    _face(_pool(), "face")
    banned = _bare(9)
    banned.is_active = False
    banned.save()
    html = _render(banned)
    assert "<img" not in html
    assert "审" in html
    deleted = _bare(10)
    delete_account(deleted)
    deleted.refresh_from_db()
    assert "<img" not in _render(deleted)


@pytest.mark.django_db
def test_an_empty_pool_keeps_the_initial(site):
    html = _render(_bare(11))
    assert "<img" not in html
    assert "审" in html


@pytest.mark.django_db
def test_the_folders_under_the_pool_count_and_others_do_not(site):
    from wagtail.models import Collection

    from core import avatars

    folder = _pool().add_child(name="英雄")
    inside = _face(folder, "inside")
    _face(Collection.get_first_root_node(), "elsewhere")
    _face(Collection.objects.get(name="默认封面"), "a-cover")
    assert [image.pk for image in avatars.load_pool()] == [inside.pk]
    user = _bare(12)
    assert inside.get_rendition("fill-88x88").url in _render(user)


# --- where faces are -----------------------------------------------------------------


@pytest.mark.django_db
def test_the_member_card_uses_the_pool_too(client, site):
    from members.models import MemberGroup, MemberGroupMembership

    face = _face(_pool(), "face")
    user = _verified(_bare(13))
    group = MemberGroup.objects.create(name="管理组")
    MemberGroupMembership.objects.create(group=group, user=user, title="社长")
    html = client.get("/members/").content.decode()
    assert face.get_rendition("fill-400x400").url in html  # the big card (4.2)
    assert face.get_rendition("fill-176x176").url in html  # 全部成员 (4.4)


def test_no_template_prints_the_initial_without_trying_the_pool():
    """Every place an initial would be drawn tries the pool first."""
    offenders = []
    for path in Path(django_settings.BASE_DIR).rglob("*.html"):
        if any(part in {".venv", "node_modules", "prerendered"} for part in path.parts):
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "nickname|initial" in line and "default_avatar" not in line:
                offenders.append(f"{path.as_posix()}:{number}")
    assert offenders == []


@pytest.mark.django_db
def test_a_long_list_looks_at_the_pool_once(client, site):
    from accounts.models import User
    from members.models import MemberGroup, MemberGroupMembership

    # More faces than people, so a per-person lookup cannot hide behind a
    # small pool (109's lesson).
    for index in range(12):
        _face(_pool(), f"face{index}")
    group = MemberGroup.objects.create(name="管理组")

    def seed(count):
        start = User.objects.count() + 300
        for index in range(count):
            user = _verified(_bare(start + index))
            MemberGroupMembership.objects.create(group=group, user=user, title="")

    assert_no_n_plus_one(client, "/members/", seed)


# --- keeping the pages in step -------------------------------------------------------


@pytest.mark.django_db
def test_changes_to_the_pool_regenerate_the_site(site):
    from wagtail.models import Collection

    with mock.patch("core.prerender.request_all_soon") as regenerate:
        face = _face(_pool(), "new")
        assert regenerate.call_count == 1  # a new face
        face.collection = Collection.get_first_root_node()
        face.save()
        assert regenerate.call_count == 2  # moved out
        face.collection = _pool()
        face.save()
        assert regenerate.call_count == 3  # moved back
        face.delete()
        assert regenerate.call_count == 4  # deleted


@pytest.mark.django_db
def test_closing_or_reopening_an_account_regenerates_its_pages(site):
    user = _bare(14)
    with mock.patch("accounts.signals.refresh_nickname_pages") as refresh:
        user.is_active = False
        user.save(update_fields=["is_active"])
        assert refresh.call_count == 1
        user.is_active = True
        user.save()
        assert refresh.call_count == 2


# --- by main position (v6.10, round 113) ---------------------------------------------


def _with_role(index, role):
    user = _bare(index)
    user.main_role = role
    user.save()
    return user


def _role_folders():
    pool = _pool()
    return {
        "tank": pool.add_child(name="坦克"),
        "damage": pool.add_child(name="输出"),
        "support": pool.add_child(name="支援"),
    }


@pytest.mark.django_db
def test_a_tank_gets_a_tank_face_and_a_support_a_support_face(site):
    from core import avatars

    folders = _role_folders()
    tanks = [_face(folders["tank"], f"tank{index}") for index in range(2)]
    _face(folders["damage"], "damage")
    support = _face(folders["support"], "support")
    pool = avatars.load_pool()
    tank_player = _with_role(20, "tank")
    assert avatars.pick(tank_player, pool) == tanks[tank_player.pk % 2]
    assert avatars.pick(_with_role(21, "support"), pool) == support
    html = _render(tank_player, size="md")
    assert tanks[tank_player.pk % 2].get_rendition("fill-176x176").url in html


@pytest.mark.django_db
def test_without_a_main_position_any_face(site):
    from core import avatars

    folders = _role_folders()
    faces = [
        _face(folders["tank"], "tank"),
        _face(folders["damage"], "damage"),
        _face(_pool(), "loose"),
    ]
    pool = avatars.load_pool()
    # Three people in a row get the three faces, whatever folder they are in.
    people = [_with_role(index, "") for index in (30, 31, 32)]
    assert {avatars.pick(user, pool) for user in people} == set(faces)
    assert avatars.pick(people[0], pool) == faces[people[0].pk % 3]


@pytest.mark.django_db
def test_an_empty_position_folder_falls_back_to_the_whole_pool(site):
    from core import avatars

    folders = _role_folders()
    faces = [_face(folders["tank"], "tank"), _face(folders["damage"], "damage")]
    user = _with_role(23, "support")  # 支援 is there but empty
    assert avatars.pick(user, avatars.load_pool()) == faces[user.pk % 2]


@pytest.mark.django_db
def test_folders_under_a_position_folder_count_for_it(site):
    from core import avatars

    folders = _role_folders()
    reinhardt = _face(folders["tank"].add_child(name="莱因哈特"), "reinhardt")
    _face(folders["damage"], "damage1")
    _face(folders["damage"], "damage2")
    pool = avatars.load_pool()
    # The only tank face, for every tank player (two in a row, so a miss on
    # the folder cannot land on it by chance).
    for index in (40, 41):
        assert avatars.pick(_with_role(index, "tank"), pool) == reinhardt


@pytest.mark.django_db
def test_loading_the_pool_costs_the_same_however_many_faces(site):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    from core import avatars

    folders = _role_folders()

    def looks():
        with CaptureQueriesContext(connection) as queries:
            avatars.load_pool()
        return len(queries)

    for index in range(3):
        _face(folders["tank"], f"few{index}")
    few = looks()
    for index in range(9):
        _face(folders["support"], f"many{index}")
    assert looks() == few


@pytest.mark.django_db
def test_without_a_main_position_the_first_other_one_counts(site):
    """The small card in the member list shows one position: the main one,
    or else the first under 也能打; the face follows it."""
    from core import avatars

    folders = _role_folders()
    tank = _face(folders["tank"], "tank")
    damage = _face(folders["damage"], "damage")
    _face(folders["support"], "support")
    pool = avatars.load_pool()
    for index, others, face in (
        (50, "support,damage", damage),
        (51, "damage,support", damage),
        (52, "tank,damage,support", tank),
    ):
        user = _with_role(index, "")
        user.flex_roles = others
        assert avatars.pick(user, pool) == face, others
