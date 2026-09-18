"""Public scrim pages (design 9.2)."""

from __future__ import annotations

from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from scrims import services
from scrims.models import Role, Scrim, ScrimStatus
from scrims.slots import actions_context


@require_GET
def scrim_index(request):
    return render(
        request,
        "scrims/index.html",
        {"scrims": services.public_scrims().select_related()},
    )


def _visible_or_404(pk) -> Scrim:
    scrim = services.visible_scrim(pk)
    if scrim is None:
        raise Http404("内战不存在")
    return scrim


def share_info(request, scrim, counts) -> dict:
    """Design 13.14: title and start time; format and signup count; default image.

    Signups refresh the static page (round 057), so the count stays current.
    """
    from django.utils import timezone
    from django.utils.dateformat import format as format_date

    from content.seo import build_seo

    starts = format_date(timezone.localtime(scrim.starts_at), "n月j日 H:i")
    return build_seo(
        request,
        title=f"{scrim.title} · {starts}",
        description=f"{scrim.get_format_display()} · 已报名 {counts['total']} 人",
        kind="scrim",
        canonical=request.build_absolute_uri(reverse("scrim_detail", args=[scrim.pk])),
    )


@require_GET
def scrim_detail(request, pk):
    scrim = _visible_or_404(pk)
    signups = scrim.signups.select_related("user").all()
    counts = services.signup_counts(scrim)
    context = {
        "seo": share_info(request, scrim, counts),
        "scrim": scrim,
        # Design 9.2: nicknames and roles only. No ranks, no game IDs.
        "signups": signups,
        "counts": counts,
        "cancelled": scrim.status == ScrimStatus.CANCELLED,
    }
    context.update(actions_context(request, scrim))
    return render(request, "scrims/detail.html", context)


def _roles_from(request) -> list[str]:
    wanted = set(request.POST.getlist("roles"))
    return [role for role in Role.values if role in wanted]


@require_POST
def scrim_signup(request, pk):
    if not request.user.is_authenticated:
        return redirect_to_login(request)
    scrim = _visible_or_404(pk)
    try:
        services.sign_up(
            scrim=scrim,
            user=request.user,
            game_account_id=request.POST.get("game_account"),
            roles=_roles_from(request),
        )
    except services.ScrimError as exc:
        for problem in exc.problems:
            messages.error(request, problem)
    else:
        messages.success(request, "报名成功。")
    return redirect("scrim_detail", pk=scrim.pk)


@require_POST
def scrim_cancel_signup(request, pk):
    if not request.user.is_authenticated:
        return redirect_to_login(request)
    scrim = _visible_or_404(pk)
    try:
        services.cancel(scrim=scrim, user=request.user)
    except services.ScrimError as exc:
        for problem in exc.problems:
            messages.error(request, problem)
    else:
        messages.success(request, "已取消报名。")
    return redirect("scrim_detail", pk=scrim.pk)


def redirect_to_login(request):
    return redirect(f"{reverse('account_login')}?next={request.path}")


@require_GET
def scrim_actions_fragment(request, pk):
    """The personalised part of a prerendered detail page (design 13.13.3)."""
    scrim = services.visible_scrim(pk)
    if scrim is None:
        return HttpResponse(status=404)
    context = actions_context(request, scrim)
    context["oob"] = True
    response = render(request, "scrims/slots/actions.html", context)
    response["Cache-Control"] = "private, no-store"
    return response


@require_GET
def me_scrims(request):
    if not request.user.is_authenticated:
        return redirect_to_login(request)
    signups = (
        request.user.scrim_signups.select_related("scrim", "game_account")
        .exclude(scrim__status=ScrimStatus.DRAFT)
        .order_by("-scrim__starts_at")
    )
    return render(request, "scrims/me.html", {"signups": signups})


# Keep the import used by the admin split page in one place.
get_scrim = get_object_or_404
