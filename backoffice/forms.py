"""The back office's forms (docs/admin.md 4).

The rules are the ones the Wagtail forms had (docs/admin-inventory.md):
who sees which article fields, the tournament locks once people have signed
up, the stored secrets that are never shown again. Each form lists its
fields in ``FIELDSETS`` when the page draws them in groups.
"""

from __future__ import annotations

from django import forms
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.utils import timezone
from django.utils.text import slugify

from accounts.models import Feature, FeatureGroupRestriction, FeatureUserRule, User
from accounts.roles import ROLE_CHOICES, join_roles, parse_roles
from accounts.services import (
    GROUP_AUTHOR,
    GROUP_CONTENT,
    GROUP_EXTERNAL,
    GROUP_SCRIM,
    GROUP_SJTU,
    GROUP_SUBMITTER,
    GROUP_TOURNAMENT,
)
from backoffice.widgets import DateLocal, DateTimeLocal, image_field
from content.models import ArticleCategory, ArticlePage, StandardPage
from content.permissions import is_submitter_only, plain_writer, user_can_edit_author
from content.widgets import MarkdownEditor
from core.models import SiteSettings
from members.models import MemberGroup, MemberGroupMembership
from scrims.models import Scrim
from teams.models import Team
from tournaments.models import Tournament


class KeepSeconds:
    """The browser's date-and-time box holds minutes. A time stored with
    seconds (a copy, an import) comes back without them; keep the stored one
    then, or saving an untouched form would move the time and tell everyone
    taking part (design 8.1 「时间改了」)."""

    def _post_clean(self):
        for name, field in self.fields.items():
            if not isinstance(field, forms.DateTimeField):
                continue
            stored = getattr(self.instance, name, None) if self.instance.pk else None
            sent = self.cleaned_data.get(name)
            if stored and sent and sent == stored.replace(second=0, microsecond=0):
                self.cleaned_data[name] = stored
        super()._post_clean()


def _person_label(user) -> str:
    return f"{user.nickname}（{user.email}）"


class PersonChoiceField(forms.ModelChoiceField):
    """Nicknames repeat; pick 「昵称（邮箱）」."""

    def label_from_instance(self, obj):
        return _person_label(obj)


# --- articles (docs/admin.md 4.2) ------------------------------------------------

# What plain members do not set (v6.25, round 130): the address, the search
# text and the schedule. Left out rather than hidden, so saving again keeps
# what an editor set.
EDITOR_ONLY_FIELDS = (
    "slug",
    "seo_title",
    "search_description",
    "go_live_at",
    "expire_at",
)


