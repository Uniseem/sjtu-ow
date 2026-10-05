"""A newcomer's first evening, in a real browser, on the test machine (round 168).

    bash scripts/remote-check.sh run uv run python scripts/journey.py

The tests drive Django directly; this drives Chromium, so it also catches
what only a browser shows: a script the CSP blocks, a form whose button does
nothing, a slot that never fills. On a throwaway site (screens.py's seed: a
captain with a team, a scrim) it registers through the sign-up form with test
values, reads the code from the worker's console mail, verifies, adds a game
ID and a contact, signs up for the scrim, applies to the team and looks for
the scrim under 「我的安排」 on the homepage. Every console error, uncaught
exception and CSP report on the way is printed and counts as a failure.
Exits 1 if any step fails. Needs ``chromium`` (installed on the test machine).

    bash scripts/remote-check.sh run uv run python scripts/journey.py pages

opens every page the project's own apps define, as a visitor, a member and
a superuser (admin pages as the superuser only), and reports each one where
the browser saw an error or the page answered 500. Covers the admin's
script-heavy pages (drag-and-drop teams) that no test can run.

    bash scripts/remote-check.sh run uv run python scripts/journey.py admin

is the officers' evening: ten more players sign up, the scrim admin ticks
ten on the split page, generates the teams, moves a card out and back with
the card buttons and saves; the tournament admin moves three people from the
pool into a new team with the card buttons, names it and saves.
"""

from __future__ import annotations

import email
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import screens  # noqa: E402

screens.WORK = Path("/tmp/sjtu-ow-journey")
WORK = screens.WORK
LOG = WORK / "worker.log"
EVENTS: list[tuple[str, str]] = []
# Test values for this throwaway site only.
EMAIL, NICKNAME, PASSWORD = "newbie@journey.test", "新来的", "Journey-Test-Pass-2026"


class Watching(screens.DevTools):
    """Keeps the browser's own messages: exceptions, error logs, CSP, and the
    status of each page loaded. A 404 or 405 page reports its own address as
    a failed load; that is the page answering, not an error on it."""

    page_url = ""
    statuses: dict[str, int] = {}

    def _receive(self):
        message = super()._receive()
        method, params = message.get("method", ""), message.get("params", {})
        if method == "Runtime.exceptionThrown":
            EVENTS.append(("exception", params["exceptionDetails"].get("text", "")))
        elif method == "Log.entryAdded" and params["entry"].get("level") == "error":
            entry = params["entry"]
            if not (
                entry.get("source") == "network" and entry.get("url") == self.page_url
            ):
                EVENTS.append(
                    ("error", f"{entry.get('text', '')} {entry.get('url', '')}")
                )
        elif method == "Runtime.consoleAPICalled" and params.get("type") == "error":
            words = [
                str(arg.get("value", arg.get("description", arg.get("type", ""))))
                for arg in params.get("args", [])
            ]
            EVENTS.append(("console", " ".join(words)))
        elif method == "Network.responseReceived" and params.get("type") == "Document":
            self.statuses[params["response"]["url"]] = params["response"]["status"]
        return message


def verification_code(console: str) -> str | None:
    """The code in the newest letter to EMAIL that the console mail backend
    printed. Its plain-text part says 验证码：XXXXXX (templates/account/email),
    transfer-encoded, so each letter is parsed and decoded first."""
    for chunk in reversed(console.split("-" * 79)):
        start = chunk.find("Content-Type:")
        if start < 0 or f"To: {EMAIL}" not in chunk:
            continue
        letter = email.message_from_string(chunk[start:])
        for part in letter.walk():
            if part.get_content_type() == "text/plain":
                body = part.get_payload(decode=True).decode("utf-8", "replace")
                found = re.search(r"验证码：([A-Z0-9]{6})", body)
                if found:
                    return found.group(1)
    return None


