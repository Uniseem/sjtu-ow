# 073 实现报告

## 结论

**完成。** 设计 v1.9.1；评论区补齐用户要的 YouTube 要素：点赞（`CommentLike` 表）、最新 / 最热排序、置顶（每篇一条，数据库部分唯一约束兜底）、作者编辑（重新送审）与删除（保留回复串）。29 条测试（含一条真线程并发双击），31/31 处规则变异被抓到。

## 逐条结果

| 任务 | 结果 |
|---|---|
| 设计 v1.9.1 | 4.4 三行权限；5.6「排序与分页」「点赞与置顶」和渲染段落；12.11 两行约束；12.15.1 去掉「v1.9.1」标记、加部分唯一约束；新 12.15.2 `CommentLike`；13.4 五条路由；13.13.3；14.2；附录 C 点赞限流；附录 D |
| 迁移 | `comments/0002_comment_extras`：`CommentLike(comment, user, created_at)`，唯一 (comment, user)；`Comment` 加部分唯一约束 `one_pinned_comment_per_page`（`is_pinned` 时 page 唯一） |
| 服务 | `toggle_like()`（登录、评论可见；`get_or_create` + `F()` 同事务增减 `like_count`，再点一次取消）、`pin_problem()` / `release_pin()` / `pin()` / `unpin()`（内容编辑；只能置顶可见的顶层；先取消旧的再置顶）、`edit()`（作者；可见；1–500 字；`edited_at`；重新送审）、`delete()`（作者；清空正文、取消置顶、行保留）、`hide()` 同时取消置顶、`thread()` 加 `sort`（`new` 默认，`top` 按置顶、赞数、可见回复数、时间；未知值归一为 `new`）、已删除但还有可见回复的顶层保留占位、返回当前访客点过的赞 |
| 端点 | `/comments/<评论>/like/`、`/edit/`、`/delete/`、`/pin/`、`/unpin/`（POST；HTMX 返回整块评论区，服务的拒绝理由显示在评论区顶部；未登录 `HX-Redirect`）；点赞每人每分钟 60 次；`/more/` 和 `_section_response` 读 `sort`，交互版整块 `hx-include` 一个隐藏的 `sort` 字段，动作后排序不丢 |
| 模板 | `_like.html`（登录后是按钮，静态页是赞数）、`_own.html`（作者的编辑表单在 `<details>` 里、删除按钮）、`_item.html` / `_reply.html`（已删除占位、置顶 / 取消置顶按钮、「已编辑」）、`section.html`（评论多于一条时显示「最新 / 最热」链接，带参数走实时渲染；「加载更多」沿用排序） |
| 后台 | 编辑页勾「置顶」时同样校验（回复、隐藏、已删除的拒绝并在表单上报错），保存时先取消同篇旧的置顶 |
| 测试 | `comments/tests/test_comment_extras.py`：点两次归零且无行、数据库唯一约束、真线程并发双击只剩一行且计数一致、隐藏 / 删除的不能赞、匿名不能赞、访客看到自己点过的赞；最热排序三级、隐藏的回复不算热度、置顶替换旧的并在两种排序都最前、数据库只允许一条置顶、置顶权限与对象、隐藏 / 删除取消置顶；编辑重新送审且赞不变、空 / 空白 / 超长拒绝、隐藏的不能编辑、别人不能编辑删除、删除保留回复串并拒绝再回复、删掉的回复消失；静态页有赞数、占位、排序链接且无 CSRF、无隐藏字段、`?sort=top` 换序；五个端点串起来走一遍、HTMX 动作带排序、匿名与路人被拒、点赞限流、加载更多沿用排序、交互版无 Alpine / 内联处理器且只有自己的评论有编辑删除、后台表单移动置顶并拒绝回复和隐藏、五种动作都重新生成文章页 |
| 连带 | 附录 C 的 pin（`LIKE_LIMIT_MINUTE`）、地址清单五条、README「文章评论」两条 |

## 验收输出

```
$ uv run python manage.py makemigrations comments --name comment_extras
Migrations for 'comments':
  comments\migrations\0002_comment_extras.py
    + Create model CommentLike
    + Create constraint one_pinned_comment_per_page on model comment
    + Add field comment to commentlike
    + Add field user to commentlike
    + Create constraint comment_like_once_per_user on model commentlike

$ PYTHONUTF8=1 uv run python manage.py tailwind build --force
Built production stylesheet 'C:\Users\fyc12\Desktop\Claudee\sjtu-ow\static\css\app.css'.
tailwind exit: 0

$ uv run ruff check .
All checks passed!
[exit 0]

$ uv run ruff format --check .
239 files already formatted
[exit 0]

$ uv run python manage.py makemigrations --check --dry-run
No changes detected
[exit 0]

$ DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod ... uv run python manage.py check --deploy
System check identified no issues (0 silenced).
[exit 0]

$ PYTHONUTF8=1 uv run pytest -q
898 passed in 130.08s (0:02:10)
[exit 0]
```

（逐条单独看退出码，没有用管道合并；069 轮的教训。）

**变异（脚本 `mutate_073.py`，本轮目录）**

