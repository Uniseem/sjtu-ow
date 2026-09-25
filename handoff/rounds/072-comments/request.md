# 072 文章评论基础

## 背景

用户 2026-09-25 决定做文章评论：登录用户可发；先发后审（AI 审核 + 内容编辑隐藏）；照 YouTube 评论区（顶层评论 + 折叠的回复串，回复可 @某人）；要点赞、最新/最热排序、管理员置顶、编辑自己的评论；只挂在文章页。本轮做基础，点赞、排序、置顶、编辑、删除在 073。

## 本轮范围

做：

- 设计 v1.9：1.3 删「文章评论」；4.3.1/4.4 加功能标识 `article_comment`；5.2 文章页；5.5.1 送审范围加评论；新增 5.6 节「文章评论」；12.5.1 `comments_enabled`；新增 12.15 `comments` 表；12.11、12.14.1；13.4 路由；13.7/13.8；13.13.1/13.13.3/13.13.4；14.1/14.2 后台「评论」；15.2 限流；附录 B/C/D
- 迁移：`accounts/0004`（`Feature` 加 `article_comment`）、`moderation/0003`（`TargetType` 加 `comment`）、`content/0004`（`ArticlePage.comments_enabled`）、新应用 `comments` 的 `0001`（`Comment`：page、author、parent（只指顶层）、reply_to_user、body ≤ 500、created_at、edited_at、is_pinned、is_hidden、is_deleted、like_count）；`RESERVED_CHILD_SLUGS` 加 `comments`
- 服务：`can_comment()`、`create()`（功能权限、文章已发布且开放评论、长度、parent 属于同一篇且是顶层；送审；刷新文章页）、`hide()` / `unhide()`、`visible_thread()`（顶层分页 20 条 + 加载更多；隐藏的顶层若有可见回复渲染占位）、`assign_comment_permissions()`（内容编辑）
- 渲染：一个上下文函数 + 一个带 `interactive` 标记的模板；静态版进预渲染（只读，`<details>` 折叠回复串，无 CSRF、不写 cookie、不含「退出」）；登录用户由槽位 `article-comments:<page_id>` 整体替换成交互版；`ArticlePage.get_context` 对已登录的实时渲染直接给交互版
- 端点：`/comments/<page_pk>/new/`、`/comments/<pk>/reply/`（POST，登录，HTMX 未登录返回 `HX-Redirect`）、`/comments/<page_pk>/more/?page=N`（GET 实时）；限流每人每分钟 3 条、每天 100 条
- 后台：`CommentViewSet`（内容编辑可见），隐藏/恢复视图；`ArticlePage` 面板加「开放评论」，投稿者看不到
- `refresh_nickname_pages` 加上评论过或被 @ 的文章
- 测试与变异；附录 B pin；地址清单

明确不做：点赞、排序、置顶、编辑、删除（073）；邮件通知；赛事和内战页的评论。

## 验收标准

本地检查全绿（逐条看退出码）；新守卫逐个变异被抓到；静态页真生成一次确认无 CSRF、无「退出」；CI 绿。
