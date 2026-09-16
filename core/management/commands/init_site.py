from django.core.management.base import BaseCommand

from accounts.services import GROUP_EXTERNAL, GROUP_SJTU, ensure_user_groups


class Command(BaseCommand):
    help = (
        "Initialize groups, page tree, workflows, and default typography. "
        "This round creates the 交大用户 / 校外用户 groups; other roles wait for 005."
    )

    def handle(self, *args, **options):
        sjtu, external = ensure_user_groups()
        self.stdout.write(self.style.SUCCESS(f"已确保用户组存在：{sjtu.name}"))
        self.stdout.write(self.style.SUCCESS(f"已确保用户组存在：{external.name}"))
        later = [
            "用户组：内容编辑、赛事管理员、内战管理员、认证作者、投稿者，以及各自的权限",
            "页面树：首页、「资讯」栏目、用户协议和隐私政策占位页面",
            "「内容审核」工作流，并绑定到文章栏目",
            "「投稿图片」图片集合及权限",
            "初始游戏模式",
            "9 个排版区域的默认设置（全部使用系统字体），并生成初始字体样式表",
        ]
        self.stdout.write(
            self.style.NOTICE("以下内容仍等到后续里程碑写入（命令可重复执行）：")
        )
        for item in later:
            self.stdout.write(f"  - {item}")
        unused = (GROUP_SJTU, GROUP_EXTERNAL)
        self.stdout.write(
            self.style.NOTICE(
                "本轮只初始化 " + "、".join(unused) + "。其余角色组在 005 创建。"
            )
        )
