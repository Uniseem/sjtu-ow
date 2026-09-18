"""Front-end views for personal center (design 13.4 / 13.5)."""

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from accounts.forms import (
    ContactMethodForm,
    DeleteAccountForm,
    GameAccountForm,
    ProfileForm,
    game_account_limit_reached,
)
from accounts.models import ContactMethod, GameAccount
from accounts.services import (
    AccountDeletionError,
    delete_account,
    deletion_blocked_reason,
    deletion_blockers,
    max_game_accounts,
    personal_data,
    profile_gaps,
)
from core.ratelimit import over_limit

ME_NAV = (
    ("me_profile", "基本资料", True),
    ("me_game_accounts", "游戏 ID 与段位", True),
    ("me_contacts", "联系方式", True),
    ("me_teams", "我的战队", True),
    ("me_registrations", "我的报名", True),
    ("me_security", "账号安全", True),
)


def _apply_validation_error(form, exc: ValidationError) -> None:
    if getattr(exc, "error_dict", None):
        for field, messages_ in exc.message_dict.items():
            target = field if field in form.fields else None
            form.add_error(target, messages_)
        return
    form.add_error(None, exc)


def me_context(request, current: str, **extra):
    """Shared context for every 个人中心 page; other apps use it too."""
    return {
        "current_me": current,
        "me_nav": ME_NAV,
        "profile_gaps": profile_gaps(request.user),
        **extra,
    }


_me_context = me_context


@login_required
@require_http_methods(["GET", "POST"])
def me_profile(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "资料已保存。")
            return redirect("me_profile")
    else:
        form = ProfileForm(instance=request.user)
    return render(
        request,
        "me/profile.html",
        _me_context(request, "me_profile", form=form),
    )


@login_required
@require_http_methods(["GET", "POST"])
def me_game_accounts(request):
    user = request.user
    at_limit = game_account_limit_reached(user)
    if request.method == "POST":
        form = GameAccountForm(request.POST, user=user)
        if at_limit:
            form.add_error(None, f"每人最多绑定 {max_game_accounts()} 个游戏 ID。")
        elif form.is_valid():
            try:
                form.save()
            except ValidationError as exc:
                _apply_validation_error(form, exc)
            else:
                if request.htmx:
                    return _game_accounts_list_response(request)
                messages.success(request, "游戏 ID 已添加。")
                return redirect("me_game_accounts")
        if request.htmx:
            return render(
                request,
                "me/game_accounts.html#form_response",
                _game_accounts_form_context(request, form=form),
            )
    else:
        form = GameAccountForm(user=user) if request.GET.get("new") else None
        if form and at_limit:
            messages.error(request, f"每人最多绑定 {max_game_accounts()} 个游戏 ID。")
            if request.htmx:
                return _game_accounts_list_response(request)
            return redirect("me_game_accounts")
    if request.htmx and form is not None:
        return render(
            request,
            "me/game_accounts.html#form_response",
            _game_accounts_form_context(request, form=form),
        )
    return render(
        request,
        "me/game_accounts.html",
        _game_accounts_page_context(request, form=form),
    )


@login_required
@require_http_methods(["GET", "POST"])
def me_game_account_edit(request, pk: int):
    account = get_object_or_404(GameAccount, pk=pk, user=request.user)
    if request.method == "POST":
        form = GameAccountForm(request.POST, instance=account, user=request.user)
        if form.is_valid():
            try:
                form.save()
            except ValidationError as exc:
                _apply_validation_error(form, exc)
            else:
                if request.htmx:
                    return render(
                        request,
                        "me/game_accounts.html#card_response",
                        _me_context(request, "me_game_accounts", account=account),
                    )
                messages.success(request, "游戏 ID 已更新。")
                return redirect("me_game_accounts")
    else:
        form = GameAccountForm(instance=account, user=request.user)
    if request.htmx:
        return render(
            request,
            "me/game_accounts.html#form_response",
            _game_accounts_form_context(request, form=form, account=account),
        )
    return render(
        request,
        "me/game_accounts.html",
        _game_accounts_page_context(request, form=form, editing=account),
    )


@login_required
@require_POST
def me_game_account_delete(request, pk: int):
    account = get_object_or_404(GameAccount, pk=pk, user=request.user)
    blocked = deletion_blocked_reason(account)
    if blocked:
        if request.htmx:
            return HttpResponse(blocked, status=400)
        messages.error(request, blocked)
        return redirect("me_game_accounts")
    account.delete()
    if request.htmx:
        return _game_accounts_list_response(request)
    messages.success(request, "游戏 ID 已删除。")
    return redirect("me_game_accounts")


