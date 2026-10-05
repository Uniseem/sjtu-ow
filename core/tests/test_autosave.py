"""Round 202 (design 13.17, v7.6): editing saves itself.

The user, 10-05: 「……应当是上传后自动就保存替换，其他的更改也一样，全站的后台都
是，都给我改成自动保存，无需手动保存」. The page posts the form with
X-Autosave: 1; the view keeps every changed field that is fine, leaves the
ones with errors as stored, says why, and never redirects.
"""

from datetime import timedelta
from unittest import mock

import pytest
from django import forms
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from wagtail.images import get_image_model
from wagtail.models import Collection, ModelLogEntry

from accounts.models import ContactMethod, GameAccount, User
from accounts.services import GROUP_CONTENT, GROUP_SUBMITTER
from accounts.tests.test_onboarding import _user
from core import autosave
from core.models import SiteSettings, TypographyRule
from members.models import MemberGroup
from moderation import services as moderation
from moderation.models import ModerationItem, TargetType

AUTOSAVE = {"HTTP_X_AUTOSAVE": "1"}


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


def _root(email="root202@example.com"):
    user = _user(email)
    User.objects.filter(pk=user.pk).update(is_superuser=True, is_staff=True)
    return User.objects.get(pk=user.pk)


def _save(client, url, data):
    response = client.post(url, data, **AUTOSAVE)
    assert response.status_code == 200, response.content[:500]
    assert response["Content-Type"].startswith("application/json")
    return response.json()


# --- the rule ---------------------------------------------------------------------


class _Rules(forms.ModelForm):
    """A form with a rule across fields, to see what autosave does with it."""

    class Meta:
        model = User
        fields = ("nickname", "motto")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("motto") == "冲突":
            raise forms.ValidationError("两项对不上。")
        return cleaned


@pytest.mark.django_db
def test_a_rule_across_fields_holds_back_what_it_names_or_everything(site):
    person = _user("rules202@example.com")
    data = {"nickname": "新的名字", "motto": "冲突"}
    assert autosave.save_valid_fields(_Rules(data, instance=person)) == []
    person.refresh_from_db()
    assert person.nickname != "新的名字"  # nothing named: nothing saved

    class Named(_Rules):
        autosave_together = ("motto",)

    assert autosave.save_valid_fields(Named(data, instance=person)) == ["nickname"]
    person.refresh_from_db()
    assert person.nickname == "新的名字" and person.motto != "冲突"


@pytest.mark.django_db
def test_the_profile_keeps_what_is_fine_and_says_what_is_not(site, client):
    person = _user("me202@example.com")
    client.force_login(person)
    url = reverse("me_profile")
    before = person.nickname
    answer = _save(client, url, {"nickname": "", "is_sjtu": "false", "motto": "周五见"})
    person.refresh_from_db()
    assert person.motto == "周五见"
    assert person.nickname == before  # an empty nickname is not saved
    assert "nickname" in answer["errors"] and answer["ok"] is False
    assert "motto" in answer["saved"]
    answer = _save(
        client, url, {"nickname": "改好了", "is_sjtu": "false", "motto": "周五见"}
    )
    assert answer["ok"] is True and answer["errors"] == {}
    person.refresh_from_db()
    assert person.nickname == "改好了"
    # Without the header the form still submits and comes back as before.
    response = client.post(url, {"nickname": "整张提交", "is_sjtu": "false"})
    assert response.status_code == 302


@pytest.mark.django_db
def test_the_avatar_goes_as_soon_as_it_is_chosen(site, client):
    """「上传后自动就保存替换」: the form sends itself; its button is for
    pages without the script."""
    client.force_login(_user("face202@example.com"))
    html = client.get(reverse("me_profile")).content.decode()
    avatar = html[html.index('action="' + reverse("me_avatar_upload")) :]
    avatar = avatar[: avatar.index("</form>")]
    assert "data-autosubmit-file" in html.split(reverse("me_avatar_upload"))[1][:200]
    assert "data-autosave-button" in avatar and "data-autosubmit-status" in avatar
    profile = html[html.index('action="' + reverse("me_profile") + '"') :]
    assert "data-autosave" in profile[: profile.index(">")]


