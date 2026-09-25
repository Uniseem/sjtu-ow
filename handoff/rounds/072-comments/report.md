# 072 实现报告

## 结论

**完成。** 设计 v1.9 新增 5.6 节和 12.15 表；新应用 `comments` 提供 YouTube 式的文章评论（顶层 + 折叠回复串、@被回复者）、先发后审、内容编辑隐藏与恢复、每篇文章的开关、限流；静态页只读、登录后由槽位整块换成交互版。31 条测试（24 个函数，含参数化），14/14 处规则变异被抓到。

## 逐条结果

| 任务 | 结果 |
|---|---|
| 设计 v1.9 | 1.3、2.3、4.3.1、4.4、5.5.1、新 5.6 节、12.5.1、12.14.1、新 12.15 节、13.4、13.13.3、13.13.4、14.1、14.2、15.2、附录 B、C、D |
| 迁移 | `accounts/0004`（`Feature` 加 `article_comment`）、`moderation/0003`（`TargetType` 加 `comment`，且进 `SHORT_TYPES` 合并送审）、`content/0004`（`ArticlePage.comments_enabled`）、`comments/0001`（`Comment` 表，两个索引）。`RESERVED_CHILD_SLUGS` 加 `comments` |
| 服务 | `can_comment()`（登录、功能权限、文章开放评论）、`create()`（长度 1–500、parent 同一篇且可见、回复的回复挂回顶层并记 `reply_to_user`；提交后送审 + 刷新文章页）、`hide()` / `unhide()`（内容编辑权限）、`thread()`（置顶在前、时间倒序、每页 20、回复按时间；读者看不到隐藏的，但有可见回复的隐藏顶层保留占位；内容编辑看到隐藏的并标出）、`assign_comment_permissions()`（`init_site` 调用） |
| 渲染 | `comments/rendering.py`：一个 `section_context()` 出静态版和交互版；`section.html` + `_item.html` + `_reply.html` + `_composer.html` + `_more.html`。静态版无表单、无 CSRF、不写 Cookie；`ArticlePage.get_context` 按登录状态选版本，`?comments=N` 翻页；槽位 `article-comments:<id>` 注册在 `AppConfig.ready()`，未发布或不存在的文章返回空串 |
| 端点 | `/comments/<文章>/new/`、`/comments/<评论>/reply/`（POST；HTMX 返回整块评论区，普通请求提示后跳回文章；未登录的 HTMX 请求 `HX-Redirect` 到登录页）、`/comments/<文章>/more/`（GET，下一页 + 带外替换「加载更多」）、`/comments/<评论>/hide/`、`/unhide/`（内容编辑，否则 403）。限流每人每分钟 3 条、每天 100 条：超限的 HTMX 请求返回整块评论区并带「评论太频繁」的提示（不是 429，否则 HTMX 不换内容） |
| 后台 | `CommentViewSet`（列表：摘录、作者、文章、时间、隐藏、置顶；筛选、搜正文；编辑页只有两个开关；保存后刷新文章页），菜单「社区 → 评论」内容编辑可见；`ArticlePage` 面板加「开放评论」，投稿者表单里去掉这个字段 |
| 连带 | `accounts.services.refresh_nickname_pages()` 加评论过或被 @ 的文章；`init_site` 输出一行「已分配评论权限」 |
| 测试 | `comments/tests/test_comments.py`：发表与回复串结构、匿名与禁言、关闭评论、长度三种、跨文章和隐藏的 parent、送审记录、隐藏与可见性、占位、排序与分页、静态页只读、真生成静态文件无 CSRF 无「退出」、槽位给登录者发表框、未发布文章槽位为空、登录实时页是交互版、内容编辑看到隐藏正文和恢复按钮、无 Alpine 表达式和内联处理器、端点五条、限流、未发布 404、加载更多、隐藏端点权限、预渲染触发两条、改昵称刷新、后台列表权限、保留别名 |

## 验收输出

