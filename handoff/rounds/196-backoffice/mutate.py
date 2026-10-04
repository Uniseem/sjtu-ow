"""Round 196: break each rule of the new back office once and check its test
goes red (AGENTS.md rule 7). Runs the tests first and stops if they are not
green (083). ``--check`` only looks that every mutation still applies.

bash scripts/remote-check.sh run uv run python handoff/rounds/196-backoffice/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

B = "backoffice/tests/test_backoffice.py::"
DOOR = B + "test_the_door"
FALLBACK = B + "test_wagtails_own_admin_is_for_superusers"
POLICY = B + "test_both_admins_get_the_admin_policy"
WRITE = B + "test_a_member_writes_saves_and_publishes"
OWN = B + "test_a_member_only_chooses_open_categories_and_sees_their_own"
PAGES = B + "test_site_pages_are_for_editors"
PINS = B + "test_pins_are_three_published_articles_at_most_once_each"
INTRO = B + "test_the_news_introduction_is_markdown"
INTRO_MIGRATION = (
    B + "test_the_migration_turns_the_introduction_and_its_drafts_into_markdown"
)
UPLOAD = B + "test_members_upload_into_the_submission_collection_only"
DIALOG = B + "test_the_dialog_offers_what_one_may_choose_and_takes_an_upload"
PICKER = B + "test_a_picture_field_refuses_a_picture_one_may_not_choose"
SAVE_CUP = B + "test_saving_a_tournament_does_what_the_admin_did"
SECONDS = B + "test_an_untouched_time_with_seconds_is_kept"
DELETE_CUP = B + "test_only_a_draft_never_published_is_deleted"
SCRIM = B + "test_a_scrim_is_saved_and_only_an_empty_draft_deleted"
ROLES = B + "test_roles_are_ticked_and_system_groups_left_alone"
SELF = B + "test_nobody_switches_their_own_account_off"
RULES = B + "test_rules_for_one_person_and_for_a_role"
PEOPLE = B + "test_people_pages_are_for_superusers"
SECRETS = B + "test_the_secrets_are_never_shown_and_blank_keeps_them"
LOG = B + "test_the_log_shows_page_and_model_entries_with_their_names"
WAYS = B + "test_the_ways_in_lead_to_the_back_office"
W = "core/tests/test_admin_wording.py::"
ROLE_TABS = W + "test_each_role_sees_only_its_sections_and_tabs"
TABS = W + "test_each_section_has_its_tabs_in_order"
COUNT = W + "test_review_tabs_count_what_waits"
PLACED = W + "test_every_back_office_address_goes_through_the_door"
E = "content/tests/test_submitter_editor.py::"
PROMOTE = E + "test_only_editors_and_authors_get_the_promote_fields"
ADDRESS = E + "test_the_address_comes_from_the_title_and_survives_the_writer"
RESERVED = E + "test_reserved_and_taken_addresses_step_aside"
TAKEN = E + "test_an_editor_s_taken_address_is_refused_on_the_field"
FIELDS = "content/tests/test_submissions.py::test_submitter_category_and_author_fields"
C = "content/tests/test_category_delete.py::"
USED = C + "test_a_used_category_says_why_and_stays"
OFFER = C + "test_only_empty_categories_offer_delete"
S = "core/tests/test_admin_safety.py::"
STOP = S + "test_stopping_an_account_needs_a_reason_and_cancels_its_applications"
TEAM_EDIT = S + "test_an_admin_edit_of_a_team_regenerates_its_pages"
COMMENTS = S + "test_comments_are_hidden_or_pinned_not_added_or_deleted"
COMMENT_LIST = (
    "comments/tests/test_comments.py::"
    "test_content_editors_open_the_admin_list_and_others_do_not"
)
LOCK = "tournaments/tests/test_state_table.py::test_auto_approve_is_locked_once_anyone_has_registered"
MOVED = "tournaments/tests/test_time_changed.py::test_saving_in_the_admin_sends_it"
GROUPS = "members/tests/test_members.py::test_an_admin_creates_a_group_with_members"
LINK = "core/tests/test_admin_link.py::test_the_site_owner_is_shown_the_way_in"
REVISE = "moderation/tests/test_ask_author.py::test_each_kind_of_content_has_somewhere_to_fix_it"
ROUTES = "content/tests/test_content.py::test_every_fixed_top_level_route_is_reserved"
EDITOR_CSS = "content/tests/test_markdown.py::test_what_the_renderer_emits_has_its_styles"

V = "backoffice/views/"
F = "backoffice/forms.py"

MUTATIONS = [
    # the door and the fallback admin
    ("signed-out visitors are not sent to sign in", "backoffice/nav.py",
     "            if not request.user.is_authenticated:\n                return redirect_to_login(request.get_full_path())\n",
     "", [DOOR]),
    ("anyone signed in gets in", "backoffice/nav.py",
     "            if not access.can_enter(request.user):\n                raise PermissionDenied(\"没有进入后台的权限。\")\n",
     "", [DOOR]),
    ("a view without placed", "backoffice/urls.py",
     '    path("log/", settings.action_log, name="log"),',
     '    path("log/", settings.action_log.__wrapped__, name="log"),', [PLACED]),
    ("wagtail's admin open to every member", "core/middleware.py",
     "            if user is not None and user.is_authenticated and not user.is_superuser:",
     "            if False:", [FALLBACK]),
    ("wagtail's admin without the admin policy", "core/middleware.py",
     "        if request.path.startswith((prefix, wagtail)):",
     "        if request.path.startswith(prefix):", [POLICY]),
    # navigation
    ("every section shown", "backoffice/nav.py",
     "            first = next((t for t in section.tabs if self._tab_allowed(t)), None)",
     "            first = section.tabs[0]", [ROLE_TABS]),
    ("a strip for one page", "backoffice/nav.py",
     "        return links if len(links) > 1 else []", "        return links", [TABS]),
    ("no count on 报名", "backoffice/nav.py",
     "                count=_pending_registrations,\n", "", [COUNT]),
    # articles
    ("members see every article", V + "articles.py",
     "    if mine:\n        articles = articles.filter(owner=user)",
     "    if False:\n        articles = articles.filter(owner=user)", [OWN]),
    ("anyone edits any article", V + "articles.py",
     "    if not perms.can_edit():\n        raise PermissionDenied(\"你不能编辑这篇文章。\")\n",
     "", [OWN]),
    ("publishing on the edit page saves only", V + "articles.py",
     '        publishing = "publish" in request.POST', "        publishing = False",
     [WRITE]),
    ("the preview shows the live page", V + "articles.py",
     "    draft = page.get_latest_revision_as_object()\n    return draft.serve_preview",
     "    draft = page\n    return draft.serve_preview", [WRITE]),
    ("members choose any category", F,
     "            self.fields[\"category\"].queryset = ArticleCategory.objects.filter(\n                allow_submission=True\n            )",
     "            pass", [FIELDS, OWN]),
    ("members get the address and schedule", F,
     "        if plain_writer(user):\n            for name in EDITOR_ONLY_FIELDS:",
     "        if False:\n            for name in EDITOR_ONLY_FIELDS:", [PROMOTE]),
    ("members set the author", F,
     "        if not user_can_edit_author(user):\n            self.fields.pop(\"author\")",
     "        if False:\n            self.fields.pop(\"author\")", [FIELDS]),
    ("a reserved word becomes the address", F,
     "        if base.lower() in RESERVED_CHILD_SLUGS:\n            base = f\"{base}-article\"\n        candidate",
     "        candidate", [RESERVED]),
    ("a taken address goes through", F,
     "            raise ValidationError(\"这个网址片段已经有文章在用了，换一个。\")",
     "            pass", [TAKEN]),
    ("the writer's save resets the address", F,
     "        keep = \"slug\" not in self.fields and self._original_slug",
     "        keep = False", [ADDRESS]),
    # site pages and categories
    ("site pages for everyone inside", V + "pages.py",
     "    if not access.edits_site_pages(request.user):",
     "    if False:", [PAGES]),
    ("the same article pinned twice", F,
     "        if len(picked) != len(set(picked)):", "        if False:", [PINS]),
    ("drafts can be pinned", F,
     "        live = ArticlePage.objects.live().order_by(\"-first_published_at\")",
     "        live = ArticlePage.objects.order_by(\"-first_published_at\")", [PINS]),
    ("pins saved as a draft only", V + "pages.py",
     "        _save_and_publish(request, draft, home.latest_revision)\n        messages.success(request, \"首页的置顶文章已更新。\")",
     "        draft.save_revision(user=request.user)\n        messages.success(request, \"首页的置顶文章已更新。\")",
     [PINS]),
    ("the introduction printed as written", "content/templates/content/article_index_page.html",
     "{{ page.intro|markdown }}", "{{ page.intro }}", [INTRO]),
    ("the migration leaves the HTML", "content/migrations/0009_markdown_intro.py",
     "        page.intro = from_html(page.intro or \"\")\n", "", [INTRO_MIGRATION]),
    ("the migration leaves the drafts", "content/migrations/0009_markdown_intro.py",
     "            content[\"intro\"] = from_html(content[\"intro\"])\n", "",
     [INTRO_MIGRATION]),
    ("a used category deleted", V + "categories.py",
     "    count = category.articles.count()\n    if count:",
     "    count = category.articles.count()\n    if False:", [USED]),
    ("delete offered on a used category", "backoffice/templates/backoffice/content/categories.html",
     "{% if can_delete and not item.article_count %}", "{% if can_delete %}", [OFFER]),
    # pictures
    ("the dialog shows every picture", V + "images.py",
     "    return image_policy().instances_user_has_any_permission_for(user, list(actions))",
     "    return Image.objects.all()", [DIALOG]),
    ("the dialog uploads anywhere", V + "images.py",
     "    collection = (\n        collections_for(request.user, \"add\")",
     "    collection = (\n        Collection.objects", [DIALOG]),
    ("a picture field takes any picture", "backoffice/widgets.py",
     "        queryset = image_policy().instances_user_has_any_permission_for(\n            user, [\"choose\"]\n        )",
     "        queryset = Image.objects.all()", [PICKER]),
    ("collections for everyone", V + "images.py",
     "    if not request.user.is_superuser:\n        raise PermissionDenied(\"集合只有超级管理员能改。\")",
     "    pass", [UPLOAD]),
    # tournaments and scrims
    ("auto approval unlocked", F,
     "            self.add_error(\"auto_approve\", \"已经有报名了，不能再改「报名自动通过」。\")",
     "            pass", [LOCK]),
    ("the creator not filled in", V + "events.py",
     "    if tournament.created_by_id is None:\n        tournament.created_by = request.user",
     "    if False:\n        tournament.created_by = request.user", [SAVE_CUP]),
    ("the start before the save forgotten", V + "events.py",
     "    old_starts_at = form.initial.get(\"starts_at\")\n    tournament = form.save(commit=False)",
     "    old_starts_at = None\n    tournament = form.save(commit=False)", [SAVE_CUP, MOVED]),
    ("no after_change", V + "events.py",
     "    tournament_services.after_change(tournament, actor=request.user)\n", "", [SAVE_CUP]),
    ("a published tournament deleted", V + "events.py",
     "    if not tournament_services.can_delete(tournament):\n        messages.error(request, \"发布过的赛事不能删除，只能取消。\")",
     "    if False:\n        messages.error(request, \"发布过的赛事不能删除，只能取消。\")",
     [DELETE_CUP]),
    ("seconds cut off", F,
     "            if stored and sent and sent == stored.replace(second=0, microsecond=0):",
     "            if False:", [SECONDS]),
    ("a scrim without its creator", V + "events.py",
     "    if scrim.created_by_id is None:\n        scrim.created_by = request.user",
     "    if False:\n        scrim.created_by = request.user", [SCRIM]),
    ("a scrim with signups deleted", V + "events.py",
     "    if not scrim_services.can_delete(scrim):",
     "    if False:", [SCRIM]),
    # people
    ("system groups ticked here too", F,
     "        Group.objects.exclude(name__in=SYSTEM_GROUPS).values_list(\"name\", flat=True)",
     "        Group.objects.values_list(\"name\", flat=True)", [ROLES]),
    ("one's own account switched off", F,
     "        if editor is not None and editor.pk == self.instance.pk:",
     "        if False:", [SELF]),
    ("stopped without a reason", F,
     "            self.add_error(\"deactivation_note\", \"停用账号要写原因。\")",
     "            pass", [STOP]),
    ("applications left after stopping", V + "members.py",
     "            _after_deactivation(request, person)", "            pass", [STOP]),
    ("a second rule for the same feature", F,
     "            raise ValidationError(\"这项功能已经有单独规则了，先删掉旧的再加。\")",
     "            pass", [RULES]),
    ("rules without who set them", V + "members.py",
     "        rule.updated_by = request.user\n", "", [RULES]),
    ("people pages for editors", V + "members.py",
     "    if not request.user.is_superuser:\n        raise PermissionDenied(\"这一页只有超级管理员能用。\")",
     "    pass", [PEOPLE]),
    ("a team edit regenerates nothing", V + "members.py",
     "        team_services.on_team_changed(team, author=request.user)\n", "",
     [TEAM_EDIT]),
    ("group members saved out of order", V + "members.py",
     "        formset.save_in_order(group)", "        formset.save(commit=False)",
     [GROUPS]),
    # comments, settings, the log
    ("any action on a comment", V + "comments.py",
     "    if action not in ACTIONS:\n        raise PermissionDenied(\"没有这个操作。\")\n",
     "", [COMMENTS]),
    ("the comment list for everyone inside", V + "comments.py",
     "def comment_list(request):\n    _moderator(request)",
     "def comment_list(request):\n    pass", [COMMENT_LIST]),
    ("a blank secret clears it", F,
     "    def clean_smtp_password(self):\n        return self._kept(\"smtp_password\")",
     "    def clean_smtp_password(self):\n        return self.cleaned_data.get(\"smtp_password\")",
     [SECRETS]),
    ("the log without page entries", V + "settings.py",
     "    union = pages.union(models, all=True)", "    union = models", [LOG]),
    ("the log's action filter ignored", V + "settings.py",
     "            filters[\"action\"] = form.cleaned_data[\"action\"]", "            pass",
     [LOG]),
    # the ways in
    ("the account menu still points at Wagtail", "templates/components/account_area.html",
     "{% url 'backoffice:home' %}", "{% url 'wagtailadmin_home' %}", [LINK]),
    ("a fix-it letter points at Wagtail", "moderation/notifications.py",
     "        return admin + reverse(\"backoffice:article_edit\", args=[item.target_id])",
     "        return admin + reverse(\"wagtailadmin_pages:edit\", args=[item.target_id])",
     [REVISE]),
    ("我要投稿 opens Wagtail's editor", "content/services.py",
     "    return reverse(\"backoffice:article_new\")",
     "    return reverse(\"wagtailadmin_pages:add\", args=[\"content\", \"articlepage\", 1])",
     [WAYS]),
    ("robots let /wagtail/ in", "content/views.py",
     "            \"Disallow: /wagtail/\",\n", "", [WAYS]),
    ("a page may take the slug wagtail", "content/models.py",
     "        \"wagtail\",\n", "", [ROUTES]),
    ("the editor without its styles", "content/widgets.py",
     "\"vendor/easymde/easymde.min.css\", \"css/markdown-editor.css\"",
     "\"vendor/easymde/easymde.min.css\"", [EDITOR_CSS]),
]


def run(tests):
    return subprocess.run(
        [PY, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *tests],
        cwd=ROOT,
        env=ENV,
        capture_output=True,
        text=True,
    ).returncode


def _text(rel):
    return (ROOT / rel).read_bytes().decode("utf-8").replace("\r\n", "\n")


def check():
    bad = [
        (label, _text(rel).count(old))
        for label, rel, old, _new, _tests in MUTATIONS
        if _text(rel).count(old) != 1
    ]
    print("mutations:", len(MUTATIONS), "not applying:", bad or "none")
    return not bad


def main():
    if not check():
        sys.exit(1)
    if "--check" in sys.argv:
        return
    every = sorted({t for *_rest, tests in MUTATIONS for t in tests})
    assert run(every) == 0, "baseline is red"
    print("baseline green,", len(every), "tests")
    failed = []
    for label, rel, old, new, tests in MUTATIONS:
        path = ROOT / rel
        backup = path.with_suffix(path.suffix + ".mutbak")
        shutil.copy2(path, backup)
        try:
            raw = path.read_bytes().decode("utf-8")
            crlf = "\r\n" in raw
            text = raw.replace("\r\n", "\n").replace(old, new)
            path.write_bytes(
                (text.replace("\n", "\r\n") if crlf else text).encode("utf-8")
            )
            for test in tests:
                red = run([test]) != 0
                print(("caught " if red else "MISSED ") + label + " -> " + test.split("::")[1])
                if not red:
                    failed.append((label, test))
        finally:
            shutil.copy2(backup, path)
            backup.unlink()
            folder = rel.rsplit("/", 1)[0]
            for cache in ROOT.glob(folder + "/**/__pycache__/*.pyc"):
                cache.unlink()
    assert run(every) == 0, "not green after restoring"
    print("restored and green;", "missed:", failed or "none")


if __name__ == "__main__":
    main()
