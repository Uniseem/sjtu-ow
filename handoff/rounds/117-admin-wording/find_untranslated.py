"""Which admin strings have no Chinese (round 117). Run it after upgrading
Wagtail, and put what it prints into locale/zh_Hans/LC_MESSAGES/*.po.

Renders the admin pages as a temporary superuser (and the dashboard and a
few pages as each staff role) inside a transaction that is rolled back,
records every gettext lookup that came back untranslated, then lists the
gettext calls in Wagtail's JS bundles that /admin/jsi18n/ cannot answer.

Windows (AGENTS.md: no `shell <`):
  uv run python manage.py shell -c "exec(open(r'handoff/rounds/117-admin-wording/find_untranslated.py', encoding='utf-8').read())"
Linux:
  python manage.py shell < handoff/rounds/117-admin-wording/find_untranslated.py

False alarms it still prints: Django's own '%s KB' / '%s MB' (translated to
the same text), django-filter's internal 'exact', and our own Chinese labels
that contain ASCII (「SMTP 密码」).
"""

import json
import re
from collections import Counter
from pathlib import Path

from allauth.account.models import EmailAddress
from django.contrib.auth.models import Group
from django.db import transaction
from django.test import Client
from django.utils import timezone, translation
from django.utils.translation import trans_real
from wagtail.images.models import Image
from wagtail.models import Collection, Page, Revision, Task, Workflow

import wagtail
from accounts.models import User
from content.models import ArticlePage

ASCII_WORD = re.compile(r"[A-Za-z]{2,}")
missing = {}
current = {"url": ""}
real = {name: getattr(trans_real, name) for name in ("gettext", "pgettext", "ngettext", "npgettext")}


def record(context, msgid, plural, untranslated):
    if untranslated and ASCII_WORD.search(msgid or ""):
        missing.setdefault((context, msgid, plural), current["url"])


def _gettext(message):
    result = real["gettext"](message)
    record(None, message, None, result == message)
    return result


def _pgettext(context, message):
    result = real["pgettext"](context, message)
    record(context, message, None, result == message)
    return result


def _ngettext(singular, plural, number):
    result = real["ngettext"](singular, plural, number)
    record(None, singular, plural, result in (singular, plural))
    return result


def _npgettext(context, singular, plural, number):
    result = real["npgettext"](context, singular, plural, number)
    record(context, singular, plural, result in (singular, plural))
    return result


def admin_urls():
    article = ArticlePage.objects.first()
    image = Image.objects.first()
    collection = Collection.objects.exclude(depth=1).first()
    workflow = Workflow.objects.first()
    task = Task.objects.first()
    root = Page.objects.get(depth=1)
    urls = [
        "/admin/", "/admin/account/", f"/admin/pages/{root.pk}/", "/admin/pages/search/?q=a",
        "/admin/images/", "/admin/images/?layout=list", "/admin/images/multiple/add/",
        "/admin/documents/", "/admin/collections/", "/admin/collections/add/",
        "/admin/users/", "/admin/groups/", "/admin/groups/new/", "/admin/sites/", "/admin/redirects/",
        "/admin/workflows/list/", "/admin/workflows/tasks/index/",
        "/admin/reports/site-history/", "/admin/reports/locked/", "/admin/reports/workflow/",
        "/admin/reports/workflow_tasks/", "/admin/reports/aging-pages/", "/admin/reports/page-types-usage/",
        "/admin/moderation/", "/admin/avatars/", "/admin/registrations/", "/admin/tournaments/",
        "/admin/tournaments/new/", "/admin/scrims/", "/admin/scrims/new/", "/admin/teams/", "/admin/comments/",
        "/admin/feature_group_restrictions/", "/admin/feature_user_rules/", "/admin/feature_user_rules/new/",
        "/admin/snippets/content/articlecategory/", "/admin/snippets/content/articlecategory/add/",
        "/admin/snippets/members/membergroup/", "/admin/settings/core/sitesettings/1/",
        "/admin/settings/fonts/", "/admin/settings/typography/", "/admin/settings/prerender/",
    ]
    if article:
        urls += [f"/admin/pages/{article.pk}/edit/", f"/admin/pages/{article.pk}/history/",
                 f"/admin/pages/{article.pk}/delete/", f"/admin/pages/{article.pk}/privacy/",
                 f"/admin/pages/{article.pk}/move/", f"/admin/pages/{article.pk}/copy/",
                 f"/admin/pages/{article.get_parent().pk}/add_subpage/"]
        revisions = list(Revision.page_revisions.filter(object_id=str(article.pk)).values_list("pk", flat=True)[:2])
        if len(revisions) == 2:
            urls.append(f"/admin/pages/{article.pk}/revisions/compare/{revisions[0]}...{revisions[1]}/")
    if image:
        urls.append(f"/admin/images/{image.pk}/")
    if collection:
        urls.append(f"/admin/collections/{collection.pk}/")
    if workflow:
        urls.append(f"/admin/workflows/edit/{workflow.pk}/")
    if task:
        urls.append(f"/admin/workflows/tasks/edit/{task.pk}/")
    group = Group.objects.first()
    if group:
        urls.append(f"/admin/groups/edit/{group.pk}/")
    return urls