class ArticleForm(KeepSeconds, forms.ModelForm):
    FIELDSETS = (
        ("文章", ("title", "category", "cover", "summary", "body", "tournament")),
        ("作者和评论", ("author", "comments_enabled")),
        (
            "网址和发布时间",
            ("slug", "seo_title", "search_description", "go_live_at", "expire_at"),
        ),
    )

    class Meta:
        model = ArticlePage
        fields = (
            "title",
            "category",
            "cover",
            "summary",
            "body",
            "tournament",
            "author",
            "comments_enabled",
            "slug",
            "seo_title",
            "search_description",
            "go_live_at",
            "expire_at",
        )
        widgets = {
            "body": MarkdownEditor,
            "go_live_at": DateTimeLocal,
            "expire_at": DateTimeLocal,
            "search_description": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "slug": "网址片段",
            "seo_title": "搜索结果里的标题",
            "search_description": "搜索描述",
            "go_live_at": "定时上线",
            "expire_at": "定时下线",
        }
        help_texts = {
            "slug": "文章地址的最后一段。空着就按标题生成。",
            "seo_title": "空着就用文章标题。",
            "search_description": "空着就用摘要。",
            "go_live_at": "到这个时间才上线。点「发布」后生效；空着就是马上上线。",
            "expire_at": "到这个时间自动下线。",
        }

    def __init__(self, *args, user, parent, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.parent = parent
        self._original_slug = self.instance.slug
        self.fields["title"].label = "标题"
        self.fields["title"].help_text = ""
        self.fields["category"].empty_label = "选一个分类"
        # Unnamed categories (being set up, v7.6) are not offered.
        self.fields["category"].queryset = ArticleCategory.objects.named()
        self.fields["tournament"].empty_label = "不关联赛事"
        self.fields["cover"] = image_field(
            user,
            label="封面",
            current=self.instance.cover_id,
            help_text="空着就用默认封面图库里的一张。",
        )
        self.fields["tournament"].queryset = Tournament.objects.order_by("-pk")
        if "author" in self.fields:
            self.fields["author"] = PersonChoiceField(
                queryset=User.objects.filter(is_active=True).order_by("nickname"),
                label="作者",
                required=False,
                help_text="空着就是写这篇的人。",
            )
        if not user_can_edit_author(user):
            self.fields.pop("author")
        if is_submitter_only(user):
            self.fields.pop("comments_enabled")
            self.fields["category"].queryset = ArticleCategory.objects.named().filter(
                allow_submission=True
            )
        if plain_writer(user):
            for name in EDITOR_ONLY_FIELDS:
                self.fields.pop(name, None)
        if "slug" in self.fields:
            self.fields["slug"].required = False

    def fieldsets(self):
        for legend, names in self.FIELDSETS:
            fields = [self[name] for name in names if name in self.fields]
            if fields:
                yield legend, fields

    def clean_slug(self):
        slug = (self.cleaned_data.get("slug") or "").strip()
        if not slug:
            return ""
        from wagtail.models import Page

        if not Page._slug_is_available(slug, self.parent, self.instance):
            raise ValidationError("这个网址片段已经有文章在用了，换一个。")
        return slug

    def clean(self):
        cleaned = super().clean()
        go_live, expire = cleaned.get("go_live_at"), cleaned.get("expire_at")
        if go_live and expire and go_live >= expire:
            self.add_error("expire_at", "下线时间要晚于上线时间。")
        if expire and expire <= timezone.now() and "expire_at" in self.changed_data:
            self.add_error("expire_at", "下线时间要在将来。")
        return cleaned

    def _free_slug(self, title: str) -> str:
        """The address from the title, stepped round the reserved words and
        the articles already there (as the Wagtail form did, round 130)."""
        from wagtail.models import Page

        from content.models import RESERVED_CHILD_SLUGS

        base = slugify(title, allow_unicode=True)[:60] or "article"
        if base.lower() in RESERVED_CHILD_SLUGS:
            base = f"{base}-article"
        candidate, number = base, 1
        while not Page._slug_is_available(candidate, self.parent, self.instance):
            number += 1
            candidate = f"{base}-{number}"
        return candidate

    def save(self, commit=True):
        page = super().save(commit=False)
        # Wagtail's full_clean fills an empty slug from the title without
        # knowing the parent of a new page; ours steps round the reserved
        # words and the siblings. A plain member's form has no slug and
        # keeps the one the page already has.
        keep = "slug" not in self.fields and self._original_slug
        if not keep and not self.cleaned_data.get("slug"):
            page.slug = self._free_slug(page.title or "")
        if not page.author_id:
            page.author = page.owner if page.owner_id else self.user
        if not page.owner_id:
            page.owner = self.user
        if commit:
            page.save()
        return page


class StandardPageForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].help_text = ""

    class Meta:
        model = StandardPage
        fields = ("title", "body", "seo_title", "search_description")
        widgets = {
            "body": MarkdownEditor,
            "search_description": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "title": "标题",
            "seo_title": "搜索结果里的标题",
            "search_description": "搜索描述",
        }
        help_texts = {"seo_title": "空着就用页面标题。"}


class IndexIntroForm(forms.Form):
    intro = forms.CharField(
        label="栏目介绍",
        required=False,
        widget=MarkdownEditor(attrs={"rows": 8}),
        help_text="显示在资讯栏目顶部。保存后马上生效。",
    )


