"""Round 216: the account and core fixes from the review (A4-A13, C7-C10).

Each test here names the review item it guards. They are written so that
taking the fix out turns them red (AGENTS.md hard rule 7).
"""

import contextlib
import ipaddress
import threading
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from allauth.account.models import EmailAddress
from django.apps import apps
from django.contrib.messages import get_messages
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connections, transaction
from django.urls import reverse
from django.utils import timezone
from PIL import Image, ImageOps, PngImagePlugin

from accounts.images import AvatarError, square_face
from accounts.models import GameAccount, User
from accounts.views import DELETE_TRIES_PER_HOUR
from core import net, ratelimit
from core.fields import EncryptedTextField

ROOT = Path(__file__).resolve().parents[2]
PASSWORD = "Correct-Horse-Battery-1"


def _user(email="216@example.com", **kwargs):
    kwargs.setdefault("nickname", "二一六")
    kwargs.setdefault("password", PASSWORD)
    kwargs.setdefault("agreed_terms_at", timezone.now())
    kwargs.setdefault("agreed_cross_border_at", timezone.now())
    return User.objects.create_user(email=email, **kwargs)


# --- A4: a picture whose EXIF cannot be read is the person's error, not a 500 ---


def _png_with_broken_exif_profile() -> bytes:
    info = PngImagePlugin.PngInfo()
    # Pillow reads this chunk as hex after three header lines; "zz" is not hex.
    info.add_text("Raw profile type exif", "\nexif\n    10\nzz-not-hex\n")
    buffer = BytesIO()
    Image.new("RGB", (200, 200), "red").save(buffer, "PNG", pnginfo=info)
    return buffer.getvalue()


def test_the_broken_exif_png_really_trips_exif_transpose():
    """Keeps the A4 test below meaningful: this file decodes and loads fine
    and only fails in ImageOps.exif_transpose (216, A4)."""
    picture = Image.open(BytesIO(_png_with_broken_exif_profile()))
    picture.load()
    with pytest.raises(ValueError):
        ImageOps.exif_transpose(picture)


def test_a_picture_with_broken_exif_is_an_avatar_error():
    """216, A4: exif_transpose ran outside the try, so a malformed EXIF
    profile came out as a ValueError (a 500) instead of AvatarError."""
    upload = SimpleUploadedFile(
        "broken.png", _png_with_broken_exif_profile(), "image/png"
    )
    with pytest.raises(AvatarError) as caught:
        square_face(upload)
    assert "读不出" in str(caught.value)


# --- A5: changing the sign-in email asks for the password again ----------------


@pytest.mark.django_db
def test_adding_an_email_without_recent_password_goes_to_reauthenticate(client):
    """216, A5: with a session alone (force_login records no authentication)
    the email cannot be changed; allauth sends the person to re-enter the
    password, and nothing is added."""
    user = _user()
    client.force_login(user)
    response = client.post(
        reverse("account_email"),
        {"action_add": "", "email": "thief@example.com"},
    )
    assert response.status_code == 302
    assert response.url.startswith(reverse("account_reauthenticate"))
    assert not EmailAddress.objects.filter(email="thief@example.com").exists()
    user.refresh_from_db()
    assert user.email == "216@example.com"


# --- A6: the delete page's password box is rate limited -------------------------


@pytest.mark.django_db
def test_deleting_the_account_stops_after_too_many_wrong_passwords(client):
    """216, A6: after DELETE_TRIES_PER_HOUR wrong passwords in an hour even
    the right one is refused, so a stolen session cannot guess on."""
    user = _user()
    client.force_login(user)
    for _ in range(DELETE_TRIES_PER_HOUR):
        response = client.post(reverse("me_delete"), {"password": "wrong"})
        assert response.status_code == 200  # the form again, "密码不对"
    response = client.post(reverse("me_delete"), {"password": PASSWORD}, follow=True)
    texts = [str(message) for message in get_messages(response.wsgi_request)]
    assert any("尝试太频繁了" in text for text in texts), texts
    user.refresh_from_db()
    assert user.is_active
    assert user.email == "216@example.com"


# --- A7: a rank saved through update_fields moves its date ---------------------


@pytest.mark.django_db
def test_a_rank_saved_with_update_fields_moves_its_date():
    """216, A7: autosave saves only the changed fields; the date was stamped
    on the instance but not written, so a fresh rank greyed out as stale."""
    user = _user()
    account = GameAccount.objects.create(user=user, battletag="Rank#2160", rank_tank=20)
    old = timezone.now() - timedelta(days=400)
    GameAccount.objects.filter(pk=account.pk).update(ranks_updated_at=old)

    account = GameAccount.objects.get(pk=account.pk)
    account.rank_tank = 30
    account.save(update_fields=["rank_tank"])

    stored = GameAccount.objects.values("rank_tank", "ranks_updated_at").get(
        pk=account.pk
    )
    assert stored["rank_tank"] == 30
    assert stored["ranks_updated_at"] > timezone.now() - timedelta(minutes=5)