def journey(tools, base, data) -> list[str]:
    failed = []

    def js(expression):
        reply = tools.send(
            "Runtime.evaluate", {"expression": expression, "returnByValue": True}
        )
        return reply.get("result", {}).get("value")

    def go(path):
        tools.send("Page.navigate", {"url": path if "://" in path else base + path})
        time.sleep(2)

    def fill_and_submit(script):
        """Run ``script`` (it marks its form with data-journey), then submit."""
        js(script)
        js("document.querySelector('form[data-journey]').requestSubmit()")
        time.sleep(2.5)

    def step(name, ok, detail=""):
        print(f"{'ok ' if ok else 'BAD'} {name} {detail}".rstrip())
        if not ok:
            failed.append(name)

    def page_says(text):
        return bool(js(f"document.body.innerText.includes({text!r})"))

    go("/accounts/signup/")
    fill_and_submit(f"""(() => {{
        const f = document.querySelector('form[action*="signup"]');
        f.querySelector('[name=email]').value = {EMAIL!r};
        f.querySelector('[name=nickname]').value = {NICKNAME!r};
        f.querySelector('[name=password1]').value = {PASSWORD!r};
        f.querySelector('[name=password2]').value = {PASSWORD!r};
        f.querySelector('[name=is_sjtu][value=true]').checked = true;
        f.querySelectorAll('input[type=checkbox]').forEach(box => box.checked = true);
        f.setAttribute('data-journey', '1');
    }})()""")
    step("注册表单提交", js("location.pathname") == "/accounts/confirm-email/")

    code = None
    for _ in range(40):
        text = LOG.read_text(encoding="utf-8", errors="replace") if LOG.exists() else ""
        code = verification_code(text)
        if code:
            break
        time.sleep(0.5)
    step("验证码邮件发出", code is not None)
    if code:
        fill_and_submit(f"""(() => {{
            const field = document.querySelector('input[name=code]');
            field.value = {code!r};
            field.form.setAttribute('data-journey', '1');
        }})()""")
    step("验证后到了个人中心", js("location.pathname") == "/me/")

    go("/me/game-accounts/?new=1")
    fill_and_submit("""(() => {
        const f = [...document.querySelectorAll('main form')]
            .find(form => form.querySelector('[name=battletag]'));
        f.querySelector('[name=battletag]').value = 'Newbie#1234';
        f.querySelectorAll('select')
            .forEach(s => { s.selectedIndex = s.options.length - 5; });
        f.setAttribute('data-journey', '1');
    })()""")
    step("加了游戏 ID", page_says("Newbie#1234"))

    go("/me/contacts/?new=1")
    fill_and_submit("""(() => {
        const f = [...document.querySelectorAll('main form')]
            .find(form => form.querySelector('[name=value]'));
        const kind = f.querySelector('[name=type]');
        kind.value = kind.options[1].value;
        f.querySelector('[name=value]').value = '123456789';
        f.setAttribute('data-journey', '1');
    })()""")
    step("加了联系方式", page_says("123456789"))

    # Round 202 (design 13.17): what is edited saves itself; the avatar goes
    # the moment a picture is chosen (「上传后自动就保存替换」).
    go("/me/")
    js("""(() => {
        const motto = document.querySelector('form[data-autosave] [name=motto]');
        motto.value = '浏览器里自动保存的宣言';
        motto.dispatchEvent(new Event('input', {bubbles: true}));
    })()""")
    time.sleep(3)
    status = js("(document.querySelector('[data-autosave-status]') || {}).textContent")
    step("资料改了就自动保存", "已保存" in (status or ""), status or "")
    go("/me/")
    kept = js("document.querySelector('[name=motto]').value")
    step("刷新以后还在", kept == "浏览器里自动保存的宣言", kept or "")

    from PIL import Image

    picture = WORK / "face.png"
    Image.new("RGB", (300, 300), (200, 80, 60)).save(picture)
    js("window.__beforeUpload = true")
    root = tools.send("DOM.getDocument", {})["root"]["nodeId"]
    node = tools.send(
        "DOM.querySelector",
        {"nodeId": root, "selector": "form[data-autosubmit-file] input[type=file]"},
    )["nodeId"]
    tools.send("DOM.setFileInputFiles", {"nodeId": node, "files": [str(picture)]})
    time.sleep(1.5)
    if js("window.__beforeUpload === true"):
        # Chromium did not announce the choice itself: do what a person's
        # choice does.
        js(
            "document.querySelector('form[data-autosubmit-file] input[type=file]')"
            ".dispatchEvent(new Event('change', {bubbles: true}))"
        )
    time.sleep(4)
    step("头像选好就换上，不用再点", page_says("头像已换上"))

    go(f"/scrims/{data['scrim']}/")
    fill_and_submit("""(() => {
        const f = [...document.querySelectorAll('form')]
            .find(form => form.action.includes('/signup/'));
        const pick = f.querySelector('[name=game_account]');
        if (pick.tagName === 'SELECT') pick.selectedIndex = pick.options.length - 1;
        else pick.checked = true;
        f.querySelectorAll('[name=roles]').forEach(box => box.checked = true);
        f.setAttribute('data-journey', '1');
    })()""")
    step("报了内战", page_says("报名成功"))

    go(f"/teams/{data['team']}/apply/")
    fill_and_submit("""(() => {
        const f = [...document.querySelectorAll('main form')].pop();
        f.querySelectorAll('input[type=checkbox]').forEach(box => box.checked = true);
        f.setAttribute('data-journey', '1');
    })()""")
    applied = page_says("申请已提交")
    detail = (
        ""
        if applied
        else js(
            "[...document.forms].map(f => f.getAttribute('action') + ' ['"
            " + [...f.elements].map(e => e.name + '=' + e.value).join('&') + ']')"
            ".join(' | ') + ' || ' + [...document.querySelectorAll("
            "'.errorlist, [role=alert], .c-field__error, .text-danger')]"
            ".map(e => e.innerText).join(' / ')"
        )
    )
    step("申请了战队", applied, detail)
    # Round 204 (design 10.5): the letter to the captain waits for 「发信」.
    asked = js(
        "location.pathname.startsWith('/letters/') + '|' +"
        " document.querySelectorAll('[data-held-letter]').length"
    )
    step("申请后问要不要给队长发信", asked == "true|1", asked or "")
    fill_and_submit("""(() => {
        document.querySelector('[data-held-letters]').setAttribute('data-journey', '1');
    })()""")
    step(
        "点了发信，回到战队页",
        page_says("信已经排队发出，共 1 人")
        and js("location.pathname") == f"/teams/{data['team']}/",
        js("location.pathname") or "",
    )

    go("/")
    agenda = js("(document.querySelector('[data-my-agenda]') || {}).innerText || ''")
    step("首页「我的安排」里有这场内战", "截图内战" in (agenda or ""))

    tools.send("Runtime.evaluate", {"expression": "1"})  # collect what is pending
    for kind, text in EVENTS:
        print(f"    浏览器报告 {kind}: {text[:200]}")
    step("浏览器没有报错", not EVENTS, f"（{len(EVENTS)} 条）" if EVENTS else "")
    return failed