@pytest.mark.django_db
def test_a_game_id_being_edited_saves_itself(site, client):
    person = _user("tag202@example.com")
    account = GameAccount.objects.create(user=person, battletag="原名#1234")
    client.force_login(person)
    url = reverse("me_game_account_edit", args=[account.pk])
    answer = _save(
        client,
        url,
        {
            "battletag": "半截#",
            "rank_tank": "40",
            "rank_damage": "",
            "rank_support": "",
        },
    )
    account.refresh_from_db()
    assert account.battletag == "原名#1234" and account.rank_tank == 40
    assert "battletag" in answer["errors"]
    page = client.get(reverse("me_game_accounts") + f"?edit={account.pk}")
    assert page.status_code == 200


@pytest.mark.django_db
def test_a_contact_checks_its_value_against_its_type(site, client):
    person = _user("contact202@example.com")
    contact = ContactMethod.objects.create(user=person, type="qq", value="12345678")
    client.force_login(person)
    url = reverse("me_contact_edit", args=[contact.pk])
    _save(client, url, {"type": "qq", "value": "87654321"})
    contact.refresh_from_db()
    assert contact.value == "87654321"


# --- the back office --------------------------------------------------------------


@pytest.mark.django_db
def test_site_settings_keep_the_key_and_the_good_fields(site, client):
    root = _root()
    client.force_login(root)
    row = SiteSettings.load()
    row.smtp_password = "stored-secret"
    row.save()
    url = reverse("backoffice:site_settings")
    html = client.get(url).content.decode()
    assert "data-autosave" in html and "data-autosave-button" in html
    from wagtail.test.utils.form_data import querydict_from_html

    data = querydict_from_html(html, form_index=0)
    data["site_description"] = "交大守望先锋社区，周五内战。"
    data["moderation_alert_email"] = "不是邮箱"
    data["smtp_password"] = ""
    answer = _save(client, url, data)
    row = SiteSettings.objects.get(pk=row.pk)
    assert row.site_description == "交大守望先锋社区，周五内战。"
    assert row.moderation_alert_email == ""  # the bad address is not saved
    assert row.smtp_password == "stored-secret"  # blank keeps the key
    assert "moderation_alert_email" in answer["errors"]
    # A second autosave moments later is the same stretch of editing.
    data["site_description"] = "改了第二次"
    _save(client, url, data)
    entries = ModelLogEntry.objects.for_instance(row).filter(action="wagtail.edit")
    assert entries.count() == 1


@pytest.mark.django_db
def test_user_edits_save_themselves_and_stopping_is_a_button(site, client):
    root = _root()
    member = _user("member202@example.com")
    client.force_login(root)
    url = reverse("backoffice:user_edit", args=[member.pk])
    page = client.get(url).content.decode()
    assert 'name="is_active"' not in page and "data-user-active" in page
    answer = _save(
        client, url, {"nickname": "x", "is_sjtu": "on", "roles": ["内容编辑"]}
    )
    member.refresh_from_db()
    assert member.nickname != "x"  # too short: kept
    assert member.groups.filter(name=GROUP_CONTENT).exists()  # the roles went
    assert "nickname" in answer["errors"] and "roles" in answer["saved"]

    stop = reverse("backoffice:user_active", args=[member.pk])
    client.post(stop, {"action": "stop", "deactivation_note": ""})
    member.refresh_from_db()
    assert member.is_active  # a reason is needed
    client.post(stop, {"action": "stop", "deactivation_note": "冒名"})
    member.refresh_from_db()
    assert not member.is_active and member.deactivation_note == "冒名"
    client.post(stop, {"action": "start"})
    member.refresh_from_db()
    assert member.is_active


