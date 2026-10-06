"""成员 (docs/admin.md 4.4): users and their roles and rules, the roles and
their restrictions, teams, member groups.

Nobody is added or deleted here: registering needs the person's own consent
(design 3.1) and accounts are only ever stopped (3.7). Teams are founded by
their captains and end by disbanding (round 115).
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST
from wagtail.log_actions import log

from accounts.models import FeatureGroupRestriction, FeatureUserRule, User
from backoffice.forms import (
    ASSIGNED_ROLES,
    DeactivateForm,
    GroupRestrictionForm,
    MemberGroupForm,
    TeamForm,
    UserForm,
    UserRuleForm,
    assignable_groups,
    person_label,
    sees_emails,
)
from backoffice.nav import placed
from backoffice.views.common import paginate, search_text
from core import admin_log, autosave
from core.converters import as_id
from members import services as member_services
from members.models import MemberGroup, MemberGroupMembership
from teams import services as team_services
from teams.models import Team

PER_PAGE = 50

# One line per role on 「角色」 (design 4.1).
ROLE_SUMMARIES = {
    "内容编辑": (
        "改和发布所有文章、撤下别人的文章，改网站页面、文章分类、成员分组，"
        "看 AI 巡查记录、撤下头像、隐藏评论。"
    ),
    "认证作者": "写文章直接发布，能设文章网址、搜索描述和定时上线下线。",
    "赛事管理员": "建赛事、审核报名、编排队伍，能看报名者的联系方式。",
    "内战管理员": "建内战、勾选上场、调整分队，能看报名者的联系方式。",
    "投稿者": (
        "验证过邮箱的成员都在这一组，由系统维护：能进后台写文章、"
        "发布和撤下自己的文章、上传投稿图片。"
    ),
    "交大用户": "按「是否来自交大」自动分组，本身没有后台权限，用来按组关功能。",
    "校外用户": "按「是否来自交大」自动分组，本身没有后台权限，用来按组关功能。",
}
ROLE_ORDER = (*ASSIGNED_ROLES, "投稿者", "交大用户", "校外用户")


# --- users --------------------------------------------------------------------


@placed("members", "users", "users")
def user_list(request):
    users = User.objects.prefetch_related(
        Prefetch("groups", queryset=Group.objects.order_by("name"))
    ).order_by("-date_joined", "-pk")
    query = search_text(request)
    if query:
        users = users.filter(Q(nickname__icontains=query) | Q(email__icontains=query))
    role = request.GET.get("role") or ""
    if role:
        users = users.filter(groups__name=role)
    state = request.GET.get("state") or ""
    if state == "active":
        users = users.filter(is_active=True)
    elif state == "stopped":
        users = users.filter(is_active=False)
    sjtu = request.GET.get("sjtu") or ""
    if sjtu in ("1", "0"):
        users = users.filter(is_sjtu=sjtu == "1")
    page_obj, extra_query = paginate(request, users, PER_PAGE)
    return render(
        request,
        "backoffice/members/users.html",
        {
            "page_title": "用户",
            "page_obj": page_obj,
            "extra_query": extra_query,
            "query": query,
            "role": role,
            "roles": list(
                Group.objects.order_by("name").values_list("name", flat=True)
            ),
            "state": state,
            "sjtu": sjtu,
        },
    )


def _after_deactivation(request, user, paused) -> None:
    """As the Wagtail edit page did (design 3.7): applications cancelled,
    recruiting paused, a word about the teams this person captains. The
    state change itself is accounts.services.deactivate_account (213, A8);
    ``paused`` is what it returned."""
    from teams.services import captained_teams

    messages.info(request, "账号已停用：不能再登录，待审批的入队申请已取消。")
    teams = captained_teams(user)
    if teams:
        names = "、".join(f"「{team.name}」" for team in teams)
        messages.warning(
            request, f"这个账号是{names}的队长，到「成员 → 战队」给这些队指定新队长。"
        )
    if paused:
        names = "、".join(f"「{team.name}」" for team in paused)
        messages.info(
            request, f"{names}已改成暂不招募，新队长可以在战队管理页重新打开。"
        )


@placed("members", "users", "users")
def user_edit(request, pk):
    person = get_object_or_404(User, pk=pk)
    form = UserForm(request.POST or None, instance=person, editor=request.user)
    if autosave.wants(request):
        saved = autosave.save_valid_fields(form)
        if "roles" in autosave.valid_changes(form):
            form.save_roles()
            saved.append("roles")
        if saved:
            autosave.log_edit(form.instance, request.user)
        return autosave.respond(
            autosave.Outcome(saved=saved, errors=autosave.errors_of(form))
        )
    if request.method == "POST" and form.is_valid():
        person = form.save()
        form.save_roles()
        autosave.log_edit(person, request.user)
        messages.success(request, f"「{person.nickname}」已保存。")
        return redirect("backoffice:user_edit", person.pk)
    from accounts.services import admin_profile, is_deleted

    return render(
        request,
        "backoffice/members/user_edit.html",
        {
            "page_title": person.nickname or person.email,
            "form": form,
            "person": person,
            "person_deleted": is_deleted(person),
            "profile": admin_profile(person, viewer=request.user),
            "rules": person.feature_rules.select_related("updated_by"),
            "rule_form": UserRuleForm(user=person),
            "deactivate_form": DeactivateForm(),
            "own_account": person.pk == request.user.pk,
            "back_url": reverse("backoffice:users"),
            "back_label": "用户",
        },
    )


@placed("members", "users", "users")
@require_POST
def user_active(request, pk):
    """停用 and 启用 (design 3.7; v7.6 a button of their own, 13.17). Nobody
    switches their own account off from here. State changes go through
    accounts.services (213, A8)."""
    from accounts import services as account_services

    person = get_object_or_404(User, pk=pk)
    if person.pk == request.user.pk:
        messages.error(request, "不能在这里停用自己的账号。")
        return redirect("backoffice:user_edit", person.pk)
    if request.POST.get("action") == "start":
        if not person.is_active:
            try:
                account_services.reactivate_account(person)
            except account_services.AccountError as exc:
                messages.error(request, str(exc))
            else:
                admin_log.record(person, "users.reactivate", request.user)
                messages.success(request, f"「{person.nickname}」已重新启用。")
        return redirect("backoffice:user_edit", person.pk)
    form = DeactivateForm(request.POST)
    if not form.is_valid():
        messages.error(request, form.errors["deactivation_note"][0])
        return redirect("backoffice:user_edit", person.pk)
    if person.is_active:
        note = form.cleaned_data["deactivation_note"].strip()
        paused = account_services.deactivate_account(person, note=note)
        admin_log.record(person, "users.deactivate", request.user, note=note)
        _after_deactivation(request, person, paused)
    return redirect("backoffice:user_edit", person.pk)


@placed("members", "users", "users")
@require_POST
def user_rule_add(request, pk):
    person = get_object_or_404(User, pk=pk)
    form = UserRuleForm(request.POST, user=person)
    if form.is_valid():
        rule = form.save(commit=False)
        rule.updated_by = request.user
        rule.save()
        log(rule, "wagtail.create", user=request.user)
        messages.success(request, f"已加上规则：{rule.get_feature_display()}。")
    else:
        errors = [e for field in form.errors.values() for e in field]
        messages.error(request, errors[0] if errors else "规则没有保存。")
    return redirect("backoffice:user_edit", person.pk)


@placed("members", "users", "users")
@require_POST
def user_rule_delete(request, pk):
    rule = get_object_or_404(FeatureUserRule, pk=pk)
    log(rule, "wagtail.delete", user=request.user)
    rule.delete()
    messages.success(request, "规则已删除。")
    return redirect("backoffice:user_edit", rule.user_id)


# --- roles --------------------------------------------------------------------


@placed("members", "users", "roles")
def role_list(request):
    groups = Group.objects.annotate(
        people=Count("user", filter=Q(user__is_active=True))
    ).prefetch_related(
        Prefetch(
            "feature_restrictions",
            queryset=FeatureGroupRestriction.objects.select_related("updated_by"),
        )
    )
    order = {name: number for number, name in enumerate(ROLE_ORDER)}
    groups = sorted(groups, key=lambda g: (order.get(g.name, 99), g.name))
    return render(
        request,
        "backoffice/members/roles.html",
        {
            "page_title": "角色",
            "groups": [
                (
                    group,
                    ROLE_SUMMARIES.get(group.name, "自己建的分组，用来按组关功能。"),
                )
                for group in groups
            ],
            "restriction_form": GroupRestrictionForm(group=None),
            "assignable": set(assignable_groups()),
        },
    )


@placed("members", "users", "roles")
@require_POST
def role_restriction_add(request, pk):
    group = get_object_or_404(Group, pk=pk)
    form = GroupRestrictionForm(request.POST, group=group)
    if form.is_valid():
        restriction = form.save(commit=False)
        restriction.updated_by = request.user
        restriction.save()
        log(restriction, "wagtail.create", user=request.user)
        messages.success(
            request, f"「{group.name}」关掉了：{restriction.get_feature_display()}。"
        )
    else:
        errors = [e for field in form.errors.values() for e in field]
        messages.error(request, errors[0] if errors else "限制没有保存。")
    return redirect("backoffice:roles")


@placed("members", "users", "roles")
@require_POST
def role_restriction_delete(request, pk):
    restriction = get_object_or_404(FeatureGroupRestriction, pk=pk)
    log(restriction, "wagtail.delete", user=request.user)
    restriction.delete()
    messages.success(request, "限制已去掉。")
    return redirect("backoffice:roles")


# --- teams --------------------------------------------------------------------


def team_state(team, stuck: set[int]) -> tuple[str, str]:
    if team.is_disbanded:
        return "已解散", "off"
    if team.pk in stuck:
        return "队长已停用", "warn"
    return "正常", "ok"


@placed("members", "teams")
def team_list(request):
    teams = Team.objects.prefetch_related("memberships__user").order_by(
        "disbanded_at", "-created_at"
    )
    stuck = set(team_services.teams_without_captain().values_list("pk", flat=True))
    query = search_text(request)
    if query:
        teams = teams.filter(name__icontains=query)
    captain = request.GET.get("captain") or ""
    if captain == "gone":
        teams = teams.filter(pk__in=stuck)
    page_obj, extra_query = paginate(request, teams, PER_PAGE)
    return render(
        request,
        "backoffice/members/teams.html",
        {
            "page_title": "战队",
            "rows": [(team, team_state(team, stuck)) for team in page_obj],
            "page_obj": page_obj,
            "extra_query": extra_query,
            "query": query,
            "captain": captain,
        },
    )


@placed("members", "teams")
def team_edit(request, pk):
    team = get_object_or_404(Team, pk=pk)
    form = TeamForm(request.POST or None, instance=team, user=request.user)
    if autosave.wants(request):
        saved = autosave.save_valid_fields(form)
        if saved:
            autosave.log_edit(form.instance, request.user)
            team_services.on_team_changed(form.instance, author=request.user)
        return autosave.respond(
            autosave.Outcome(saved=saved, errors=autosave.errors_of(form))
        )
    if request.method == "POST" and form.is_valid():
        team = form.save()
        autosave.log_edit(team, request.user)
        # As the captain's own edit: pages and the AI patrol follow (7.1).
        team_services.on_team_changed(team, author=request.user)
        messages.success(request, f"战队「{team.name}」已保存。")
        return redirect("teams:edit", team.pk)
    stuck = set(team_services.teams_without_captain().values_list("pk", flat=True))
    team.refresh_from_db()
    return render(
        request,
        "backoffice/members/team_edit.html",
        {
            "page_title": team.name,
            "form": form,
            "team": team,
            "state": team_state(team, stuck),
            "memberships": team.memberships.select_related("user"),
            "back_url": reverse("teams:index"),
            "back_label": "战队",
        },
    )


# --- member groups ------------------------------------------------------------


def _group_may(request, action: str) -> None:
    """New and delete need more than the tab (change): placed checked that."""
    if not request.user.has_perm(f"members.{action}_membergroup"):
        raise PermissionDenied("没有这项分组权限。")


@placed("members", "groups")
def group_list(request):
    groups = MemberGroup.objects.annotate(people=Count("memberships"))
    return render(
        request,
        "backoffice/members/groups.html",
        {
            "page_title": "成员分组",
            "groups": groups,
            "can_add": request.user.has_perm("members.add_membergroup"),
        },
    )


@placed("members", "groups")
def group_edit(request, pk=None):
    group = get_object_or_404(MemberGroup, pk=pk) if pk else MemberGroup()
    if not pk:
        _group_may(request, "add")
    form = MemberGroupForm(request.POST or None, instance=group)
    if autosave.wants(request):
        return _group_autosave(request, form, created=not pk)
    if request.method == "POST" and form.is_valid():
        group = form.save()
        if pk:
            autosave.log_edit(group, request.user)
        else:
            log(group, "wagtail.create", user=request.user)
        messages.success(request, f"分组「{group.name or '未命名分组'}」已保存。")
        return redirect("backoffice:member_group_edit", group.pk)
    return render(
        request,
        "backoffice/members/group_edit.html",
        {
            "page_title": (group.name or "未命名分组") if pk else "新建分组",
            "form": form,
            "group": group if pk else None,
            **_people_context(request, group if pk else None),
            "can_delete": bool(pk)
            and request.user.has_perm("members.delete_membergroup"),
            "back_url": reverse("backoffice:member_groups"),
            "back_label": "成员分组",
        },
    )


def _people_context(request, group) -> dict:
    """组里的成员 (docs/admin.md 4.4, v7.7): who is in, and whom the search
    box found (?q= also works without the script)."""
    query = (request.GET.get("q") or "").strip()[:50]
    if group is None:
        return {"memberships": [], "query": "", "found": []}
    return {
        "memberships": list(
            group.memberships.select_related("user").order_by("sort_order", "pk")
        ),
        "query": query,
        "found": member_services.search_people(
            group, query, by_email=sees_emails(request.user)
        ),
        "sees_emails": sees_emails(request.user),
    }


def _people_html(request, group, problem: str = "") -> str:
    return render_to_string(
        "backoffice/members/_people.html",
        {"group": group, "problem": problem, **_people_context(request, group)},
        request=request,
    )


def _group_autosave(request, form, *, created: bool):
    """Design 13.17 (v7.6): the group exists from the first change (named or
    not; unnamed ones stay off /members/). A new one brings its people block
    along at once (v7.7), so people can be added without reloading. Fields
    with an error sit this save out, the rest still create it (212, B6)."""
    replace = {}
    if created:
        group, saved = autosave.new_from_valid_fields(form, MemberGroup())
        group.save()
        log(group, "wagtail.create", user=request.user)
        location = reverse("backoffice:member_group_edit", args=[group.pk])
        replace["[data-memberships]"] = _people_html(request, group)
    else:
        saved = autosave.save_valid_fields(form)
        group = form.instance
        location = ""
        if saved:
            autosave.log_edit(group, request.user)
    return autosave.respond(
        autosave.Outcome(
            saved=saved,
            errors=autosave.errors_of(form),
            location=location,
            replace=replace,
        )
    )


def _people_done(request, group, problem: str = "", note: str = ""):
    """After adding, moving or taking out someone: the block comes back
    whole for the script; without it, back to the page with a message."""
    if "application/json" in request.headers.get("Accept", ""):
        return JsonResponse(
            {
                "ok": not problem,
                "problem": problem,
                "replace": {
                    "[data-memberships]": _people_html(request, group, problem)
                },
            }
        )
    if problem:
        messages.error(request, problem)
    elif note:
        messages.success(request, note)
    return redirect("backoffice:member_group_edit", group.pk)


@placed("members", "groups")
def group_people(request, pk):
    """搜人 for the search box: joined people not in the group yet."""
    group = get_object_or_404(MemberGroup, pk=pk)
    found = member_services.search_people(
        group, request.GET.get("q", "")[:50], by_email=sees_emails(request.user)
    )
    return JsonResponse(
        {
            "results": [
                {"id": person.pk, "label": person_label(person, request.user)}
                for person in found
            ]
        }
    )


@placed("members", "groups")
@require_POST
def group_member_add(request, pk):
    group = get_object_or_404(MemberGroup, pk=pk)
    person = User.objects.filter(pk=as_id(request.POST.get("user"))).first()
    if person is None:
        return _people_done(request, group, "没有找到这个人。")
    try:
        member_services.add_member(group, person)
    except member_services.MembershipError as exc:
        return _people_done(request, group, str(exc))
    autosave.log_edit(group, request.user)
    return _people_done(request, group, note=f"已把「{person.nickname}」加进分组。")


def _membership(pk):
    return get_object_or_404(
        MemberGroupMembership.objects.select_related("group"), pk=pk
    )


@placed("members", "groups")
@require_POST
def group_member_remove(request, pk):
    membership = _membership(pk)
    group, name = membership.group, membership.user.nickname
    member_services.remove_member(membership)
    autosave.log_edit(group, request.user)
    return _people_done(request, group, note=f"已把「{name}」移出分组。")


@placed("members", "groups")
@require_POST
def group_member_move(request, pk):
    membership = _membership(pk)
    step = -1 if request.POST.get("direction") == "up" else 1
    member_services.move_member(membership, step)
    autosave.log_edit(membership.group, request.user)
    return _people_done(request, membership.group)


@placed("members", "groups")
@require_POST
def group_member_title(request, pk):
    """职务, one person at a time; saves itself (design 13.17)."""
    membership = _membership(pk)
    try:
        member_services.set_title(membership, request.POST.get("title", ""))
    except member_services.MembershipError as exc:
        if autosave.wants(request):
            return autosave.respond(autosave.Outcome(errors={"title": [str(exc)]}))
        messages.error(request, str(exc))
        return redirect("backoffice:member_group_edit", membership.group_id)
    autosave.log_edit(membership.group, request.user)
    if autosave.wants(request):
        return autosave.respond(autosave.Outcome(saved=["title"]))
    return redirect("backoffice:member_group_edit", membership.group_id)


@placed("members", "groups")
@require_POST
def group_delete(request, pk):
    _group_may(request, "delete")
    group = get_object_or_404(MemberGroup, pk=pk)
    name = group.name
    log(group, "wagtail.delete", user=request.user)
    group.delete()
    messages.success(request, f"分组「{name}」已删除。")
    return redirect("backoffice:member_groups")