```
$ uv run python manage.py makemigrations accounts moderation content comments --name article_comments
  accounts\migrations\0004_article_comments.py
  content\migrations\0004_article_comments.py
  moderation\migrations\0003_article_comments.py
  comments\migrations\0001_article_comments.py

$ uv run ruff check . && uv run ruff format --check .
All checks passed!
238 files already formatted

$ PYTHONUTF8=1 uv run pytest -q comments content core/tests/test_chapter15_audit.py core/tests/test_documented_urls.py core/tests/test_prerender.py accounts moderation
309 passed in 56.32s

$ PYTHONUTF8=1 uv run pytest -q
864 passed in 158.15s (0:02:38)
```

**变异（脚本 `mutate_072.py`，本轮目录）**

```
✓ 被抓到 功能权限不再检查 | 1 failed, 30 passed in 8.67s
✓ 被抓到 关闭评论的文章也收 | 1 failed, 30 passed in 10.15s
✓ 被抓到 空评论也收 | 3 failed, 28 passed in 8.93s
✓ 被抓到 超长评论也收 | 1 failed, 30 passed in 8.83s
✓ 被抓到 跨文章回复也收 | 1 failed, 30 passed in 8.77s
✓ 被抓到 隐藏的评论还能回复 | 1 failed, 30 passed in 9.05s
✓ 被抓到 回复的回复变成多层嵌套 | 1 failed, 30 passed in 9.08s
✓ 被抓到 读者也能隐藏 | 2 failed, 29 passed in 8.90s
✓ 被抓到 读者看得到隐藏的评论 | 1 failed, 30 passed in 9.16s
✓ 被抓到 置顶不再排最前 | 1 failed, 30 passed in 14.57s
✓ 被抓到 评论不再送审 | 1 failed, 30 passed in 17.36s
✓ 被抓到 评论不再刷新文章页 | 1 failed, 30 passed in 19.05s
✓ 被抓到 限流被拆掉 | 1 failed, 30 passed in 15.99s
✓ 被抓到 未登录的 HTMX 请求不再跳登录 | 1 failed, 30 passed in 14.72s
---
14/14 mutations caught
```

## 设计偏差

一处：限流超限时不返回 429，而是返回整块评论区并带提示。原因是 HTMX 默认不把 4xx 响应换进页面，用户会看到「点了没反应」。设计 5.6 里写的是「每人每分钟 3 条、每天 100 条」，没写状态码；15.2 也只写了限制本身。

## 未完成 / 顺带发现

- 点赞、最新/最热、置顶操作入口、编辑、删除在 073；`is_pinned`、`is_deleted`、`like_count`、`edited_at` 字段和排序、占位逻辑已经就位
- 评论区没有在真实浏览器里看过（发表框、折叠、HTMX 换块），074 部署后要点一遍
- `Comment.author` 是 PROTECT，注销账号只匿名化不删用户，所以不冲突；但注销后评论仍显示「已注销用户」的昵称，这是设计 3.8 的既定做法（文章署名同理）

## 需要确认

无。

## 改动文件

`docs/design.md`、`README.md`、`AGENTS.md`、`handoff/STATUS.md`、`handoff/rounds/072-comments/`；`comments/`（新：`__init__.py`、`apps.py`、`models.py`、`services.py`、`rendering.py`、`views.py`、`urls.py`、`wagtail_hooks.py`、`migrations/0001_article_comments.py`、`templates/comments/`、`tests/`）；`accounts/models.py`、`accounts/migrations/0004_article_comments.py`（新）、`accounts/services.py`；`moderation/models.py`、`moderation/services.py`、`moderation/migrations/0003_article_comments.py`（新）；`content/models.py`、`content/forms.py`、`content/migrations/0004_article_comments.py`（新）、`content/templates/content/article_page.html`；`core/management/commands/init_site.py`、`core/tests/test_chapter15_audit.py`、`core/tests/test_documented_urls.py`；`sjtu_ow/settings/base.py`、`sjtu_ow/urls.py`、`pyproject.toml`
