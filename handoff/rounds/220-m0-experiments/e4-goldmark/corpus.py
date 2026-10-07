"""E4 corpus: Markdown sources and what the production renderer
(content/markdown.py, markdown-it-py) makes of each. Run from the repository
root:  DJANGO_SETTINGS_MODULE=sjtu_ow.settings.dev uv run python handoff/rounds/220-m0-experiments/e4-goldmark/corpus.py

Sources: (1) every string literal handed to render()/analyse()/plain_text() in
the existing tests, (2) the repository's own Markdown documents cut at their
`##` headings, (3) a list of awkward inputs written for this experiment.
No article text from the live site is used (round 220 does not touch it).
"""

import ast
import json
import re
import sys
from pathlib import Path

import django

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
django.setup()

from django.conf import settings  # noqa: E402

from content import markdown  # noqa: E402

OUT = Path(__file__).with_name("corpus.json")


def from_tests():
    found = []
    for path in sorted(ROOT.glob("**/tests/test_*.py")):
        if ".venv" in path.parts or "handoff" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "attr", getattr(node.func, "id", ""))
            if name in {"render", "analyse", "plain_text"} and node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value.strip():
                    found.append((f"test:{path.relative_to(ROOT)}:{node.lineno}", arg.value))
    return found


def from_docs():
    found = []
    files = [*ROOT.glob("*.md"), *ROOT.glob("docs/*.md"), *ROOT.glob("docs/rewrite-research/*.md"), *ROOT.glob("handoff/*.md")]
    for path in sorted(set(files)):
        text = path.read_text(encoding="utf-8")
        parts = re.split(r"(?m)^(?=## )", text)
        for index, part in enumerate(parts):
            if part.strip():
                found.append((f"doc:{path.relative_to(ROOT)}#{index}", part))
    return found