@pytest.mark.django_db
def test_a_new_category_exists_from_the_first_change_and_hides_unnamed(site, client):
    from content.models import ArticleCategory

    client.force_login(_user("editor202@example.com", GROUP_CONTENT))
    url = reverse("backoffice:category_new")
    first = _save(client, url, {"name": "", "slug": "", "sort_order": "9"})
    second = _save(client, url, {"name": "", "slug": "", "sort_order": "8"})
    unnamed = ArticleCategory.objects.filter(name="")
    assert unnamed.count() == 2  # several may wait unnamed
    created = unnamed.get(sort_order=9)
    assert first["location"] == reverse("backoffice:category_edit", args=[created.pk])
    assert second["location"] != first["location"]
    assert created not in ArticleCategory.objects.named()
    writing = client.get(reverse("backoffice:article_new")).content.decode()
    assert "（未命名分类）" not in writing  # not offered to articles
    edit = reverse("backoffice:category_edit", args=[created.pk])
    _save(client, edit, {"name": "活动", "slug": "", "sort_order": "9"})
    assert not ArticleCategory.objects.named().filter(pk=created.pk).exists()
    _save(client, edit, {"name": "活动", "slug": "events", "sort_order": "9"})
    assert ArticleCategory.objects.named().filter(pk=created.pk).exists()
    clash = _save(client, edit, {"name": "活动二", "slug": "guide", "sort_order": "9"})
    created.refresh_from_db()
    assert created.slug == "events" and created.name == "活动二"  # name went, slug not
    assert "slug" in clash["errors"]
    news = client.get("/news/").content.decode()
    assert "活动二" in news


@pytest.mark.django_db
def test_a_new_member_group_and_its_rows(site, client):
    editor = _user("groups202@example.com", GROUP_CONTENT)
    joined = _user("joined202@example.com")
    client.force_login(editor)
    url = reverse("backoffice:member_group_new")
    management = {
        "members-TOTAL_FORMS": "1",
        "members-INITIAL_FORMS": "0",
        "members-MIN_NUM_FORMS": "0",
        "members-MAX_NUM_FORMS": "1000",
    }
    base = {
        "name": "",
        "description": "空名分组的简介",
        "is_visible": "on",
        "sort_order": "0",
    }
    answer = _save(
        client, url, {**base, **management, "members-0-user": "", "members-0-title": ""}
    )
    group = MemberGroup.objects.get(name="")
    assert answer["location"] == reverse(
        "backoffice:member_group_edit", args=[group.pk]
    )
    assert "空名分组的简介" not in client.get("/members/").content.decode()
    edit = answer["location"]
    # A row without a person is not saved and says so.
    answer = _save(client, edit, {**base, **management, "members-0-title": "社长"})
    assert "members-0-user" in answer["errors"] and not group.memberships.exists()
    answer = _save(
        client,
        edit,
        {
            **base,
            **management,
            "members-0-user": str(joined.pk),
            "members-0-title": "社长",
        },
    )
    assert group.memberships.get().user == joined
    assert "[data-memberships]" in answer["replace"]  # new ids on the page


@pytest.mark.django_db
def test_a_clashing_team_name_does_not_hold_back_the_rest(site, client):
    from teams import services as team_services

    root = _root()
    captain = _user("cap202@example.com")
    other = _user("other202@example.com")
    team = team_services.create_team(user=captain, name="原来的队")
    team_services.create_team(user=other, name="别人的队")
    client.force_login(root)
    url = reverse("teams:edit", args=[team.pk])
    answer = _save(client, url, {"name": "别人的队", "description": "新的简介"})
    team.refresh_from_db()
    assert team.name == "原来的队" and team.description == "新的简介"
    assert answer["errors"]


