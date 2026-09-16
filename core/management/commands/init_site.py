from django.core.management.base import BaseCommand

from accounts.services import (
    ALL_PRESET_GROUPS,
    assign_round_permissions,
    ensure_preset_groups,
)
from content.services import (
    ensure_article_categories,
    ensure_page_tree,
    remove_wagtail_stock_groups,
)


class Command(BaseCommand):
    help = (
        "Initialize groups, page tree, workflows, and default typography. "
        "This round creates preset groups, article categories, and the page tree."
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

        later = [
            "「内容审核」工作流，并绑定到文章栏目",
            "「投稿图片」图片集合及权限",
            "内容编辑 / 认证作者 / 投稿者的文章与审核权限（M2 投稿轮）",
            "投稿者组的自动成员同步（M2 投稿轮）",
            "赛事管理员的赛事管理权限（M4）",
            "内战管理员的内战管理权限（M6）",
            "初始游戏模式",
            "9 个排版区域的默认设置（全部使用系统字体），并生成初始字体样式表",
        ]
        self.stdout.write(
            self.style.NOTICE("以下内容仍等到后续里程碑写入（命令可重复执行）：")
        )
        for item in later:
            self.stdout.write(f"  - {item}")
        self.stdout.write(
            self.style.NOTICE(
                "不会改写已有用户组成员关系；重复执行只会确保组、分类和页面树存在。"
            )
        )
