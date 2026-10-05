"""「发信」: the letters an action wrote, sent or not by the person who did
it (design 10.5, v7.8). The site's own pages live here; the back office's
(``backoffice.views.letters``) draw the same thing in its look."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_GET

from core import letters, outbox
from core.converters import as_id


def _safe(request, url: str, fallback: str) -> str:
    if url and url_has_allowed_host_and_scheme(
        url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return url
    return fallback


def _rows(request, found) -> list[dict]:
    return [
        {
            "pk": row.pk,
            "subject": row.letter.get("subject", ""),
            "who": outbox.who(row, request.user),
            "count": len(row.recipients),
            "preview": reverse("letters_preview", args=[row.batch, row.pk]),
        }
        for row in found
    ]


def confirm(request, batch, *, template: str, fallback: str, context=None):
    """The page both sides draw: GET shows the letters, POST sends the ticked
    ones (or none) and goes where the action was going."""
    from core.models import HeldLetter

    found = list(outbox.waiting(request.user).filter(batch=batch))
    if not found:
        done = HeldLetter.objects.filter(batch=batch, actor=request.user).first()
        if done is None:
            raise Http404("没有这件事的信。")
        if done.state == HeldLetter.State.WAITING:
            messages.info(request, "这件事的信等了 7 天没发，已经作废。")
        else:
            messages.info(request, "这件事的信已经处理过了。")
        return redirect(_safe(request, done.back, fallback))
    back = _safe(request, found[0].back, fallback)
    if request.method == "POST":
        keep = set()
        if not request.POST.get("skip"):
            keep = {as_id(value) for value in request.POST.getlist("send")} - {None}
        sent, people = outbox.decide(request.user, batch, keep)
        if sent:
            messages.success(request, f"信已经排队发出，共 {people} 人。")
        else:
            messages.info(request, "这次没有发信。")
        return redirect(back)
    return render(
        request,
        template,
        {
            "letters": _rows(request, found),
            "back": back,
            "page_title": "发信",
            **(context or {}),
        },
    )


@never_cache
@login_required
def letters_confirm(request, batch):
    return confirm(
        request,
        batch,
        template="core/letters/confirm.html",
        fallback=reverse("me_profile"),
    )


@never_cache
@login_required
@require_GET
def letters_waiting(request):
    return render(
        request,
        "core/letters/waiting.html",
        {"batches": outbox.batches(request.user)},
    )


@never_cache
@require_GET
@xframe_options_sameorigin
def letters_preview(request, batch, pk):
    """One held letter exactly as it goes out, for the frame on 「发信」."""
    from core.email_art import for_browser
    from core.models import HeldLetter
    from core.styleguide import EMAIL_CSP

    if not request.user.is_authenticated:
        raise Http404
    row = HeldLetter.objects.filter(batch=batch, pk=pk, actor=request.user).first()
    if row is None:
        raise Http404
    name = row.recipients[0][1] if row.recipients else ""
    html = letters.html_of(outbox.thaw(row.letter), name)
    response = HttpResponse(for_browser(html))
    response._csp_config = EMAIL_CSP
    return response