PROJECT = (
    "accounts.",
    "backoffice.",
    "comments.",
    "content.",
    "core.",
    "members.",
    "moderation.",
    "scrims.",
    "search.",
    "teams.",
    "tournaments.",
)
EXTRA = ["/", "/news/", "/admin/", "/wagtail/", "/wagtail/pages/", "/accounts/login/"]


def list_routes() -> list[str]:
    """Inside Django (``journey.py routes``): the project's own addresses."""
    import django

    django.setup()
    from django.urls import URLPattern, URLResolver, get_resolver

    found = []

    def walk(patterns, prefix):
        for pattern in patterns:
            if isinstance(pattern, URLResolver):
                walk(pattern.url_patterns, prefix + str(pattern.pattern))
            elif isinstance(pattern, URLPattern):
                module = getattr(pattern.callback, "__module__", "")
                if module.startswith(PROJECT) and "(?P" not in prefix + str(
                    pattern.pattern
                ):
                    found.append(prefix + str(pattern.pattern))

    walk(get_resolver().url_patterns, "")
    return found


def fill(route: str, data: dict) -> str:
    route = route.lstrip("^").rstrip("$")
    bare = route.removeprefix("admin/")
    ids = {
        "teams": data["team"],
        "tournaments": data["cup"],
        "scrims": data["scrim"],
        "members": data["member"],
        # The back office's own (v7.0): real rows, so the pages open.
        "articles": data["article"],
        "pages": data["about"],
        "categories": data["category"],
        "member-groups": data["group"],
        "users": data["member"],
    }
    for prefix, value in ids.items():
        if bare.startswith(prefix + "/"):
            route = re.sub(r"<id:\w+>", str(value), route, count=1)
    return "/" + re.sub(r"<[^>]+>", "1", route)


