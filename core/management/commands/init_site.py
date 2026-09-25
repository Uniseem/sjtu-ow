from django.core.management.base import BaseCommand

from accounts.services import (
    ALL_PRESET_GROUPS,
    assign_round_permissions,
    ensure_preset_groups,
    sync_all_submitter_memberships,
)
from comments.services import assign_comment_permissions
from content.services import (
    assign_content_permissions,
    ensure_article_categories,
    ensure_content_workflow,
    ensure_page_tree,
    ensure_submission_image_collection,
    remove_wagtail_stock_groups,
    sync_default_site_from_site_url,
)
from core.fonts.css import regenerate_font_css
from core.fonts.services import ensure_typography_rules
from members.services import assign_member_permissions
from moderation.services import assign_moderation_permissions
from scrims.services import assign_scrim_permissions
from tournaments.services import assign_tournament_permissions


class Command(BaseCommand):
    help = (
        "Initialize groups, page tree, the content-review workflow, "
        "and the submission image collection."
    )

    def handle(self, *args, **options):
        groups = ensure_preset_groups()
        assign_round_permissions()
        for name in ALL_PRESET_GROUPS:
            group = groups[name]
            self.stdout.write(self.style.SUCCESS(f"已确保用户组存在：{group.name}"))
        self.stdout.write(
            self.style.SUCCESS(
                "已分配本轮权限：后台角色可进入 Wagtail；"
                "赛事管理员和内战管理员可查看联系方式。"
            )
        )

        removed = remove_wagtail_stock_groups()
        if removed:
            self.stdout.write(
                self.style.SUCCESS("已删除 Wagtail 自带用户组：" + "、".join(removed))
            )
        else:
            self.stdout.write(
                "Wagtail 自带的 Editors / Moderators 组不存在，无需删除。"
            )

        categories = ensure_article_categories()
        self.stdout.write(
            self.style.SUCCESS(
                "已确保文章分类："
                + "、".join(f"{item.name}（{item.slug}）" for item in categories)
            )
        )

        homepage = ensure_page_tree()
        self.stdout.write(
            self.style.SUCCESS(
                f"已确保页面树：{homepage.title}、资讯、用户协议、隐私政策、关于我们"
            )
        )

        site = sync_default_site_from_site_url()
        self.stdout.write(
            self.style.SUCCESS(f"已按 SITE_URL 设置站点：{site.hostname}:{site.port}")
        )

        collection = ensure_submission_image_collection()
        self.stdout.write(self.style.SUCCESS(f"已确保图片集合：{collection.name}"))

        workflow = ensure_content_workflow()
        self.stdout.write(
            self.style.SUCCESS(f"已确保工作流：{workflow.name}（绑定到文章栏目）")
        )

        assign_content_permissions()
        self.stdout.write(
            self.style.SUCCESS(
                "已分配内容权限：投稿者可新建稿件并上传投稿图片；"
                "内容编辑可审核发布；认证作者可直接发布。"
            )
        )

        managers = assign_tournament_permissions()
        if managers:
            self.stdout.write(
                self.style.SUCCESS(
                    "已分配赛事权限：" + "、".join(managers) + " 可创建和编辑赛事"
                )
            )

        scrim_managers = assign_scrim_permissions()
        if scrim_managers:
            self.stdout.write(
                self.style.SUCCESS(
                    "已分配内战权限："
                    + "、".join(scrim_managers)
                    + " 可创建内战、勾选上场、调整分队"
                )
            )

        reviewers = assign_moderation_permissions()
        if reviewers:
            self.stdout.write(
                self.style.SUCCESS(
                    "已分配内容审核权限：" + "、".join(reviewers) + " 可复核 AI 标记"
                )
            )

        comment_editors = assign_comment_permissions()
        if comment_editors:
            self.stdout.write(
                self.style.SUCCESS(
                    "已分配评论权限："
                    + "、".join(comment_editors)
                    + " 可隐藏和置顶评论"
                )
            )

        member_editors = assign_member_permissions()
        if member_editors:
            self.stdout.write(
                self.style.SUCCESS(
                    "已分配成员分组权限："
                    + "、".join(member_editors)
                    + " 可管理成员分组"
                )
            )

        rules = ensure_typography_rules()
        font_css_url = regenerate_font_css()
        self.stdout.write(
            self.style.SUCCESS(
                f"已确保 {len(rules)} 个排版区域（默认系统字体），"
                f"字体样式表：{font_css_url}"
            )
        )

        changed = sync_all_submitter_memberships()
        self.stdout.write(
            self.style.SUCCESS(f"已同步投稿者组成员（本轮变更 {changed} 人）")
        )

        self.stdout.write(
            self.style.NOTICE(
                "不会改写已有用户组成员关系（投稿者组除外，由系统按验证邮箱"
                "和投稿功能权限自动维护）；重复执行只会确保组、分类、页面树、"
                "工作流和权限存在。"
            )
        )