AWKWARD = [
    "# 一级\n## 二级\n### 三级\n#### 四级\n##### 五级\n###### 六级\n",
    "标题\n===\n\n小标题\n---\n",
    "一行\n第二行\n\n第三段  \n两个空格硬换行\n反斜杠\\\n硬换行\n",
    "*斜体* **粗体** ***粗斜*** ~~删除~~ `行内代码` 与 \\*转义\\*\n",
    "- 一\n- 二\n  - 二之一\n  - 二之二\n- 三\n\n1. 甲\n2. 乙\n   1. 乙一\n\n5. 从五开始\n6. 六\n",
    "- [ ] 待办\n- [x] 完成\n",
    "```python\nprint('hi')\n```\n\n    缩进代码\n\n~~~\n波浪线围栏\n~~~\n",
    "> 引用一\n> 第二行\n>\n> > 嵌套引用\n",
    "> 好的代码是它自己最好的文档。\n> ——某位工程师\n",
    "> 单行引用\n> ——出处\n",
    "> 只有出处的引用\n\n——不是引用里的\n",
    "| 名称 | 数量 |\n|:--|--:|\n| 甲 | 1 |\n| 乙 | 22 |\n",
    "| a | b |\n|---|---|\n| 带 \\| 竖线 | `x|y` |\n",
    "链接 [文字](https://example.com/a?b=1&c=2 \"标题\") 与 <https://example.com/auto> 与 [引用][r]\n\n[r]: https://example.com/ref\n",
    "[坏链接](javascript:alert(1)) 和 [另一个](data:text/html,hi) 和 [正常](/relative/path)\n",
    "裸地址 https://example.com/path.html，后面是逗号。还有（https://example.com/x）括号里的，和 https://example.com/a_b_(c) 末尾括号。\n",
    "地址在句末 https://example.com/end。 英文句末 https://example.com/end.\n",
    "已有链接 [https://example.com/in-link](https://example.com/in-link) 不重复\n",
    "https://example.com/alone-on-its-line\n",
    "<script>alert(1)</script>\n\n<div class=\"x\">块 HTML</div>\n\n行内 <b>粗</b> 与 <!-- 注释 -->\n",
    "&amp; &lt; &copy; &#35; &#x1F600; 实体\n",
    "![alt 文字](/media/images/a.png)\n",
    "![图一](/media/images/a.png)\n![图二](/media/images/b.png)\n",
    "![带标题](/media/images/a.png \"图片标题\")\n",
    "文字里的小图 ![小](/media/images/s.png) 继续\n",
    "![外站图](https://elsewhere.example/x.png)\n",
    "文字 ![外站内联](https://elsewhere.example/x.png) 继续\n",
    "![本站绝对](http://localhost:8000/media/images/a.png)\n",
    "https://www.bilibili.com/video/BV1xx411c7mD\n",
    "https://www.bilibili.com/video/BV1xx411c7mD?p=3\n",
    "[看这个视频](https://www.bilibili.com/video/BV1xx411c7mD/)\n",
    "视频前有文字 https://www.bilibili.com/video/BV1xx411c7mD\n",
    "https://player.bilibili.com/player.html?bvid=BV1xx411c7mD&page=2\n",
    "https://www.bilibili.com/video/BV1xx411c7mD?bvid=notabv\n",
    "***\n\n---\n\n___\n",
    "第一段\n\n\n\n第二段（多个空行）\n",
    "中文，标点。「引号」『二层』《书名》【方括号】\n",
    "1\\. 不是列表\n\n- 缩进\n\n    - 四空格\n",
    "Term\n: 定义（不被支持）\n",
    "脚注[^1]\n\n[^1]: 不被支持\n",
    "# 带 `代码` 和 **粗** 的标题 #\n",
    "#没有空格不是标题\n\n# \n",
    "表格后紧跟段落\n\n| a |\n|---|\n| 1 |\n后面\n",
    "emoji 😀 与 零宽​字符 与  不换行空格\n",
    "很长的一行 " + "字" * 400 + "\n",
    "\\<not html\\> 与 a < b > c\n",
    "- 列表里的 https://example.com/in-list，地址\n- 第二项\n",
    "[中文地址](https://example.com/中文/路径?关键=值) 与 [带空格](<https://example.com/a b>) 与 <a@example.com>\n",
    "[带标题](https://example.com/t \"一个 &amp; 标题\") 与 [单引号](https://example.com/u 'x')\n\n[ref]: https://example.com/r \"引用标题\"\n\n[用引用][ref] 与 [ref]\n",
    "``含 ` 反引号的代码`` 与 `` ` `` 与 ```三个```\n",
    "- 紧凑\n- 列表\n\n- 松散\n\n- 列表\n\n10. 十\n11. 十一\n\n* 星号\n+ 加号\n",
    "- ![紧凑列表里的图](/media/images/a.png)\n- 第二项\n\n- ![松散列表里的图](/media/images/b.png)\n\n- 第二项\n",
    "> ![引用里的图](/media/images/a.png)\n\n> 引用里的视频\n>\n> https://www.bilibili.com/video/BV1xx411c7mD\n",
    "| 地址 | 说明 |\n|---|---|\n| https://example.com/cell，逗号 | **粗** `代码` |\n",
    "# 标题里的地址 https://example.com/h1。\n\n## 带 [链接](/x) 的标题\n",
    "> 引用第一行\n> 第二行\n> ——出处在第三行，\n> ——不对，最后一行才算\n",
    "> 第一行  \n> ——硬换行后的出处\n",
    "> *斜体* ——不是行首\n> ——有 **粗体** 的出处\n",
    "snake_case_word 与 2*3*4 与 _强调_ 与 a_b_c 与 **未闭合\n",
    "~单波浪线~ 与 ~~双波浪线~~ 与 ~~~三个~~~\n",
    "\t制表符缩进的代码\n\n正文\n\n\t\t两个制表符\n",
    "![](/media/images/noalt.png)\n\n![]()\n\n![ ](/media/images/space.png)\n",
    "![带 *强调* 的图注 `代码`](/media/images/a.png)\n",
    "![图](/media/images/a.png) ![并排第二张](/media/images/b.png)\n",
    "![图一](/media/images/a.png)\n\n文字\n\n![图二](/media/images/b.png)\n",
    "![图一](/media/images/a.png)\n文字紧接着\n",
    "http://localhost:8000/media/images/abs.png 不是图\n\n![本站端口不同](http://localhost:9000/x.png)\n![](https://LOCALHOST:8000/up.png)\n",
    "两个链接 https://a.example.com/x 和 https://b.example.com/y，以及 http://c.example.com/z；还有\nhttps://d.example.com/换行后的\n",
    "地址里的下划线 https://example.com/a_b_c_d 和星号 https://example.com/a*b*c 和与号 https://example.com/?a=1&b=2&c=3\n",
    "括号 (https://example.com/a) 与 [https://example.com/b] 与 {https://example.com/c} 与 \"https://example.com/d\"\n",
    "https://example.com/very/long/" + "path/" * 40 + "end\n",
    "&nbsp;&nbsp;缩进 &quot;引号&quot; &#0; &#xD800; &unknown; &amp\n",
    "A | B\n--|--\n1 | 2\n",
    "|a|b|\n|-|-|\n|1|\n|1|2|3|\n",
    "第一行\\\n第二行\\\\\n第三行\n",
    "<https://example.com/尖括号>\n\n<mailto:a@example.com>\n\n<ftp://example.com/f>\n",
    "[ftp](ftp://example.com/f) [mail](mailto:a@example.com) [tel](tel:+8613800000000) [anchor](#top) [rel](../up) [proto](//cdn.example.com/x)\n",
    "空链接 [空]() 与 [空格]( ) 与 [](https://example.com/emptytext)\n",
    "Setext **强调** 标题\n=====\n\n另一个 `代码` 标题\n-----\n",
    "1. 一\n\n   续段\n\n2. 二\n   > 列表里的引用\n3. 三\n   ```\n   列表里的代码\n   ```\n",
]


def main():
    entries = []
    for source_id, text in [*from_tests(), *from_docs(), *[(f"awkward:{i}", t) for i, t in enumerate(AWKWARD)]]:
        try:
            html = str(markdown.render(text))
        except Exception as error:  # a source the production renderer itself cannot do
            html = None
            print("production renderer failed on", source_id, error, file=sys.stderr)
        entries.append({"id": source_id, "source": text, "html": html})
    OUT.write_text(json.dumps({"site_url": settings.SITE_URL, "entries": entries}, ensure_ascii=False), encoding="utf-8")
    kinds = {}
    for entry in entries:
        kinds[entry["id"].split(":")[0]] = kinds.get(entry["id"].split(":")[0], 0) + 1
    print(f"{len(entries)} documents -> {OUT.name}; by kind: {kinds}; SITE_URL={settings.SITE_URL}")


main()