def sweep(tools, base, data, routes) -> list[str]:
    """Every page, in the browser, as the people who would open it."""
    urls = sorted({fill(route, data) for route in routes} | set(EXTRA))
    urls = [
        url
        for url in urls
        if not url.endswith((".ics", ".csv", ".xml", ".txt"))
        and not url.startswith("/_fragments/")  # pieces of pages, not pages
    ]
    sessions = {"访客": None, "成员": data["sessions"]["member"]}
    sessions["站长"] = data["sessions"]["officer"]
    bad = []
    for who, session in sessions.items():
        tools.send("Network.clearBrowserCookies")
        if session:
            tools.send(
                "Network.setCookie",
                {
                    "name": "sessionid",
                    "value": session,
                    "domain": "127.0.0.1",
                    "path": "/",
                },
            )
        for url in urls:
            if url.startswith(("/admin/", "/wagtail/")) and who != "站长":
                continue
            EVENTS.clear()
            tools.page_url = base + url
            tools.send("Page.navigate", {"url": base + url})
            time.sleep(1.5)
            tools.send("Runtime.evaluate", {"expression": "1"})
            status = tools.statuses.get(base + url, 0)
            if 400 <= status < 500:
                # A page that answers 403/404/405 (forms that only take a
                # POST, say) shows the browser's own error page and logs it
                # as a failed load. Scripts and CSP still count.
                EVENTS[:] = [
                    event
                    for event in EVENTS
                    if not event[1].startswith("Failed to load resource")
                ]
            if EVENTS or status >= 500:
                bad.append(url)
                print(f"BAD {who} {status} {url}")
                for kind, text in EVENTS:
                    print(f"    浏览器报告 {kind}: {text[:200]}")
    print(f"看了 {len(urls)} 个地址，{len(bad)} 处有问题")
    return bad


def add_players(scrim_id: int, cup_id: int) -> None:
    """Inside Django (``journey.py players``): ten more people signed up for
    the scrim and in the tournament's pool, every one able to play anything."""
    import django

    django.setup()
    from allauth.account.models import EmailAddress
    from django.utils import timezone

    from accounts.models import ContactMethod, ContactType, GameAccount, User
    from scrims import services as scrim_services
    from scrims.models import Role, Scrim
    from tournaments import registration as reg
    from tournaments.models import Tournament

    now = timezone.now()
    scrim, cup = Scrim.objects.get(pk=scrim_id), Tournament.objects.get(pk=cup_id)
    for number in range(10):
        email = f"player{number}@journey.test"
        user = User.objects.create_user(
            email=email,
            password=None,
            nickname=f"队员{number}",
            is_sjtu=True,
            agreed_terms_at=now,
            agreed_cross_border_at=now,
        )
        EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
        account = GameAccount.objects.create(
            user=user,
            battletag=f"Player{number}#{4000 + number}",
            rank_tank=14 + number,
            rank_damage=15 + number,
            rank_support=16 + number,
        )
        ContactMethod.objects.create(user=user, type=ContactType.QQ, value="10000")
        scrim_services.sign_up(
            scrim=scrim,
            user=user,
            game_account_id=account.pk,
            roles=[Role.TANK, Role.DAMAGE, Role.SUPPORT],
        )
        reg.sign_up_individual(
            tournament=cup,
            user=user,
            game_account_id=account.pk,
            roles=["tank", "damage", "support"],
        )


