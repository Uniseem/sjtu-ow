"""Full-page screenshots of signed-in pages, on the test machine (round 146).

    bash scripts/remote-check.sh run uv run python scripts/screens.py [WIDTH] [dark]

Builds a throwaway site in /tmp/sjtu-ow-screens (its own database and
uploads), seeds a member, a captain, a team, two tournaments and a scrim,
starts runserver on a free port, signs the test people in by making their
sessions server-side (no password is typed anywhere), and captures each page
with headless Chromium through its DevTools port. PNGs land in
/tmp/sjtu-ow-screens/out; copy them back with scp. Needs ``chromium`` and
``fonts-noto-cjk`` (installed on the test machine). Standard library only.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = Path("/tmp/sjtu-ow-screens")
OUT = WORK / "out"

# (file name, who is signed in, path). Paths use {team}, {cup}, {teamcup},
# {scrim} and {member}.
PAGES = [
    ("home-member", "member", "/"),
    ("me-profile", "member", "/me/"),
    ("me-registrations", "member", "/me/registrations/"),
    ("me-teams", "member", "/me/teams/"),
    ("me-scrims", "member", "/me/scrims/"),
    ("team-as-member", "member", "/teams/{team}/"),
    ("team-manage", "captain", "/teams/{team}/manage/"),
    ("cup-in-pool", "member", "/tournaments/{cup}/"),
    ("teamcup-as-captain", "captain", "/tournaments/{teamcup}/"),
    ("scrim-signed-up", "member", "/scrims/{scrim}/"),
    ("teams-by-role", "member", "/teams/?role=support"),
    ("members-free-supports", "captain", "/members/?role=support&free=1"),
    ("member-page", "captain", "/members/{member}/"),
    ("own-page", "member", "/members/{member}/"),
    ("mail-tournament-reminder", "member", "/_styleguide/emails/tournament-reminder/"),
    ("mail-tournament-update", "member", "/_styleguide/emails/tournament-update/"),
    ("mail-member-left", "member", "/_styleguide/emails/member-left/"),
    ("admin-activity", "officer", "/admin/activity/"),
    # The back office (round 196).
    ("admin-home", "officer", "/admin/"),
    ("admin-articles", "officer", "/admin/articles/"),
    ("admin-article", "officer", "/admin/articles/{article}/"),
    ("admin-article-member", "member", "/admin/articles/new/"),
    ("admin-tournaments", "officer", "/admin/tournaments/"),
    ("admin-tournament", "officer", "/admin/tournaments/edit/{cup}/"),
    ("admin-split", "officer", "/admin/scrims/{scrim}/split/"),
    ("admin-users", "officer", "/admin/users/"),
    ("admin-user", "officer", "/admin/users/{member}/"),
    ("admin-images", "officer", "/admin/images/"),
    ("admin-settings", "officer", "/admin/settings/site/"),
    # What saves itself (rounds 202, 203).
    ("admin-groups", "officer", "/admin/member-groups/"),
    ("admin-group", "officer", "/admin/member-groups/{group}/"),
    ("admin-group-search", "officer", "/admin/member-groups/{group}/?q=截图"),
    ("admin-group-new", "officer", "/admin/member-groups/new/"),
    ("admin-categories", "officer", "/admin/categories/"),
    ("admin-category", "officer", "/admin/categories/{category}/"),
    ("admin-team", "officer", "/admin/teams/edit/{team}/"),
    ("admin-image-collections", "officer", "/admin/images/collections/"),
    ("admin-typography", "officer", "/admin/settings/typography/"),
]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def site_env() -> dict:
    return {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "sjtu_ow.settings.dev",
        "DATABASE_PATH": str(WORK / "db.sqlite3"),
        "MEDIA_ROOT": str(WORK / "media"),
        "PYTHONUTF8": "1",
    }


def manage(*args, **kwargs):
    return subprocess.run(
        [sys.executable, "manage.py", *args],
        cwd=ROOT,
        env=site_env(),
        check=True,
        **kwargs,
    )


# --- the data -----------------------------------------------------------------


def seed() -> dict:
    """Runs inside Django (``screens.py seed``); prints what the shots need."""
    import django

    django.setup()
    from datetime import timedelta

    from allauth.account.models import EmailAddress
    from django.test import Client
    from django.utils import timezone

    from accounts.models import ContactMethod, ContactType, GameAccount, User
    from scrims import services as scrim_services
    from scrims.models import Role, Scrim, ScrimFormat, ScrimStatus
    from teams import services as team_services
    from teams.models import Team
    from tournaments import registration as reg
    from tournaments.models import Tournament, TournamentStatus

    now = timezone.now()

    def person(email, nickname, battletag):
        user = User.objects.create_user(
            email=email,
            password=None,
            nickname=nickname,
            is_sjtu=True,
            motto="周末晚上都在线，主玩支援。",
            main_role="support",
            agreed_terms_at=now,
            agreed_cross_border_at=now,
        )
        EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
        GameAccount.objects.create(
            user=user,
            battletag=battletag,
            rank_tank=18,
            rank_damage=20,
            rank_support=24,
        )
        ContactMethod.objects.create(user=user, type=ContactType.QQ, value="123456789")
        return user

    member = person("member@screens.test", "截图队员", "Member#5123")
    captain = person("captain@screens.test", "截图队长", "Captain#7001")
    mate = person("mate@screens.test", "截图队友", "Mate#7002")
    # For admin pages (round 162): a superuser, signed in like the others.
    officer = person("officer@screens.test", "截图站长", "Officer#7003")
    User.objects.filter(pk=officer.pk).update(is_superuser=True, is_staff=True)

    team = team_services.create_team(
        user=captain, name="截图战队", description="每周二、四晚上训练。"
    )
    for user in (member, mate):
        application = team_services.apply_to_team(
            team=team, user=user, roles={"support": True}
        )
        team_services.approve_application(application=application, actor=captain)
    Team.objects.filter(pk=team.pk).update(member_contact="QQ 群 123456789")

    window = {
        "registration_opens_at": now - timedelta(days=1),
        "registration_closes_at": now + timedelta(days=3),
        "starts_at": now + timedelta(days=5),
        "status": TournamentStatus.PUBLISHED,
        "published_at": now,
        "participant_contact": "选手群 987654321",
    }
    cup = Tournament.objects.create(
        title="截图个人杯", registration_mode="individual", **window
    )
    reg.sign_up_individual(
        tournament=cup,
        user=member,
        game_account_id=member.game_accounts.first().pk,
        roles=["support"],
    )
    teamcup = Tournament.objects.create(
        title="截图战队杯",
        registration_mode="team",
        roster_min=2,
        roster_max=6,
        **window,
    )
    reg.submit(
        tournament=teamcup,
        team=team,
        actor=captain,
        selections={
            str(m.user.pk): m.user.game_accounts.first().pk
            for m in team.memberships.all()
        },
    )
    scrim = Scrim.objects.create(
        title="截图内战",
        format=ScrimFormat.RQ_5V5,
        status=ScrimStatus.PUBLISHED,
        starts_at=now + timedelta(days=1),
    )
    scrim_services.sign_up(
        scrim=scrim,
        user=member,
        game_account_id=member.game_accounts.first().pk,
        roles=[Role.SUPPORT],
    )

    # For the back office's pages (round 196): an article, a category, a
    # plain page and a member group to open.
    from content.models import (
        ArticleCategory,
        ArticleIndexPage,
        ArticlePage,
        StandardPage,
    )
    from members.models import MemberGroup, MemberGroupMembership

    category = ArticleCategory.objects.order_by("pk").first()
    article = ArticlePage(
        title="截图攻略",
        slug="screens-guide",
        category=category,
        author=member,
        owner=member,
        summary="新人入门。",
        body="## 第一步\n\n先加一个游戏 ID。",
    )
    ArticleIndexPage.objects.get(slug="news").add_child(instance=article)
    article.save_revision(user=member).publish()
    # A picture in 投稿图片, for the picture dialog (journey.py admin).
    from io import BytesIO

    from django.core.files.base import ContentFile
    from PIL import Image as PILImage
    from wagtail.images import get_image_model

    from content.services import ensure_submission_image_collection

    buffer = BytesIO()
    PILImage.new("RGB", (64, 48), (155, 58, 51)).save(buffer, "PNG")
    get_image_model().objects.create(
        title="截图封面",
        file=ContentFile(buffer.getvalue(), name="screens-cover.png"),
        collection=ensure_submission_image_collection(),
    )
    group = MemberGroup.objects.create(name="截图干部")
    MemberGroupMembership.objects.create(group=group, user=officer, title="社长")

    sessions = {}
    for name, user in (("member", member), ("captain", captain), ("officer", officer)):
        client = Client()
        client.force_login(user)
        sessions[name] = client.cookies["sessionid"].value
    return {
        "sessions": sessions,
        "team": team.pk,
        "cup": cup.pk,
        "teamcup": teamcup.pk,
        "scrim": scrim.pk,
        "member": member.pk,
        "article": article.pk,
        "about": StandardPage.objects.get(slug="about").pk,
        "category": category.pk,
        "group": group.pk,
    }


# --- DevTools over a raw websocket (as handoff/rounds/106-page-transitions) --------


class DevTools:
    def __init__(self, url):
        rest = url.split("://", 1)[1]
        hostport, path = rest.split("/", 1)
        host, port = hostport.split(":")
        self.sock = socket.create_connection((host, int(port)), timeout=60)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall(
            (
                f"GET /{path} HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\n"
                f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
                "Sec-WebSocket-Version: 13\r\n\r\n"
            ).encode()
        )
        head = b""
        while b"\r\n\r\n" not in head:
            head += self.sock.recv(1)
        self.next_id = 0

    def _read(self, n):
        data = b""
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                raise ConnectionError("closed")
            data += chunk
        return data

    def _receive(self):
        parts = b""
        while True:
            b1, b2 = self._read(2)
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
            data = self._read(n)
            if b1 & 0x0F in (0x9, 0xA):
                continue
            parts += data
            if b1 & 0x80:
                return json.loads(parts.decode("utf-8"))

    def send(self, method, params=None):
        self.next_id += 1
        payload = json.dumps(
            {"id": self.next_id, "method": method, "params": params or {}}
        ).encode()
        header = bytearray([0x81])
        n = len(payload)
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header.append(0x80 | 126)
            header += struct.pack(">H", n)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", n)
        mask = os.urandom(4)
        header += mask
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(bytes(header) + masked)
        while True:
            message = self._receive()
            if message.get("id") == self.next_id:
                if "error" in message:
                    raise RuntimeError(message["error"])
                return message.get("result", {})


def wait_for(url, seconds=60):
    for _ in range(seconds * 5):
        try:
            return urllib.request.urlopen(url, timeout=2)
        except OSError:
            time.sleep(0.2)
    raise SystemExit(f"{url} 没有起来")


def shoot(width: int, scheme: str = "light", only=()):
    shutil.rmtree(WORK, ignore_errors=True)
    OUT.mkdir(parents=True)
    if not (ROOT / "static/css/app.css").exists():
        manage("tailwind", "build")
    manage("migrate", "--noinput", stdout=subprocess.DEVNULL)
    manage("createcachetable")
    manage("init_site", "--verbosity", "0", stdout=subprocess.DEVNULL)
    seeded = subprocess.run(
        [sys.executable, __file__, "seed"],
        cwd=ROOT,
        env=site_env(),
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(seeded.stdout.strip().splitlines()[-1])

    port, debug = free_port(), free_port()
    server = subprocess.Popen(
        [sys.executable, "manage.py", "runserver", f"127.0.0.1:{port}", "--noreload"],
        cwd=ROOT,
        env=site_env(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    profile = WORK / "chromium-profile"
    browser = subprocess.Popen(
        [
            "chromium",
            "--headless=new",
            "--no-sandbox",
            "--hide-scrollbars",
            f"--remote-debugging-port={debug}",
            f"--user-data-dir={profile}",
            f"--window-size={width},900",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_for(f"http://127.0.0.1:{port}/robots.txt")
        wait_for(f"http://127.0.0.1:{debug}/json/version")
        targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{debug}/json"))
        page = next(t for t in targets if t.get("type") == "page")
        tools = DevTools(page["webSocketDebuggerUrl"])
        tools.send("Page.enable")
        tools.send("Network.enable")
        tools.send(
            "Emulation.setEmulatedMedia",
            {"features": [{"name": "prefers-color-scheme", "value": scheme}]},
        )
        tools.send(
            "Emulation.setDeviceMetricsOverride",
            {
                "width": width,
                "height": 900,
                "deviceScaleFactor": 1,
                "mobile": width < 600,
            },
        )
        for name, who, path in PAGES:
            if only and not any(name.startswith(prefix) for prefix in only):
                continue
            tools.send("Network.clearBrowserCookies")
            tools.send(
                "Network.setCookie",
                {
                    "name": "sessionid",
                    "value": data["sessions"][who],
                    "domain": "127.0.0.1",
                    "path": "/",
                },
            )
            url = f"http://127.0.0.1:{port}" + path.format(**data)
            tools.send("Page.navigate", {"url": url})
            time.sleep(2.5)
            metrics = tools.send("Page.getLayoutMetrics")
            full = metrics.get("cssContentSize") or metrics["contentSize"]
            shot = tools.send(
                "Page.captureScreenshot",
                {
                    "format": "png",
                    "captureBeyondViewport": True,
                    "clip": {
                        "x": 0,
                        "y": 0,
                        "width": width,
                        "height": full["height"],
                        "scale": 1,
                    },
                },
            )
            target = OUT / f"{name}-{width}{'-dark' if scheme == 'dark' else ''}.png"
            target.write_bytes(base64.b64decode(shot["data"]))
            print(f"{target}  {int(full['height'])}px")
    finally:
        browser.terminate()
        server.terminate()
        browser.wait(timeout=10)
        server.wait(timeout=10)


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    if sys.argv[1:2] == ["seed"]:
        print(json.dumps(seed()))
    else:
        # screens.py 1280 [dark] [admin-group me-]: only pages starting so.
        shoot(
            int(sys.argv[1]) if len(sys.argv) > 1 else 375,
            "dark" if "dark" in sys.argv[2:] else "light",
            [arg for arg in sys.argv[2:] if arg not in ("dark", "light")],
        )