def visit(client, url, follow=False):
    current["url"] = url
    with translation.override("zh-hans"):
        return client.get(url, follow=follow)


def js_gaps(client):
    catalog_js = visit(client, "/admin/jsi18n/").content.decode()
    catalog = json.loads(re.search(r"const newcatalog = (\{.*?\});\n", catalog_js, re.S).group(1))
    call = re.compile(r'\(0,\s*\w+\.(\w+)\)\(\s*"((?:\\.|[^"\\])*)"')
    root = Path(wagtail.__file__).parent
    hits, calls = Counter(), []
    for path in root.rglob("*.js"):
        if "vendor" in path.parts or "tests" in path.parts:
            continue
        for fn, text in call.findall(path.read_text(encoding="utf-8", errors="replace")):
            calls.append((path.name, fn, text))
            if text in catalog:
                hits[(path.name, fn)] += 1
    gettext_functions = {key for key, count in hits.items() if count >= 2}
    return sorted({text for name, fn, text in calls if (name, fn) in gettext_functions and text not in catalog})


for name, fn in (("gettext", _gettext), ("pgettext", _pgettext), ("ngettext", _ngettext), ("npgettext", _npgettext)):
    setattr(trans_real, name, fn)
    setattr(translation._trans, name, fn)

with transaction.atomic():
    def staff(email, *groups, superuser=False):
        user = User.objects.create_user(email=email, password="x" * 16, nickname=email[:8],
                                        is_superuser=superuser, agreed_terms_at=timezone.now(),
                                        agreed_cross_border_at=timezone.now())
        for group in groups:
            user.groups.add(Group.objects.get(name=group))
        EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
        client = Client()
        client.force_login(user)
        return client

    root_client = staff("i18n-root@local.test", superuser=True)
    for url in admin_urls():
        visit(root_client, url)
    for number, role in enumerate(("内容编辑", "赛事管理员", "内战管理员", "认证作者", "投稿者")):
        role_client = staff(f"i18n-role{number}@local.test", role)
        for url in ("/admin/", "/admin/images/", "/admin/account/"):
            visit(role_client, url, follow=True)
    js_missing = js_gaps(root_client)
    transaction.set_rollback(True)

print(f"== 服务端缺 {len(missing)} 条（django.po）")
for (context, msgid, plural), url in missing.items():
    line = (f"[{context}] " if context else "") + json.dumps(msgid, ensure_ascii=False)
    if plural:
        line += "  复数：" + json.dumps(plural, ensure_ascii=False)
    print(" ", line, "  ←", url)
print(f"== 脚本缺 {len(js_missing)} 条（djangojs.po）")
for text in js_missing:
    print(" ", json.dumps(text, ensure_ascii=False))