def officers(tools, base, data) -> list[str]:
    failed = []

    def js(expression):
        reply = tools.send(
            "Runtime.evaluate", {"expression": expression, "returnByValue": True}
        )
        return reply.get("result", {}).get("value")

    def step(name, ok, detail=""):
        print(f"{'ok ' if ok else 'BAD'} {name} {detail}".rstrip())
        if not ok:
            failed.append(name)

    def go(path):
        tools.send("Page.navigate", {"url": base + path})
        time.sleep(2)

    def press(selector):
        """Click this button the way a person does, and wait for the page it
        leads to (generating teams takes a few seconds on the dev server)."""
        found = js(
            f"(() => {{ const b = document.querySelector({selector!r});"
            " if (!b) return 'no button';"
            " if (b.disabled) return 'disabled';"
            " window.__journeyOld = true; b.click(); return 'clicked'; })()"
        )
        if found != "clicked":
            print(f"    按钮 {selector}：{found}")
            return
        for _ in range(60):
            time.sleep(0.5)
            if js("!window.__journeyOld && document.readyState === 'complete'"):
                break
        time.sleep(0.5)

    def says(text):
        return bool(js(f"document.body.innerText.includes({text!r})"))

    tools.send("Network.clearBrowserCookies")
    tools.send(
        "Network.setCookie",
        {
            "name": "sessionid",
            "value": data["sessions"]["officer"],
            "domain": "127.0.0.1",
            "path": "/",
        },
    )

    go(f"/admin/scrims/{data['scrim']}/split/")
    enabled = js("""(() => {
        const boxes = [...document.querySelectorAll('[data-pick]')];
        boxes.forEach((box, index) => {
            box.checked = index < 10;
            box.dispatchEvent(new Event('change', {bubbles: true}));
        });
        return !document.querySelector('[data-generate]').disabled;
    })()""")
    step("勾满 10 人后「生成分队」能点了", bool(enabled))
    press("[data-generate]")
    counts = js("""(() => {
        const count = team => document
            .querySelectorAll(`[data-zone-team=${team}] [data-card]`).length;
        return count('a') + '/' + count('b');
    })()""")
    step("生成了两队各 5 人", counts == "5/5", counts or "")
    moved = js("""(() => {
        const card = document.querySelector('[data-zone-team=a] [data-card]');
        card.querySelector('[data-move=""]').click();
        const out = document.querySelectorAll('[data-zone-team=a] [data-card]').length;
        card.querySelector('[data-move=a]').click();
        const back = document.querySelectorAll('[data-zone-team=a] [data-card]').length;
        return out + '/' + back;
    })()""")
    step("卡片按钮移到缓冲区再移回", moved == "4/5", moved or "")
    press("button[name=action][value=save]")
    step("保存分队", says("已保存分队"))

    go(f"/admin/tournaments/{data['cup']}/teams/")
    placed = js("""(() => {
        const cards = [...document.querySelectorAll('[data-card]')]
            .filter(card => !card.closest('[data-team-panel]'))
            .filter(card => card.querySelector('[data-move="new"]'))
            .slice(0, 3);
        cards.forEach(card => card.querySelector('[data-move="new"]').click());
        document.querySelector('input[name="name-new"]').value = '浏览器编的队';
        return cards.length;
    })()""")
    step("三个散人移进新队伍", placed == 3, str(placed))
    press("button[name=action][value=save]")
    step("保存编队", says("已保存：新建 1 支"))
    # Round 204 (design 10.5): asked before the three hear they are placed.
    asked = js(
        "location.pathname.startsWith('/admin/letters/') + '|' +"
        " document.querySelectorAll('[data-held-letter]').length + '|' +"
        " (document.querySelector('[data-held-letter]') || {}).innerText"
    )
    step(
        "编完问要不要给编进的人发信",
        bool(asked) and asked.startswith("true|1|") and "3 人" in asked,
        " ".join((asked or "").split())[:120],
    )
    press("button[name=skip]")
    step("选了都不发，回到编队页", says("这次没有发信"))
    step("新队伍出现在页面上", says("浏览器编的队"))

    # Round 202 (design 13.17): settings save themselves; another button on
    # the page (an action) waits for what was just typed.
    go("/admin/settings/site/")
    typed = js("""(() => {
        const box = document.querySelector('[data-autosave] [name=site_description]');
        if (!box) return 'no box';
        box.value = '浏览器自动保存的简介';
        box.dispatchEvent(new Event('input', {bubbles: true}));
        return 'typed';
    })()""")
    time.sleep(3)
    status = js("(document.querySelector('[data-autosave-status]') || {}).textContent")
    step("全站设置改了就自动保存", "已保存" in (status or ""), f"{typed} {status}")
    go("/admin/settings/site/")
    js("""(() => {
        const box = document.querySelector('[data-autosave] [name=site_description]');
        box.value = '点按钮之前先存上';
        box.dispatchEvent(new Event('input', {bubbles: true}));
        window.__journeyOld = true;
        document.querySelector('form[action*="send-test-email"] button').click();
    })()""")
    for _ in range(20):
        time.sleep(0.5)
        if js("!window.__journeyOld && document.readyState === 'complete'"):
            break
    go("/admin/settings/site/")
    flushed = js("document.querySelector('[name=site_description]').value")
    step("点别的按钮前先存好了刚改的", flushed == "点按钮之前先存上", flushed or "")

    # Round 203: a member group's people — search, one click to add, the
    # post saves itself, and it is all still there after a reload.
    go(f"/admin/member-groups/{data['group']}/")
    js("""(() => {
        const box = document.querySelector('[data-person-search] [name=q]');
        box.value = '截图队';
        box.dispatchEvent(new Event('input', {bubbles: true}));
    })()""")
    time.sleep(2)
    found = js("document.querySelectorAll('[data-person-results] form').length")
    step("搜得到人", (found or 0) > 0, str(found))
    js("document.querySelector('[data-person-results] form button').click()")
    time.sleep(2)
    people = js("document.querySelectorAll('[data-membership]').length")
    step("点一下就加进组里", people == 2, str(people))
    js("""(() => {
        const rows = document.querySelectorAll('[data-membership]');
        const box = rows[rows.length - 1].querySelector('[name=title]');
        box.value = '浏览器加的职务';
        box.dispatchEvent(new Event('input', {bubbles: true}));
    })()""")
    time.sleep(3)
    go(f"/admin/member-groups/{data['group']}/")
    kept = js("""[...document.querySelectorAll('[data-membership] [name=title]')]
        .map(box => box.value).join('|')""")
    step("职务改了就存，刷新还在", "浏览器加的职务" in (kept or ""), kept or "")

    # The back office's article form (round 196): the Markdown editor with
    # its own toolbar icons, the picture dialog, publishing.
    go("/admin/articles/new/")
    # Round 205 (design 13.17, v7.9): the first change makes the article, a
    # draft, with the category still empty; the address becomes its own.
    js("""(() => {
        const title = document.querySelector('#id_title');
        title.value = '浏览器写的文章';
        title.dispatchEvent(new Event('input', {bubbles: true}));
    })()""")
    for _ in range(20):
        time.sleep(0.5)
        if js("/^\\/admin\\/articles\\/\\d+\\/$/.test(location.pathname)"):
            break
    made = js(
        "location.pathname + '|' +"
        " document.querySelector('[data-autosave-status]').textContent"
    )
    where = (made or "").split("|")[0]
    step(
        "新文章打第一个字就建好（分类还空着）",
        where not in ("", "/admin/articles/new/") and "已保存" in (made or ""),
        made or "",
    )
    started = js("""(() => {
        const category = document.querySelector('#id_category');
        category.value = category.options[1].value;
        category.dispatchEvent(new Event('change', {bubbles: true}));
        const editor = document.querySelector('.CodeMirror');
        if (!editor) return 'no editor';
        editor.CodeMirror.setValue('## 小标题\\n\\n浏览器里写的正文。');
        return String(document.querySelectorAll('.editor-toolbar button use').length);
    })()""")
    step("编辑器起来了，工具栏有图标", started not in (None, "no editor", "0"), started)
    drawn = js("""(() => {
        const use = document.querySelector('.editor-toolbar button use');
        const id = use && use.getAttribute('href').slice(1);
        const icon = id && document.getElementById(id);
        return !!(icon && icon.querySelector('path'));
    })()""")
    step("工具栏图标画得出来", bool(drawn))
    js("""document.querySelector('#id_cover').closest('[data-image-picker]')
        .querySelector('[data-image-picker-choose]').click()""")
    time.sleep(2)
    picked = js("""(() => {
        const picture = document.querySelector('[data-pick-image]');
        if (!picture) return 'no picture';
        picture.click();
        return document.querySelector('#id_cover').value;
    })()""")
    step("对话框里选了封面", bool(picked) and picked.isdigit(), str(picked))
    for _ in range(20):
        time.sleep(0.5)
        state = "document.querySelector('[data-autosave-status]').dataset.state"
        if js(state) == "saved":
            break
    tools.send("Page.reload", {})
    time.sleep(2.5)
    kept = js("""document.querySelector('#id_title').value + '|' +
        document.querySelector('#id_cover').value + '|' +
        document.querySelector('.CodeMirror').CodeMirror.getValue().includes('浏览器里写的正文')""")
    step(
        "刷新以后草稿还在（标题、封面、正文）",
        bool(kept)
        and kept.startswith("浏览器写的文章|")
        and kept.endswith("|true")
        and kept.split("|")[1].isdigit(),
        kept or "",
    )
    press("button[name=publish]")
    step("文章发布了", says("已发布"))
    step("封面留在文章上", bool(js("document.querySelector('#id_cover').value")))

    # Round 206 (design 13.17, v7.10): a new scrim exists from its title, the
    # start still empty; publishing says what is missing, then goes through.
    go("/admin/scrims/new/")
    js("""(() => {
        const title = document.querySelector('#id_title');
        title.value = '浏览器建的内战';
        title.dispatchEvent(new Event('input', {bubbles: true}));
    })()""")
    for _ in range(20):
        time.sleep(0.5)
        if js("location.pathname.startsWith('/admin/scrims/edit/')"):
            break
    scrim_page = js("location.pathname") or ""
    made = scrim_page.startswith("/admin/scrims/edit/")
    step("新内战打标题就建好（开始时间还空着）", made, scrim_page)
    scrim_id = scrim_page.rstrip("/").rsplit("/", 1)[-1]
    go(f"/admin/scrims/{scrim_id}/publish/")
    step("发布页写着还缺开始时间", says("还没填好：开始时间"))
    go(scrim_page)
    js("""(() => {
        const start = document.querySelector('#id_starts_at');
        const when = new Date(Date.now() + 3 * 86400000);
        const pad = n => String(n).padStart(2, '0');
        start.value = when.getFullYear() + '-' + pad(when.getMonth() + 1) + '-' +
            pad(when.getDate()) + 'T20:00';
        start.dispatchEvent(new Event('change', {bubbles: true}));
    })()""")
    for _ in range(20):
        time.sleep(0.5)
        state = "document.querySelector('[data-autosave-status]').dataset.state"
        if js(state) == "saved":
            break
    go(f"/admin/scrims/{scrim_id}/publish/")
    press("main form.b-form button[type=submit]")
    step("补上开始时间就发布了", says("「浏览器建的内战」已发布"))

    tools.send("Runtime.evaluate", {"expression": "1"})
    for kind, text in EVENTS:
        print(f"    浏览器报告 {kind}: {text[:200]}")
    step("浏览器没有报错", not EVENTS, f"（{len(EVENTS)} 条）" if EVENTS else "")
    return failed