class PinnedArticlesForm(forms.Form):
    """首页的置顶文章: at most three, in order (design 5.2)."""

    SLOTS = 3

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        live = ArticlePage.objects.live().order_by("-first_published_at")
        for number in range(1, self.SLOTS + 1):
            self.fields[f"article_{number}"] = forms.ModelChoiceField(
                queryset=live,
                required=False,
                label=f"第 {number} 篇",
                empty_label="（不置顶）",
            )

    def clean(self):
        cleaned = super().clean()
        chosen = [cleaned.get(f"article_{n}") for n in range(1, self.SLOTS + 1)]
        picked = [article.pk for article in chosen if article is not None]
        if len(picked) != len(set(picked)):
            raise ValidationError("同一篇文章只能置顶一次。")
        cleaned["articles"] = [article for article in chosen if article is not None]
        return cleaned


class CategoryForm(forms.ModelForm):
    # Only the address is checked across categories (unique once filled in).
    autosave_together = ("slug",)

    class Meta:
        model = ArticleCategory
        fields = ("name", "slug", "sort_order", "allow_submission")
        help_texts = {
            "name": "名称或网址片段空着时，网站上不出现这个分类。",
            "slug": "资讯栏目按分类筛选时地址里用的词，只用字母、数字和连字符。",
            "sort_order": "数字小的排在前面。",
            "allow_submission": "关掉后普通成员写文章时不能选这个分类。",
        }

    def clean_slug(self) -> str:
        slug = (self.cleaned_data.get("slug") or "").strip()
        taken = ArticleCategory.objects.filter(slug=slug).exclude(pk=self.instance.pk)
        if slug and taken.exists():
            raise forms.ValidationError("这个网址片段已经有分类在用了。")
        return slug


# --- pictures (docs/admin.md 4.2) ---------------------------------------------------


def collections_for(user, action: str):
    from wagtail.images import get_image_model
    from wagtail.models import Collection
    from wagtail.permissions import policy_registry

    if user.is_superuser:
        return Collection.objects.all()
    policy = policy_registry.get_by_type(get_image_model())
    return policy.collections_user_has_permission_for(user, action)


class CollectionChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        depth = max(obj.depth - 2, 0)
        return ("　" * depth) + obj.name if obj.depth > 1 else "（根）"


class ImageEditForm(forms.Form):
    title = forms.CharField(label="标题", max_length=255)
    collection = CollectionChoiceField(queryset=None, label="集合", empty_label=None)

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["collection"].queryset = collections_for(user, "add").order_by(
            "path"
        )


