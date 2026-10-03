"""「上线清单」 on the dashboard, for superusers (round 122).

A fresh install works, but several things only the owner can do decide
whether people can actually use it: without SMTP nobody can register
(signing up needs a verified email), the agreement everyone ticks starts
empty, AI review needs a key in the environment. Each check says what is
missing and where to fix it; 「必做」 ones block real use, 「建议」 ones
make the site better.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.urls import reverse
from wagtail.admin.ui.components import Component

LEGAL_SLUGS = (("terms", "用户协议"), ("privacy", "隐私政策"))


@dataclass(frozen=True)
class Check:
    label: str
    done: bool
    detail: str  # what is missing, or what is in place
    url: str = ""
    required: bool = True


def _settings_url(site) -> str:
    return reverse("wagtailsettings:edit", args=["core", "sitesettings", site.pk])


def _page_text(page) -> str:
    return " ".join(str(block.value) for block in page.body) if page.body else ""


def _mail(site) -> Check:
    done = bool(site.smtp_host and site.from_address)
    return Check(
        "邮件（SMTP）",
        done,
        "已配置。改过之后在全站设置里点「发送测试邮件」确认能发出去。"
        if done
        else "还没配置。注册要验证邮箱，没有邮件就没有人能注册、找回密码。"
        "在全站设置里填 SMTP 服务器和发件地址，再点「发送测试邮件」。",
        _settings_url(site),
    )


def _ai(site) -> Check:
    from moderation import services

    if not services.is_configured():
        detail = (
            "服务器没有设置环境变量 MODERATION_API_KEY（或自建服务的 "
            "MODERATION_BASE_URL），AI 审核不会运行。写进 .env 后重启 web 和 worker。"
        )
    elif not site.moderation_enabled:
        detail = "密钥已设置，但全站设置里「启用 AI 内容审核」关着。"
    else:
        detail = "在运行。可以在「内容审核」页上点「试一下」确认能连上。"
    return Check(
        "AI 内容审核",
        services.is_enabled(),
        detail,
        reverse("moderation_index"),
        required=False,
    )


def _legal() -> list[Check]:
    from content.models import StandardPage

    checks = []
    for slug, title in LEGAL_SLUGS:
        page = StandardPage.objects.filter(slug=slug).first()
        if page is None:
            checks.append(Check(title, False, "页面不存在，先运行 init_site。"))
            continue
        text = _page_text(page)
        blanks = text.count("【")
        if not text.strip():
            detail = (
                "还没有正文，注册的人要勾选同意它。"
                "运行 load_legal_pages 填入草稿，再改。"
            )
        elif blanks:
            detail = (
                f"正文里还有 {blanks} 处【】要社团填写"
                "（运营方、联系方式、生效日期等）。"
            )
        else:
            detail = "已填写。"
        checks.append(
            Check(
                title,
                bool(text.strip()) and not blanks,
                detail,
                reverse("wagtailadmin_pages:edit", args=[page.pk]),
            )
        )
    return checks


def _about() -> Check:
    from content.models import StandardPage

    page = StandardPage.objects.filter(slug="about").first()
    text = _page_text(page) if page else ""
    return Check(
        "关于我们",
        bool(text.strip()),
        "已填写。"
        if text.strip()
        else "还是空的。页脚每页都链到它，写几句社团介绍和联系方式。",
        reverse("wagtailadmin_pages:edit", args=[page.pk]) if page else "",
        required=False,
    )


def _home(site) -> Check:
    missing = [
        label
        for label, value in (
            ("站点简介", site.site_description),
            ("QQ 群链接", site.qq_group_url),
            ("成立日期", site.founded_on),
            ("首屏图片", site.hero_image_id),
        )
        if not value
    ]
    return Check(
        "首页和分享信息",
        not missing,
        "已填写。"
        if not missing
        else "还没填："
        + "、".join(missing)
        + "。站点简介用在搜索结果和链接预览里，QQ 群链接是首页的「加入」按钮。",
        _settings_url(site),
        required=False,
    )


def _backup(site) -> Check:
    key = bool(getattr(settings, "BACKUP_ENCRYPTION_KEY", ""))
    done = bool(site.backup_s3_enabled and key)
    if done:
        detail = "每次备份后加密上传到对象存储。"
    elif not key:
        detail = (
            "备份只留在这台服务器上，服务器坏了就全没了。设置环境变量 "
            "BACKUP_ENCRYPTION_KEY，再在全站设置里填对象存储（设计 16.7）。"
        )
    else:
        detail = (
            "加密密钥已设置，全站设置里「备份上传到对象存储」还没开。"
            "填好对象存储后点「测试对象存储」，测通了再打开。"
        )
    return Check("异地备份", done, detail, _settings_url(site), required=False)


def _pictures() -> Check:
    from core import avatars, covers

    missing = [
        label
        for label, count in (
            ("默认封面", len(covers.load_pool())),
            ("默认头像", len(avatars.load_pool())),
        )
        if not count
    ]
    return Check(
        "默认封面和默认头像",
        not missing,
        "图库里有图。"
        if not missing
        else "「"
        + "」「".join(missing)
        + "」图库是空的，没有封面、头像的地方会显示占位图。"
        "在「图片」里上传到这两个集合（可以建子文件夹）。",
        reverse("wagtailimages:index"),
        required=False,
    )


def _roles() -> Check:
    from django.contrib.auth.models import Group

    from accounts.services import GROUP_CONTENT

    group = Group.objects.filter(name=GROUP_CONTENT).first()
    done = bool(group and group.user_set.filter(is_active=True).exists())
    return Check(
        "内容编辑",
        done,
        "已有人负责。"
        if done
        else "还没有人在「内容编辑」组。投稿审核、内容审核、头像审核"
        "都只有超级管理员能做。在「用户」里给社团干部加上这个组"
        "（赛事、内战管理员同理）。",
        reverse("wagtailusers_groups:index"),
        required=False,
    )


def _test_banner() -> Check:
    on = bool(getattr(settings, "TEST_ENVIRONMENT", False))
    return Check(
        "测试环境标记",
        not on,
        "页面顶部有「测试环境」横幅、禁止搜索引擎收录。正式上线前去掉 .env 里的 "
        "TEST_ENVIRONMENT 并重启。"
        if on
        else "已关闭。",
        required=False,
    )


def setup_checks() -> list[Check]:
    from core.models import SiteSettings

    site = SiteSettings.load()
    return [
        _mail(site),
        *_legal(),
        _ai(site),
        _backup(site),
        _roles(),
        _about(),
        _home(site),
        _pictures(),
        _test_banner(),
    ]


class SetupPanel(Component):
    name = "site_setup"
    template_name = "core/admin/setup_panel.html"
    order = 20

    def get_context_data(self, parent_context):
        checks = setup_checks()
        open_required = [check for check in checks if check.required and not check.done]
        open_optional = [
            check for check in checks if not check.required and not check.done
        ]
        return {
            "open_required": open_required,
            "open_optional": open_optional,
            "done": [check for check in checks if check.done],
        }