@pytest.mark.django_db
def test_pictures_and_collections_save_themselves(site, client, settings, tmp_path):
    from backoffice.tests.test_backoffice import _png

    settings.MEDIA_ROOT = tmp_path
    root = _root()
    client.force_login(root)
    collection = Collection.get_first_root_node().add_child(name="旧名字")
    image = get_image_model().objects.create(
        title="原标题", file=_png(), collection=collection
    )
    url = reverse("backoffice:image_edit", args=[image.pk])
    answer = _save(client, url, {"title": "", "collection": str(collection.pk)})
    image.refresh_from_db()
    assert image.title == "原标题" and "title" in answer["errors"]
    _save(client, url, {"title": "新标题", "collection": str(collection.pk)})
    image.refresh_from_db()
    assert image.title == "新标题"
    rename = reverse("backoffice:collection_rename", args=[collection.pk])
    assert "name" in _save(client, rename, {"name": " "})["errors"]
    _save(client, rename, {"name": "新名字"})
    collection.refresh_from_db()
    assert collection.name == "新名字"


@pytest.mark.django_db
def test_typography_saves_each_row_and_merges_the_regeneration(site, client):
    client.force_login(_root())
    url = reverse("core_typography")
    from wagtail.test.utils.form_data import querydict_from_html

    data = querydict_from_html(client.get(url).content.decode(), form_index=0)
    size = next(key for key in data if key.endswith("-size_rem"))
    data[size] = "1.125"
    with (
        mock.patch("core.prerender.request_all_soon") as soon,
        mock.patch("core.prerender.request_all") as every,
    ):
        answer = _save(client, url, data)
    assert answer["ok"] and answer["saved"]
    assert TypographyRule.objects.filter(size_rem="1.125").exists()
    assert every.call_count == 0  # merged, not one full run per autosave
    assert soon.call_count <= 1


# --- quieter side effects -------------------------------------------------------------


@pytest.mark.django_db
def test_the_patrol_reads_the_latest_text_not_each_half(site):
    from moderation.tests.test_moderation import configure_ai

    configure_ai()
    for text in ("周", "周五", "周五见"):
        moderation.submit(
            target_type=TargetType.MOTTO, target_id=7, field="motto", text=text
        )
    items = ModerationItem.objects.filter(target_type=TargetType.MOTTO, target_id=7)
    assert list(items.values_list("excerpt", flat=True)) == ["周五见"]
    items.update(checked_at=timezone.now())
    moderation.submit(
        target_type=TargetType.MOTTO, target_id=7, field="motto", text="改了"
    )
    assert items.count() == 2  # what was read stays on record


@pytest.mark.django_db
def test_one_log_entry_per_stretch_of_editing(site):
    editor = _user("log202@example.com")
    other = _user("log202b@example.com")
    group = MemberGroup.objects.create(name="日志组")
    autosave.log_edit(group, editor)
    autosave.log_edit(group, editor)
    entries = ModelLogEntry.objects.for_instance(group).filter(action="wagtail.edit")
    assert entries.count() == 1
    autosave.log_edit(group, other)
    assert entries.count() == 2
    entries.update(timestamp=timezone.now() - timedelta(minutes=31))
    autosave.log_edit(group, editor)
    assert entries.count() == 3


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name,args",
    [
        ("backoffice:site_settings", []),
        ("core_typography", []),
        ("backoffice:collections", []),
    ],
)
def test_the_back_office_forms_say_they_save_themselves(site, client, name, args):
    client.force_login(_root())
    html = client.get(reverse(name, args=args)).content.decode()
    assert "data-autosave" in html and "data-autosave-button" in html


@pytest.mark.django_db
def test_editors_with_a_role_but_no_group_permission_still_need_it(site, client):
    """The door (199) still decides; autosave adds no way in."""
    client.force_login(_user("plain202@example.com", GROUP_SUBMITTER))
    response = client.post(
        reverse("backoffice:member_group_new"), {"name": "偷建"}, **AUTOSAVE
    )
    assert response.status_code == 403
    assert not MemberGroup.objects.filter(name="偷建").exists()
    assert Group.objects.filter(name=GROUP_SUBMITTER).exists()
