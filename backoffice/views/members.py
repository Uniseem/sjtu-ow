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
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from wagtail.log_actions import log

from accounts.models import FeatureGroupRestriction, FeatureUserRule, User
from backoffice import access
from backoffice.forms import (
    ASSIGNED_ROLES,
    GroupRestrictionForm,
    MemberGroupForm,
    TeamForm,
    UserForm,
    UserRuleForm,
    assignable_groups,
    membership_formset,
)
from backoffice.nav import placed
from backoffice.views.common import paginate, search_text
from members.models import MemberGroup
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


def _superuser(request) -> None:
    if not request.user.is_superuser:
        raise PermissionDenied("这一页只有超级管理员能用。")


# --- users --------------------------------------------------------------------


@placed("members", "users", "users")
def user_list(request):
    _superuser(request)
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


def _after_deactivation(request, user) -> None:
    """As the Wagtail edit page did (design 3.7): applications cancelled,
    recruiting paused, a word about the teams this person captains."""
    from accounts.services import after_deactivation
    from teams.services import captained_teams

    paused = after_deactivation(user)
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
    _superuser(request)
    person = get_object_or_404(User, pk=pk)
    was_active = person.is_active
    form = UserForm(request.POST or None, instance=person, editor=request.user)
    if request.method == "POST" and form.is_valid():
        person = form.save()
        form.save_roles()
        log(person, "wagtail.edit", user=request.user)
        messages.success(request, f"「{person.nickname}」已保存。")
        if was_active and not person.is_active:
            _after_deactivation(request, person)
        return redirect("backoffice:user_edit", person.pk)
    from accounts.services import admin_profile

    return render(
        request,
        "backoffice/members/user_edit.html",
        {
            "page_title": person.nickname or person.email,
            "form": form,
            "person": person,
            "profile": admin_profile(person, viewer=request.user),
            "rules": person.feature_rules.select_related("updated_by"),
            "rule_form": UserRuleForm(user=person),
            "back_url": reverse("backoffice:users"),
            "back_label": "用户",
        },
    )


@placed("members", "users", "users")
@require_POST
def user_rule_add(request, pk):
    _superuser(request)
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
    _superuser(request)
    rule = get_object_or_404(FeatureUserRule, pk=pk)
    log(rule, "wagtail.delete", user=request.user)
    rule.delete()
    messages.success(request, "规则已删除。")
    return redirect("backoffice:user_edit", rule.user_id)


# --- roles --------------------------------------------------------------------


@placed("members", "users", "roles")
def role_list(request):
    _superuser(request)
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
    _superuser(request)
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
    _superuser(request)
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
    _superuser(request)
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
    _superuser(request)
    team = get_object_or_404(Team, pk=pk)
    form = TeamForm(request.POST or None, instance=team, user=request.user)
    if request.method == "POST" and form.is_valid():
        team = form.save()
        log(team, "wagtail.edit", user=request.user)
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


def _group_editor(request, action: str = "change") -> None:
    if not access.edits_member_groups(request.user):
        raise PermissionDenied("成员分组只有内容编辑能改。")
    if not request.user.has_perm(f"members.{action}_membergroup"):
        raise PermissionDenied("没有这项分组权限。")


@placed("members", "groups")
def group_list(request):
    _group_editor(request)
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
    _group_editor(request, "change" if pk else "add")
    Formset = membership_formset()
    form = MemberGroupForm(request.POST or None, instance=group)
    formset = Formset(request.POST or None, instance=group, prefix="members")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        group = form.save()
        formset.instance = group
        formset.save_in_order(group)
        log(group, "wagtail.edit" if pk else "wagtail.create", user=request.user)
        messages.success(request, f"分组「{group.name}」已保存。")
        return redirect("backoffice:member_group_edit", group.pk)
    return render(
        request,
        "backoffice/members/group_edit.html",
        {
            "page_title": group.name if pk else "新建分组",
            "form": form,
            "formset": formset,
            "group": group if pk else None,
            "can_delete": bool(pk)
            and request.user.has_perm("members.delete_membergroup"),
            "back_url": reverse("backoffice:member_groups"),
            "back_label": "成员分组",
        },
    )


@placed("members", "groups")
@require_POST
def group_delete(request, pk):
    _group_editor(request, "delete")
    group = get_object_or_404(MemberGroup, pk=pk)
    name = group.name
    log(group, "wagtail.delete", user=request.user)
    group.delete()
    messages.success(request, f"分组「{name}」已删除。")
    return redirect("backoffice:member_groups")
