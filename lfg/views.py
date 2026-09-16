"""LFG board (design 6.3). The shell is static; the list is loaded live."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from core.models import GameMode
from core.ratelimit import over_limit
from lfg import services
from lfg.forms import LfgPostForm
from lfg.models import LfgPost, LfgStatus

POST_LIMIT = 10  # per user per hour (design 附录 C)
HOUR = 60 * 60
ROLE_NAMES = ("tank", "damage", "support")


@require_GET
def lfg_index(request):
    """The static shell: nav, filters and an empty list container."""
    return render(
        request,
        "lfg/index.html",
        {"modes": GameMode.objects.filter(is_active=True)},
    )


@require_GET
def lfg_list(request):
    """The list itself; the login check lives here (design 13.13.1)."""
    if not request.user.is_authenticated:
        return render(request, "lfg/_login_required.html", status=200)
    roles = [name for name in ROLE_NAMES if request.GET.get(name) == "1"]
    posts = services.filtered_posts(
        mode_id=request.GET.get("mode") or None,
        roles=roles,
        open_only=request.GET.get("open") == "1",
    )
    return render(
        request,
        "lfg/_list.html",
        {"posts": posts, "now": request.GET.get("t", "")},
    )


@login_required
def lfg_create(request):
    allowed, reason = services.can_post(request.user)
    form = LfgPostForm(request.POST or None, user=request.user)
    if request.method == "POST":
        if not allowed:
            messages.error(request, reason)
        elif over_limit(f"lfg_post:{request.user.pk}", POST_LIMIT, HOUR):
            messages.error(request, "发车太频繁了，过一会儿再试。")
        elif form.is_valid():
            try:
                services.create_post(
                    user=request.user,
                    game_account=form.cleaned_data["game_account"],
                    mode=form.cleaned_data["mode"],
                    roles=form.roles(),
                    start_at=form.cleaned_data["start_at"],
                    note=form.cleaned_data.get("note", ""),
                )
            except services.LfgError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, "车帖已发布。")
                return redirect("lfg_index")
    return render(
        request,
        "lfg/form.html",
        {"form": form, "allowed": allowed, "reason": reason, "post": None},
    )


@login_required
def lfg_edit(request, pk):
    post = get_object_or_404(LfgPost, pk=pk, owner=request.user)
    form = LfgPostForm(request.POST or None, instance=post, user=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            services.update_post(
                post=post,
                user=request.user,
                game_account=form.cleaned_data["game_account"],
                mode=form.cleaned_data["mode"],
                roles=form.roles(),
                start_at=form.cleaned_data["start_at"],
                note=form.cleaned_data.get("note", ""),
            )
        except services.LfgError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "车帖已更新。")
            return redirect("lfg_index")
    return render(
        request,
        "lfg/form.html",
        {"form": form, "allowed": True, "reason": "", "post": post},
    )


@login_required
@require_POST
def lfg_status(request, pk):
    post = get_object_or_404(LfgPost, pk=pk)
    try:
        services.set_status(
            post=post, user=request.user, status=request.POST.get("status", "")
        )
    except services.LfgError as exc:
        messages.error(request, str(exc))
    else:
        labels = dict(LfgStatus.choices)
        messages.success(request, f"车帖已标记为「{labels[post.status]}」。")
    return redirect("lfg_index")