# --- A10: the rate-limit count is one transaction -------------------------------


@pytest.mark.django_db
def test_over_limit_counts_inside_a_transaction(monkeypatch):
    """216, A10: every cache call of over_limit happens inside the module's
    transaction.atomic(), so the database cache's get-then-set incr cannot
    interleave with another request's."""
    state = {"depth": 0, "entered": 0, "calls": []}

    @contextlib.contextmanager
    def recording_atomic(*args, **kwargs):
        with transaction.atomic(*args, **kwargs):
            state["depth"] += 1
            state["entered"] += 1
            try:
                yield
            finally:
                state["depth"] -= 1

    class RecordingCache:
        def __getattr__(self, name):
            real = getattr(cache, name)

            def call(*args, **kwargs):
                state["calls"].append((name, state["depth"]))
                return real(*args, **kwargs)

            return call

    monkeypatch.setattr(
        ratelimit, "transaction", SimpleNamespace(atomic=recording_atomic)
    )
    monkeypatch.setattr(ratelimit, "cache", RecordingCache())

    assert ratelimit.over_limit("216-a10", 1, 60) is False
    assert ratelimit.over_limit("216-a10", 1, 60) is True
    assert state["entered"] == 2
    assert [name for name, _ in state["calls"]] == ["add", "add", "incr"]
    assert all(depth > 0 for _, depth in state["calls"]), state["calls"]


@pytest.mark.django_db(transaction=True)
def test_concurrent_hits_are_all_counted():
    """216, A10 with real threads and connections: eight hits at once count
    eight. (Not guaranteed to go red without the fix, since the race needs
    an unlucky interleaving; the test above is the deterministic guard.)"""
    key = "216-a10-threads"
    bucket = int(ratelimit.time.time() // 60)
    cache_key = f"sjtu_ow:rl:{key}:{bucket}"
    # The cache table is not a model, so a transaction test's flush leaves
    # it alone: start and end clean, or a re-run would count on from 8.
    cache.delete(cache_key)
    start = threading.Barrier(8)
    errors = []

    def hit():
        start.wait()
        try:
            ratelimit.over_limit(key, 100, 60)
        except Exception as exc:  # noqa: BLE001 - the exception is the result
            errors.append(exc)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=hit) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert all(not thread.is_alive() for thread in threads), "有线程卡住了"
    assert not errors, errors
    try:
        assert cache.get(cache_key) == 8
    finally:
        cache.delete(cache_key)


# --- A13: someone else's game account is out of reach --------------------------


@pytest.mark.django_db
def test_cannot_edit_or_delete_another_users_game_account(client):
    """216, A13: the edit and delete views look the account up among the
    signed-in person's own; anyone else's is a 404 and stays as it was."""
    owner = _user(email="owner216@example.com", nickname="主人216")
    stranger = _user(email="stranger216@example.com", nickname="路人216")
    account = GameAccount.objects.create(
        user=owner, battletag="Owner#2160", rank_tank=20
    )
    client.force_login(stranger)
    edit = reverse("me_game_account_edit", args=[account.pk])
    data = {
        "battletag": "Stolen#2160",
        "rank_tank": "40",
        "rank_damage": "",
        "rank_support": "",
    }
    assert client.get(edit).status_code == 404
    assert client.post(edit, data).status_code == 404
    assert client.post(edit, data, headers={"X-Autosave": "1"}).status_code == 404
    delete = reverse("me_game_account_delete", args=[account.pk])
    assert client.post(delete).status_code == 404
    stored = GameAccount.objects.get(pk=account.pk)
    assert stored.user_id == owner.pk
    assert stored.battletag == "Owner#2160"
    assert stored.rank_tank == 20


# --- C7: restore checks the key against every encrypted column ------------------


def test_restore_lists_every_encrypted_column():
    """216, C7: the AI key (197) was missing from ENCRYPTED_COLUMNS, so a
    backup holding only that secret passed the key check with a wrong key."""
    from core.management.commands.restore import ENCRYPTED_COLUMNS

    in_models = {
        (model._meta.db_table, field.column)
        for model in apps.get_models()
        for field in model._meta.concrete_fields
        if isinstance(field, EncryptedTextField)
    }
    assert in_models  # the comparison below must not be two empty sets
    assert set(ENCRYPTED_COLUMNS) == in_models


# --- C8: internal addresses, and connecting to the address that was checked -----


@pytest.mark.parametrize(
    "address", ["100.96.0.1", "100.64.0.1", "::ffff:10.0.0.1", "10.0.0.1", "::1"]
)
def test_internal_addresses_are_internal(address):
    """216, C8: the shared carrier range 100.64.0.0/10 (the production
    server's WARP network sits in it) and IPv4 written as IPv6 are internal."""
    assert net.is_internal(ipaddress.ip_address(address))


def test_a_public_address_is_not_internal():
    assert not net.is_internal(ipaddress.ip_address("8.8.8.8"))


