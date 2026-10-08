"""233：把前台布局的七条守卫改坏，确认测试会红，再改回来。"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WEB = ROOT / "web"


def once(text, old, new):
    count = text.count(old)
    if count != 1:
        sys.exit(f"要改的原文出现了 {count} 次，不是 1 次：{old!r}")
    return text.replace(old, new, 1)


def run():
    return subprocess.run(["pnpm", "--filter", "@sjtu-ow/site", "test"], cwd=WEB).returncode


CASES = [
    (
        "A 样式表不进页面",
        ROOT / "web/apps/site/server.ts",
        '...parts.assets.css.map((href) => `<link rel="stylesheet" href="${href}">`),\n',
        "\n",
    ),
    (
        "B 导航前缀匹配改精确",
        ROOT / "web/apps/site/src/sections.ts",
        "if (path.startsWith(prefix)) return section",
        "if (path === prefix) return section",
    ),
    (
        "C 访客也画成员菜单",
        ROOT / "web/apps/site/src/components/AccountArea.vue",
        '<details v-if="user" class="c-menu">',
        '<details v-if="!user" class="c-menu">',
    ),
    (
        "D 加载条到了不清 is-loading",
        ROOT / "web/apps/site/src/loadbar.ts",
        "const from = this.progress()\n    this.clear()",
        "const from = this.progress()",
    ),
    (
        "E 右键菜单没有图片组",
        ROOT / "web/apps/site/src/contextmenu-entries.ts",
        "if (target.imageSrc !== null) {",
        "if (false && target.imageSrc !== null) {",
    ),
    (
        "F 有昵称也当访客",
        ROOT / "web/apps/site/src/entry-server.ts",
        'return { user: { nickname: user.nickname, admin: user.admin === true } }',
        "return VISITOR",
    ),
    (
        "G 提示不会自己走",
        ROOT / "web/apps/site/src/toasts.ts",
        "if (at >= 0) toasts.splice(at, 1)",
        "if (false) toasts.splice(at, 1)",
    ),
]


def main():
    files = {path: path.read_text(encoding="utf-8") for _, path, _, _ in CASES}
    if run() != 0:
        sys.exit("基线不是绿的，先修测试")
    try:
        for name, path, old, new in CASES:
            original = files[path]
            path.write_text(once(original, old, new), encoding="utf-8")
            code = run()
            path.write_text(original, encoding="utf-8")
            if code == 0:
                sys.exit(f"没抓到：{name}")
            print(f"抓到 {name}（退出码 {code}）")
    finally:
        for path, original in files.items():
            path.write_text(original, encoding="utf-8")
    if run() != 0:
        sys.exit("改回来之后不是绿的")
    print(f"{len(CASES)} 处都抓到，已改回")


if __name__ == "__main__":
    main()