def main() -> int:
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)
    env = screens.site_env()
    if not (ROOT / "static/css/app.css").exists():
        screens.manage("tailwind", "build")
    screens.manage("migrate", "--noinput", stdout=subprocess.DEVNULL)
    screens.manage("createcachetable")
    screens.manage("init_site", "--verbosity", "0", stdout=subprocess.DEVNULL)
    seeded = subprocess.run(
        [sys.executable, str(ROOT / "scripts/screens.py"), "seed"],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(seeded.stdout.strip().splitlines()[-1])

    port, debug = screens.free_port(), screens.free_port()
    server = subprocess.Popen(
        [sys.executable, "manage.py", "runserver", f"127.0.0.1:{port}", "--noreload"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    with LOG.open("w") as log:
        worker = subprocess.Popen(
            [sys.executable, "manage.py", "run_worker"],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    browser = subprocess.Popen(
        [
            "chromium",
            "--headless=new",
            "--no-sandbox",
            f"--remote-debugging-port={debug}",
            f"--user-data-dir={WORK / 'profile'}",
            "--window-size=1280,900",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        base = f"http://127.0.0.1:{port}"
        screens.wait_for(f"{base}/robots.txt")
        screens.wait_for(f"http://127.0.0.1:{debug}/json/version")
        targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{debug}/json"))
        page = next(t for t in targets if t.get("type") == "page")
        tools = Watching(page["webSocketDebuggerUrl"])
        for domain in ("Page", "Runtime", "Log", "Network"):
            tools.send(f"{domain}.enable")
        if "admin" in sys.argv[1:]:
            subprocess.run(
                [
                    sys.executable,
                    __file__,
                    "players",
                    str(data["scrim"]),
                    str(data["cup"]),
                ],
                cwd=ROOT,
                env=env,
                check=True,
            )
            failed = officers(tools, base, data)
        elif "pages" in sys.argv[1:]:
            listed = subprocess.run(
                [sys.executable, __file__, "routes"],
                cwd=ROOT,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            routes = json.loads(listed.stdout.strip().splitlines()[-1])
            failed = sweep(tools, base, data, routes)
        else:
            failed = journey(tools, base, data)
    finally:
        for process in (browser, worker, server):
            process.terminate()
        for process in (browser, worker, server):
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
    print("全部走通" if not failed else f"没走通：{'、'.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["routes"]:
        sys.path.insert(0, str(ROOT))
        print(json.dumps(list_routes()))
    elif sys.argv[1:2] == ["players"]:
        sys.path.insert(0, str(ROOT))
        add_players(int(sys.argv[2]), int(sys.argv[3]))
    else:
        raise SystemExit(main())