def test_public_addresses_refuses_a_name_with_any_internal_address(monkeypatch):
    """216, C8: one internal address among the answers is enough to refuse."""
    monkeypatch.setattr(
        net,
        "resolved_addresses",
        lambda host, port: [
            ipaddress.ip_address("93.184.216.34"),
            ipaddress.ip_address("100.96.0.1"),
        ],
    )
    with pytest.raises(net.UnsafeUrl):
        net.public_addresses("fonts.example.com", 443)

    monkeypatch.setattr(
        net, "resolved_addresses", lambda host, port: [ipaddress.ip_address("8.8.8.8")]
    )
    assert net.public_addresses("fonts.example.com", 443) == [
        ipaddress.ip_address("8.8.8.8")
    ]


class _Connected(Exception):
    """Stands in for the network: the socket call was reached."""


def test_font_download_connects_to_the_checked_address(monkeypatch):
    """216, C8: urllib used to look the name up again to connect (DNS
    rebinding); the pinned connection dials the address that was checked."""
    from core.fonts import download

    monkeypatch.setattr(
        net,
        "resolved_addresses",
        lambda host, port: [ipaddress.ip_address("93.184.216.34")],
    )
    dialled = []

    def fake_create_connection(address, *args, **kwargs):
        dialled.append(address)
        raise _Connected

    monkeypatch.setattr(download.socket, "create_connection", fake_create_connection)
    connection = download._PinnedHTTPSConnection("fonts.example.com", 443, timeout=5)
    with pytest.raises(_Connected):
        connection.connect()
    assert dialled == [("93.184.216.34", 443)]


def test_font_download_refuses_an_internal_answer_before_connecting(monkeypatch):
    """216, C8: a name answering with an internal address never gets a socket."""
    from core.fonts import download

    monkeypatch.setattr(
        net,
        "resolved_addresses",
        lambda host, port: [ipaddress.ip_address("100.96.0.1")],
    )
    dialled = []

    def fake_create_connection(address, *args, **kwargs):
        dialled.append(address)
        raise _Connected

    monkeypatch.setattr(download.socket, "create_connection", fake_create_connection)
    connection = download._PinnedHTTPSConnection("fonts.example.com", 443, timeout=5)
    with pytest.raises(download.DownloadError):
        connection.connect()
    assert dialled == []


def test_the_font_opener_uses_the_pinned_connection():
    """216, C8: the pinned connection is only worth something if the opener
    that fetch_bytes uses actually picks it for https."""
    from core.fonts import download

    https = [
        handler
        for handler in download._opener.handlers
        if hasattr(handler, "https_open")
    ]
    assert len(https) == 1
    assert isinstance(https[0], download._PinnedHTTPSHandler)


# --- C10: the container does not run as root; backups stay out of the image -----


def test_the_image_runs_as_a_plain_user():
    """216, C10: a USER line after the useradd and before CMD."""
    lines = [
        line.strip()
        for line in (ROOT / "Dockerfile").read_text(encoding="utf-8").splitlines()
    ]
    useradd = next(i for i, line in enumerate(lines) if "useradd" in line)
    user = next(i for i, line in enumerate(lines) if line == "USER app")
    cmd = max(i for i, line in enumerate(lines) if line.startswith("CMD"))
    assert useradd < user < cmd
    assert not any(
        line.startswith("USER") and line != "USER app" for line in lines[user:]
    )


def test_backups_stay_out_of_the_image():
    """216, C10: backups hold everyone's email and contacts."""
    lines = {
        line.strip()
        for line in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    }
    assert "backups" in lines


def test_font_download_through_a_proxy_checks_the_font_host(monkeypatch):
    """216, C8 follow-up: behind HTTPS_PROXY the connection's ``host`` is the
    proxy. The name to check (and to verify TLS against) is the font host;
    the proxy itself may well sit on an internal address."""
    import http.client

    from core.fonts import download

    asked = []

    def resolve(host, port):
        asked.append(host)
        if host == "fonts.example":
            return [ipaddress.ip_address("10.0.0.5")]
        return [ipaddress.ip_address("93.184.216.34")]

    monkeypatch.setattr("core.net.resolved_addresses", resolve)
    tunnelled = []
    monkeypatch.setattr(
        http.client.HTTPSConnection, "connect", lambda self: tunnelled.append(self)
    )

    refused = download._PinnedHTTPSConnection("proxy.internal", 3128)
    refused.set_tunnel("fonts.example", 443)
    with pytest.raises(download.DownloadError):
        refused.connect()
    assert asked == ["fonts.example"] and not tunnelled

    asked.clear()
    allowed = download._PinnedHTTPSConnection("proxy.internal", 3128)
    allowed.set_tunnel("fonts.public.example", 443)
    allowed.connect()
    assert asked == ["fonts.public.example"]
    assert tunnelled == [allowed]  # the standard library tunnels and checks TLS