class ImageUploadForm(forms.Form):
    collection = CollectionChoiceField(
        queryset=None, label="放进集合", empty_label=None
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["collection"].queryset = collections_for(user, "add").order_by(
            "path"
        )


class CollectionForm(forms.Form):
    name = forms.CharField(label="名称", max_length=255)
    parent = CollectionChoiceField(queryset=None, label="放在", empty_label=None)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from wagtail.models import Collection

        self.fields["parent"].queryset = Collection.objects.order_by("path")


# --- tournaments and scrims (docs/admin.md 4.3) -------------------------------


class TournamentForm(KeepSeconds, forms.ModelForm):
    """Design 8.1: 「报名自动通过」 and 「报名方式」 lock once anyone has signed
    up; a team tournament's minimum cannot pass the site's team size."""

    FIELDSETS = (
        ("内容", ("title", "summary", "description", "cover")),
        ("时间", ("starts_at", "registration_opens_at", "registration_closes_at")),
        (
            "报名规则",
            (
                "registration_mode",
                "roster_min",
                "roster_max",
                "sjtu_only",
                "auto_approve",
            ),
        ),
        ("通知", ("participant_contact",)),
    )

    class Meta:
        model = Tournament
        fields = (
            "title",
            "summary",
            "description",
            "cover",
            "starts_at",
            "registration_opens_at",
            "registration_closes_at",
            "registration_mode",
            "roster_min",
            "roster_max",
            "sjtu_only",
            "auto_approve",
            "participant_contact",
        )
        widgets = {
            "description": MarkdownEditor,
            "summary": forms.Textarea(attrs={"rows": 2}),
            "starts_at": DateTimeLocal,
            "registration_opens_at": DateTimeLocal,
            "registration_closes_at": DateTimeLocal,
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        from tournaments import services

        self.fields["cover"] = image_field(
            user, label="封面", current=self.instance.cover_id
        )
        cap = services.team_max_members()
        self.fields["roster_min"].help_text = (
            f"整队报名时不能超过全站战队人数上限（现在是 {cap} 人，"
            "在全站设置里改），否则没有战队能报名。个人报名不受这条限制。"
        )

    fieldsets = ArticleForm.fieldsets

    def clean(self):
        from tournaments import services

        cleaned = super().clean()
        # Round 119: on the field before saving; only when these change, so
        # lowering the site cap later does not block unrelated edits.
        touched = {"roster_min", "registration_mode"} & set(self.changed_data)
        if (
            (touched or not self.instance.pk)
            and cleaned.get("roster_min")
            and cleaned.get("registration_mode")
        ):
            probe = Tournament(
                roster_min=cleaned["roster_min"],
                registration_mode=cleaned["registration_mode"],
            )
            warning = services.roster_min_warning(probe)
            if warning:
                self.add_error("roster_min", warning)
        if not self.instance.pk:
            return cleaned
        if "auto_approve" in self.changed_data and services.has_registrations(
            self.instance
        ):
            self.add_error("auto_approve", "已经有报名了，不能再改「报名自动通过」。")
        if "registration_mode" in self.changed_data and services.has_entries(
            self.instance
        ):
            self.add_error(
                "registration_mode", "已经有人报名了，不能再改「报名方式」。"
            )
        return cleaned


class ScrimForm(KeepSeconds, forms.ModelForm):
    FIELDSETS = (
        ("内容", ("title", "description")),
        ("时间", ("starts_at", "signup_closes_at")),
        ("规则", ("format", "sjtu_only")),
    )

    class Meta:
        model = Scrim
        fields = (
            "title",
            "description",
            "starts_at",
            "signup_closes_at",
            "format",
            "sjtu_only",
        )
        widgets = {
            "description": MarkdownEditor,
            "starts_at": DateTimeLocal,
            "signup_closes_at": DateTimeLocal,
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

    fieldsets = ArticleForm.fieldsets


# --- people (docs/admin.md 4.4) -----------------------------------------------------

# The roles a superuser hands out here, first in this order, then any group
# made by hand (design 4.2); 投稿者, 交大用户 and 校外用户 follow from the
# account itself (design 4.1).
ASSIGNED_ROLES = (GROUP_CONTENT, GROUP_AUTHOR, GROUP_TOURNAMENT, GROUP_SCRIM)
SYSTEM_GROUPS = (GROUP_SUBMITTER, GROUP_SJTU, GROUP_EXTERNAL)


def assignable_groups() -> list[str]:
    names = list(
        Group.objects.exclude(name__in=SYSTEM_GROUPS).values_list("name", flat=True)
    )
    first = [name for name in ASSIGNED_ROLES if name in names]
    return first + sorted(name for name in names if name not in ASSIGNED_ROLES)


class UserForm(forms.ModelForm):
    roles = forms.MultipleChoiceField(
        label="角色",
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="投稿者、交大用户、校外用户由系统按账号情况维护，不在这里改。",
    )

    class Meta:
        model = User
        fields = ("nickname", "is_sjtu")

    def __init__(self, *args, editor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.groups = assignable_groups()
        self.fields["roles"].choices = [(name, name) for name in self.groups]
        if self.instance.pk:
            self.initial["roles"] = list(
                self.instance.groups.filter(name__in=self.groups).values_list(
                    "name", flat=True
                )
            )

    def save_roles(self) -> None:
        wanted = set(self.cleaned_data.get("roles") or [])
        for group in Group.objects.filter(name__in=self.groups):
            if group.name in wanted:
                self.instance.groups.add(group)
            else:
                self.instance.groups.remove(group)


class DeactivateForm(forms.Form):
    """停用 is its own button (design 13.17, v7.6): it cannot be undone in
    its effects (applications cancelled, recruiting paused), so it is not
    something to save while typing. The reason is for admins only (3.7)."""

    deactivation_note = forms.CharField(
        label="停用原因",
        max_length=200,
        help_text="只有管理员能看到（设计 3.7）。",
        error_messages={"required": "停用账号要写原因。"},
    )


class UserRuleForm(forms.ModelForm):
    class Meta:
        model = FeatureUserRule
        fields = ("feature", "allowed", "note")
        widgets = {
            "feature": forms.Select(attrs={"class": "c-input", "aria-label": "功能"}),
            "allowed": forms.Select(
                choices=[(False, "单独禁止"), (True, "单独允许")],
                attrs={"class": "c-input", "aria-label": "规则"},
            ),
        }
        labels = {"allowed": "规则"}

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.user = user
        self.fields["feature"].choices = [("", "选一项功能"), *Feature.choices]

    def clean_allowed(self):
        value = self.cleaned_data.get("allowed")
        return value in (True, "True", "true", "1")

    def clean_feature(self):
        feature = self.cleaned_data.get("feature")
        taken = FeatureUserRule.objects.filter(user=self.instance.user, feature=feature)
        if feature and taken.exists():
            raise ValidationError("这项功能已经有单独规则了，先删掉旧的再加。")
        return feature


class GroupRestrictionForm(forms.ModelForm):
    class Meta:
        model = FeatureGroupRestriction
        fields = ("feature", "note")

    def __init__(self, *args, group, **kwargs):
        super().__init__(*args, **kwargs)
        self.group = group
        self.fields["feature"].choices = [("", "选一项功能"), *Feature.choices]

    def clean_feature(self):
        feature = self.cleaned_data.get("feature")
        taken = FeatureGroupRestriction.objects.filter(
            group=self.group, feature=feature
        )
        if feature and taken.exists():
            raise ValidationError("这一组的这项功能已经关掉了。")
        return feature

    def save(self, commit=True):
        self.instance.group = self.group
        return super().save(commit=commit)


class TeamForm(forms.ModelForm):
    """缺的位置 as boxes, as on the captain's page (design-details 5.2)."""

    recruiting_roles = forms.MultipleChoiceField(
        label="缺的位置",
        choices=ROLE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="招募中时显示在战队卡和战队主页上。都不勾表示哪个位置都要。",
    )

    # A clashing name is the only rule across rows; the rest still saves.
    autosave_together = ("name",)

    class Meta:
        model = Team
        fields = ("name", "description", "logo", "is_recruiting", "recruiting_roles")

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["logo"] = image_field(
            user, label="队标", current=self.instance.logo_id
        )
        if self.instance.pk:
            self.initial["recruiting_roles"] = parse_roles(
                self.instance.recruiting_roles
            )

    def clean_name(self) -> str:
        """The rule the database keeps for teams still active; the form
        cannot see it (it names a field the form leaves out), so a clash
        used to end in a server error."""
        from teams.services import NAME_TAKEN, name_taken

        name = (self.cleaned_data.get("name") or "").strip()
        if name and name_taken(name, exclude_pk=self.instance.pk):
            raise forms.ValidationError(NAME_TAKEN)
        return name

    def clean_recruiting_roles(self) -> str:
        return join_roles(self.cleaned_data.get("recruiting_roles") or [])


class MemberGroupForm(forms.ModelForm):
    # A clashing name is the only rule across rows; the rest still saves.
    autosave_together = ("name",)

    class Meta:
        model = MemberGroup
        fields = ("name", "description", "is_visible", "sort_order")
        help_texts = {"name": "名称空着时成员展示页上不出现这个分组。"}


class MembershipForm(forms.ModelForm):
    class Meta:
        model = MemberGroupMembership
        fields = ("user", "title")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = User.objects.filter(is_active=True).order_by(
            "nickname"
        )
        self.fields["title"].help_text = ""


class MembershipFormSet(BaseInlineFormSet):
    """组里的成员, one row each; 组内顺序 is Django's ORDER field (the model's
    sort_order is not editable), written back by ``save_in_order``."""

    def add_fields(self, form, index):
        super().add_fields(form, index)
        if "ORDER" in form.fields:
            form.fields["ORDER"].label = "组内顺序"
            form.fields["ORDER"].required = False

    def save_in_order(self, group) -> None:
        self.save(commit=False)
        for membership in self.deleted_objects:
            membership.delete()
        for number, form in enumerate(self.ordered_forms):
            membership = form.instance
            membership.group = group
            membership.sort_order = number
            membership.save()


def membership_formset():
    return inlineformset_factory(
        MemberGroup,
        MemberGroupMembership,
        form=MembershipForm,
        formset=MembershipFormSet,
        fk_name="group",
        extra=1,
        can_delete=True,
        can_order=True,
    )


# --- site settings (docs/admin.md 4.6) ------------------------------------------------

SITE_FIELDSETS = (
    (
        "站点信息",
        (
            "site_description",
            "default_share_image",
            "hero_image",
            "founded_on",
            "qq_group_url",
        ),
    ),
    (
        "栏目横幅",
        (
            "banner_news",
            "banner_tournaments",
            "banner_scrims",
            "banner_teams",
            "banner_members",
        ),
    ),
    (
        "社区参数",
        (
            "team_max_members",
            "team_max_captained",
            "max_game_accounts",
            "scrim_reminder_hours",
            "tournament_reminder_hours",
        ),
    ),
    (
        "邮件发送",
        (
            "smtp_host",
            "smtp_port",
            "smtp_security",
            "smtp_username",
            "smtp_password",
            "from_address",
            "from_name",
            "email_subject_prefix",
        ),
    ),
    (
        "AI 审核",
        (
            "moderation_enabled",
            "moderation_api_key",
            "moderation_base_url",
            "moderation_model",
            "moderation_alert_email",
            "moderation_daily_limit",
            "moderation_image_enabled",
            "moderation_extra_body",
            "moderation_timeout",
            "moderation_max_output_tokens",
        ),
    ),
    (
        "异地备份（对象存储）",
        (
            "backup_s3_enabled",
            "backup_s3_endpoint",
            "backup_s3_bucket",
            "backup_s3_region",
            "backup_s3_access_key_id",
            "backup_s3_secret_access_key",
            "backup_s3_prefix",
        ),
    ),
)
SITE_IMAGES = (
    "default_share_image",
    "hero_image",
    "banner_news",
    "banner_tournaments",
    "banner_scrims",
    "banner_teams",
    "banner_members",
)


class SiteSettingsForm(forms.ModelForm):
    """Every setting in one page; the stored secrets (SMTP, object storage, the
    AI's key) are never shown and a blank box keeps them (core.forms)."""

    FIELDSETS = SITE_FIELDSETS

    class Meta:
        model = SiteSettings
        fields = [name for _legend, names in SITE_FIELDSETS for name in names]
        widgets = {
            "founded_on": DateLocal,
            "site_description": forms.Textarea(attrs={"rows": 3}),
            "moderation_extra_body": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user, **kwargs):
        from core.forms import SECRET_FIELDS, _secret_field

        super().__init__(*args, **kwargs)
        for name in SITE_IMAGES:
            model_field = self._meta.model._meta.get_field(name)
            self.fields[name] = image_field(
                user,
                label=model_field.verbose_name,
                help_text=model_field.help_text,
                current=getattr(self.instance, f"{name}_id", None),
            )
        for name, (label, help_text) in SECRET_FIELDS.items():
            stored = bool(self.instance.pk and getattr(self.instance, name))
            self.fields[name] = _secret_field(
                label, help_text + ("现在：已保存。" if stored else "现在：还没有。")
            )
            self.initial[name] = ""

    fieldsets = ArticleForm.fieldsets

    def clean_smtp_password(self):
        from core.forms import kept_secret

        return kept_secret(self, "smtp_password")

    def clean_backup_s3_secret_access_key(self):
        from core.forms import kept_secret

        return kept_secret(self, "backup_s3_secret_access_key")

    def clean_moderation_api_key(self):
        from core.forms import kept_secret

        return kept_secret(self, "moderation_api_key")

    def clean_moderation_extra_body(self):
        from core.forms import cleaned_extra_body

        return cleaned_extra_body(self)


# --- the log (docs/admin.md 4.6) ----------------------------------------------


class LogFilterForm(forms.Form):
    action = forms.ChoiceField(label="动作", required=False)
    since = forms.DateField(label="从", required=False, widget=DateLocal)
    until = forms.DateField(label="到", required=False, widget=DateLocal)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from wagtail.log_actions import registry

        self.fields["action"].choices = [("", "全部动作"), *registry.get_choices()]