```
$ python mutate_073.py            # 第一次：第 17 条的匹配串在 create() 和 edit() 里各出现一次，脚本改文件前先断言失败，代码没被动过
✓ 被抓到 未登录也能点赞 | 1 failed, 28 passed in 17.31s
✓ 被抓到 隐藏或删除的也能点赞 | 1 failed, 28 passed in 15.45s
✓ 被抓到 点赞不加计数 | 7 failed, 22 passed in 15.30s
✓ 被抓到 再点一次不取消 | 2 failed, 27 passed in 16.05s
✓ 被抓到 回复也能置顶 | 2 failed, 27 passed in 14.40s
✓ 被抓到 隐藏或删除的也能置顶 | 2 failed, 27 passed in 15.65s
✓ 被抓到 读者也能置顶 | 2 failed, 27 passed in 15.20s
✓ 被抓到 置顶不检查 pin_problem | 1 failed, 28 passed in 17.07s
✓ 被抓到 置顶新的不取消旧的 | 1 failed, 28 passed in 15.39s
✓ 被抓到 隐藏不取消置顶 | 1 failed, 28 passed in 16.61s
✓ 被抓到 删除不取消置顶 | 1 failed, 28 passed in 16.14s
✓ 被抓到 别人也能编辑和删除 | 2 failed, 27 passed in 10.89s
✓ 被抓到 隐藏的评论还能编辑 | 1 failed, 28 passed in 10.75s
✓ 被抓到 编辑成空也收 | 2 failed, 27 passed in 17.54s
✓ 被抓到 编辑超长也收 | 1 failed, 28 passed in 10.63s
✓ 被抓到 编辑不标记 edited_at | 2 failed, 27 passed in 10.63s
AssertionError: ('编辑不再送审', 2)

$ python mutate_073.py 16         # 匹配串加一行前文后从第 17 条接着跑
✓ 被抓到 编辑不再送审 | 1 failed, 28 passed in 10.13s
✓ 被抓到 删除不清正文 | 1 failed, 28 passed in 13.13s
✓ 被抓到 最热不看赞数 | 4 failed, 25 passed in 17.97s
✓ 被抓到 最热把隐藏的回复也算热度 | 1 failed, 28 passed in 30.33s
✓ 被抓到 最热里置顶不再最前 | 1 failed, 28 passed in 21.66s
✓ 被抓到 未知排序不归一 | 1 failed, 28 passed in 13.69s
✓ 被抓到 已删除的顶层连回复一起消失 | 2 failed, 27 passed in 11.49s
✓ 被抓到 看不到自己点过的赞 | 2 failed, 27 passed in 9.62s
✓ 被抓到 点赞限流被拆掉 | 1 failed, 28 passed in 10.52s
✓ 被抓到 HTMX 动作丢掉排序 | 1 failed, 28 passed in 10.56s
✓ 被抓到 未登录的动作不再跳登录 | 1 failed, 28 passed in 18.12s
✓ 被抓到 加载更多丢掉排序 | 1 failed, 28 passed in 15.02s
✓ 被抓到 后台表单不查置顶规则 | 1 failed, 28 passed in 9.63s
✓ 被抓到 后台置顶不取消旧的 | 1 failed, 28 passed in 9.24s
✓ 被抓到 别人的评论也显示编辑 / 删除 | 1 failed, 28 passed in 9.31s
---
15/15 mutations caught (from #17)

合计 31/31 被抓到。
```

**浏览器（开发服务器，匿名访客看静态版）**

本机开发库是空的，先 `migrate`、`init_site`，再用脚本造一篇文章和六条评论（一条被赞两次并置顶、带两条回复；一条作者删除但下面留一条回复；一条最新没人赞）。`/news/comment-look/` 和 `?sort=top` 各看一次，页面文字如下（内置浏览器 `get_page_text`）：

```
评论 3
最新
最热

登录后评论

读者甲 2026年9月26日 02:14 置顶

第一条评论，后面会被点两个赞。

赞 2
2 条回复

读者丙 2026年9月26日 02:14

最新的一条，没人赞。

赞 0

评论已删除。

1 条回复
```

`?sort=top` 下顺序是：置顶的、已删除占位（有一条可见回复）、最新的（0 赞 0 回复）。两种排序都没有表单、没有点赞按钮，只有赞数和「登录后评论」。登录态的交互版没有在浏览器里点过（本机没有可登录的密码，见「未验证」）。

## 设计偏差

- 计划里写排序切换用 `hx-get` + `hx-push-url`；实际做成普通链接（`?sort=top#comments`）。静态页里也能切，走一次实时渲染，不需要脚本；设计 5.6 按实际写的
- 后台编辑页的「置顶」开关原来（072）不校验、也不取消旧的；这轮补上，否则会撞新加的唯一约束

## 顺带发现，留给下一轮

- 「加载更多」拼出的第二页里，回复串、点赞、编辑按钮都走同一套模板，但第二页是 `hx-swap="beforeend"` 追加进列表，如果访客这时点赞，整块评论区会被第一页替换掉，第二页要重新加载。社团规模下可接受，记在这里
- 个人信息导出（3.8）没有评论和点赞（072 起就没有）。留给 074 或之后决定要不要加

## 未验证

- 浏览器里真人点击（登录态）：本机没有登录账号的密码，交互版靠测试客户端 `force_login` 验证；静态页在浏览器里看过（见验收输出）
- 测试机没动（用户指示）
