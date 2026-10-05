"""Letters an action writes wait for the person who did it (design 10.5, v7.8).

User 10-05: 「然后所有的发信都必须手动点发信」. The fifteen letters some
action brings with it (an application, a decision, a cancellation …) go
through ``hold`` instead of ``core.letters.send``. Inside a signed-in
person's POST (``HeldLettersMiddleware`` opens a batch with ``asking``) they
are written down whole and the page goes on to 「发信」, where that person
sends them or not. Anywhere else (the worker, a command, a test calling a
service) nobody is there to ask, so they go at once as before.
"""

from __future__ import annotations

import dataclasses
import json
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from core import letters

WAIT = timedelta(days=7)
BACK_OFFICE = ("/admin/", "/wagtail/")


@dataclasses.dataclass
class Batch:
    key: uuid.UUID
    actor: object
    held: int = 0


_current: ContextVar[Batch | None] = ContextVar("held_letters", default=None)


@contextmanager
def asking(actor):
    """Letters ``hold`` gets inside this block wait for ``actor``."""
    batch = Batch(uuid.uuid4(), actor)
    token = _current.set(batch)
    try:
        yield batch
    finally:
        _current.reset(token)


def freeze(letter: letters.Letter) -> dict:
    """As the database gives it back (tuples become lists), so two writes of
    the same letter compare equal."""
    return json.loads(json.dumps(dataclasses.asdict(letter)))


def thaw(data: dict) -> letters.Letter:
    known = {field.name for field in dataclasses.fields(letters.Letter)}
    values = {key: value for key, value in data.items() if key in known}
    values["facts"] = [tuple(pair) for pair in values.get("facts", [])]
    values["items"] = [tuple(pair) for pair in values.get("items", [])]
    if values.get("action"):
        values["action"] = tuple(values["action"])
    return letters.Letter(**values)


def send_to(letter: letters.Letter, pairs, *, fail_silently: bool = False) -> int:
    """One message per (address, name), as ``core.letters.send`` does."""
    sent = 0
    for address, name in pairs:
        email = letters.message(letter, address, name)
        sent += email.send(fail_silently=fail_silently)
    return sent


def hold(letter: letters.Letter, recipients, *, fail_silently: bool = False) -> int:
    """Send ``letter`` once the person whose action wrote it says so.

    Returns how many went out now: 0 while it waits. The same letter to more
    people in one action (a cancelled tournament to each captain) is one
    letter with them all on it."""
    from core.models import HeldLetter

    pairs = [list(pair) for pair in letters.people(recipients)]
    if not pairs:
        return 0
    batch = _current.get()
    if batch is None:
        return send_to(letter, pairs, fail_silently=fail_silently)
    frozen = freeze(letter)
    for row in HeldLetter.objects.filter(batch=batch.key):
        if row.letter == frozen:
            known = {address for address, _name in row.recipients}
            row.recipients += [pair for pair in pairs if pair[0] not in known]
            row.save(update_fields=["recipients"])
            return 0
    HeldLetter.objects.create(
        batch=batch.key, actor=batch.actor, letter=frozen, recipients=pairs
    )
    batch.held += 1
    return 0


def waiting(actor):
    """This person's letters still waiting, newer than ``WAIT``."""
    from core.models import HeldLetter

    if not getattr(actor, "is_authenticated", False):
        return HeldLetter.objects.none()
    return HeldLetter.objects.filter(
        actor=actor,
        state=HeldLetter.State.WAITING,
        created_at__gte=timezone.now() - WAIT,
    )


def page_url(batch_key, *, in_back_office: bool) -> str:
    name = "backoffice:letters_confirm" if in_back_office else "letters_confirm"
    return reverse(name, args=[batch_key])


def settle(request, response, batch: Batch):
    """After the action: send, ask, or leave the letters waiting."""
    from core.models import HeldLetter

    rows = HeldLetter.objects.filter(batch=batch.key, state=HeldLetter.State.WAITING)
    if not batch.held or not rows.exists():
        return response
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated and user.pk == batch.actor.pk):
        # Nobody left to ask: the account was deleted and signed out.
        decide(batch.actor, batch.key, {row.pk for row in rows}, anyone=True)
        return response
    in_back_office = request.path.startswith(BACK_OFFICE)
    redirected = response.status_code in (301, 302, 303, 307, 308)
    back = response["Location"] if redirected else request.get_full_path()
    rows.update(back=back[:500], in_back_office=in_back_office)
    if not redirected:
        # An answer the page reads itself (autosave): the letters wait and
        # the reminders point at them (design 10.5).
        return response
    from django.shortcuts import redirect

    return redirect(page_url(batch.key, in_back_office=in_back_office))


def decide(actor, batch_key, keep, *, anyone: bool = False) -> tuple[int, int]:
    """Send the letters ``keep`` names, drop the rest of the batch. Each row
    is claimed once, so a second click sends nothing. Returns (letters,
    people) that went out."""
    from core.models import HeldLetter

    rows = (
        HeldLetter.objects.filter(batch=batch_key, state=HeldLetter.State.WAITING)
        if anyone
        else waiting(actor).filter(batch=batch_key)
    )
    now = timezone.now()
    sent = people = 0
    for row in rows:
        state = HeldLetter.State.SENT if row.pk in keep else HeldLetter.State.SKIPPED
        claimed = HeldLetter.objects.filter(
            pk=row.pk, state=HeldLetter.State.WAITING
        ).update(state=state, decided_at=now)
        if claimed and state == HeldLetter.State.SENT:
            send_to(thaw(row.letter), row.recipients, fail_silently=True)
            sent += 1
            people += len(row.recipients)
    return sent, people


@dataclasses.dataclass
class Waiting:
    """One action whose letters wait, for the reminders and the list."""

    key: uuid.UUID
    subjects: list[str]
    people: int
    at: object
    url: str


def batches(actor) -> list[Waiting]:
    found: dict = {}
    for row in waiting(actor).order_by("-created_at", "pk"):
        item = found.get(row.batch)
        if item is None:
            item = found[row.batch] = Waiting(
                row.batch,
                [],
                0,
                row.created_at,
                page_url(row.batch, in_back_office=row.in_back_office),
            )
        item.subjects.append(row.letter.get("subject", ""))
        item.people += len(row.recipients)
    return list(found.values())


def waiting_count(actor) -> int:
    return waiting(actor).values("batch").distinct().count()


def who(row, actor) -> str:
    """「你自己」, names, or 「某某等 N 人」."""
    own = getattr(actor, "email", "")
    names = [
        "你自己" if address == own else (name or address)
        for address, name in row.recipients
    ]
    if len(names) > 6:
        return "、".join(names[:5]) + f" 等 {len(names)} 人"
    return "、".join(names)