@login_required
@require_http_methods(["GET", "POST"])
def me_contacts(request):
    if request.method == "POST":
        form = ContactMethodForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                form.save()
            except ValidationError as exc:
                _apply_validation_error(form, exc)
            else:
                if request.htmx:
                    return _contacts_list_response(request)
                messages.success(request, "联系方式已添加。")
                return redirect("me_contacts")
        if request.htmx:
            return render(
                request,
                "me/contacts.html#form_response",
                _contacts_form_context(request, form=form),
            )
    else:
        form = ContactMethodForm(user=request.user) if request.GET.get("new") else None
    if request.htmx and form is not None:
        return render(
            request,
            "me/contacts.html#form_response",
            _contacts_form_context(request, form=form),
        )
    return render(
        request,
        "me/contacts.html",
        _contacts_page_context(request, form=form),
    )


@login_required
@require_http_methods(["GET", "POST"])
def me_contact_edit(request, pk: int):
    contact = get_object_or_404(ContactMethod, pk=pk, user=request.user)
    if request.method == "POST":
        form = ContactMethodForm(request.POST, instance=contact, user=request.user)
        if form.is_valid():
            try:
                form.save()
            except ValidationError as exc:
                _apply_validation_error(form, exc)
            else:
                if request.htmx:
                    return render(
                        request,
                        "me/contacts.html#row_response",
                        _me_context(request, "me_contacts", contact=contact),
                    )
                messages.success(request, "联系方式已更新。")
                return redirect("me_contacts")
    else:
        form = ContactMethodForm(instance=contact, user=request.user)
    if request.htmx:
        return render(
            request,
            "me/contacts.html#form_response",
            _contacts_form_context(request, form=form, contact=contact),
        )
    return render(
        request,
        "me/contacts.html",
        _contacts_page_context(request, form=form, editing=contact),
    )


@login_required
@require_POST
def me_contact_delete(request, pk: int):
    contact = get_object_or_404(ContactMethod, pk=pk, user=request.user)
    contact.delete()
    if request.htmx:
        return _contacts_list_response(request)
    messages.success(request, "联系方式已删除。")
    return redirect("me_contacts")


@login_required
@require_http_methods(["GET"])
def me_security(request):
    return render(
        request,
        "me/security.html",
        _me_context(
            request,
            "me_security",
            password_url=reverse("account_change_password"),
            email_url=reverse("account_email"),
        ),
    )


EXPORTS_PER_HOUR = 5  # design 3.8 (default)


@login_required
def me_export(request):
    """Design 3.8: the user's own data as a JSON download."""
    if over_limit(f"me-export:{request.user.pk}", EXPORTS_PER_HOUR, 3600):
        messages.error(request, "导出太频繁了，请一小时后再试。")
        return redirect("me_security")
    response = JsonResponse(
        personal_data(request.user),
        json_dumps_params={"ensure_ascii": False, "indent": 2},
    )
    response["Content-Disposition"] = 'attachment; filename="sjtu-ow-my-data.json"'
    response["Cache-Control"] = "no-store"
    return response


@login_required
@require_http_methods(["GET", "POST"])
def me_delete(request):
    """Design 3.8: anonymise the account after the password is confirmed."""
    blockers = deletion_blockers(request.user)
    form = DeleteAccountForm(request.POST or None, user=request.user)
    if request.method == "POST" and not blockers and form.is_valid():
        try:
            delete_account(request.user)
        except AccountDeletionError as exc:
            blockers = [str(exc)]
        else:
            logout(request)
            messages.success(request, "账号已注销。")
            return redirect("home")
    return render(
        request,
        "me/delete.html",
        _me_context(request, "me_security", form=form, blockers=blockers),
    )


def _game_accounts_page_context(request, form=None, editing=None):
    accounts = request.user.game_accounts.order_by("pk")
    return _me_context(
        request,
        "me_game_accounts",
        accounts=accounts,
        form=form,
        editing=editing,
        at_limit=game_account_limit_reached(request.user),
        max_game_accounts=max_game_accounts(),
    )


def _game_accounts_form_context(request, form, account=None):
    action = (
        reverse("me_game_account_edit", args=[account.pk])
        if account
        else reverse("me_game_accounts")
    )
    return _me_context(
        request,
        "me_game_accounts",
        form=form,
        account=account,
        form_action=action,
        cancel_url=reverse("me_game_accounts"),
    )


def _game_accounts_list_response(request):
    return render(
        request,
        "me/game_accounts.html#account_list",
        _game_accounts_page_context(request),
    )


def _contacts_page_context(request, form=None, editing=None):
    contacts = request.user.contact_methods.order_by("type", "pk")
    return _me_context(
        request,
        "me_contacts",
        contacts=contacts,
        form=form,
        editing=editing,
    )


def _contacts_form_context(request, form, contact=None):
    action = (
        reverse("me_contact_edit", args=[contact.pk])
        if contact
        else reverse("me_contacts")
    )
    return _me_context(
        request,
        "me_contacts",
        form=form,
        contact=contact,
        form_action=action,
        cancel_url=reverse("me_contacts"),
    )


def _contacts_list_response(request):
    return render(
        request,
        "me/contacts.html#contact_list",
        _contacts_page_context(request),
    )
