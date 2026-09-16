from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Initialize groups, page tree, workflows, and default typography. "
        "M0 only prints the planned work; writes start in M1/M2."
    )

    def handle(self, *args, **options):
        planned = [
            "用户组：内容编辑、赛事管理员、内战管理员、认证作者、投稿者、交大用户、校外用户，以及各自的权限",
            "页面树：首页、「资讯」栏目、用户协议和隐私政策占位页面",
            "「内容审核」工作流，并绑定到文章栏目",
            "「投稿图片」图片集合及权限",
            "初始游戏模式",
            "9 个排版区域的默认设置（全部使用系统字体），并生成初始字体样式表",
        ]
        self.stdout.write(
            self.style.NOTICE("init_site 将创建以下内容（本轮不写入数据库）：")
        )
        for item in planned:
            self.stdout.write(f"  - {item}")
        self.stdout.write(
            self.style.WARNING(
                "具体初始数据在 M1、M2 实现。"
                "命令可以重复执行，已存在的内容不会重复创建。"
            )
        )
