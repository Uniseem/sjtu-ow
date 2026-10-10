# 275 前端：接 BE-0–3 的类型，重写文章页（含评论）、资讯列表、首页

## 背景

273/274（GPT/GLM）做完了 BE-0–3：普通页导入、`/api/page/{slug}` 的 SEO 字段、搜索的分组回答、会话的 `can_submit_article`，`apigen` 已重新生成。按规则，删除 `pending-api.ts` 对应段、页面改用生成类型、跑对拍是前端（Claude）的事。同时 STATUS 的 `next_frontend` 指向 273 遗留的内容组：文章页（现在不在路由表里，404）、资讯列表、首页——三页都是 260 时代的旧货（手写 `fetch`、吞错误、禁用色板、不照旧模板），照 `docs/frontend-migration.md` 第 6.2 节重写。

## 本轮范围

**做**：

1. **接 BE-0/BE-1**：删 `pending-api.ts` 的 `SitePage` 段，`StandardPage.vue` 改用生成的 `GetApiPageSlugOut`（已含 `seo_title`、`search_description`、`last_published_at`）。
2. **接 BE-2**：删 `SearchResults`/`SearchGroup` 段和 `searchSite` 的双重断言，`Search.vue` 改用生成的 `GetApiSearchOut`（`groups` 已是生成形状；旧的五份平铺列表在生成类型里仍在，不动）。
3. **接 BE-3**：删 `SubmitAbility` 段，`Submit.vue` 直接读生成会话类型里的 `can_submit_article`。
4. **文章页 `/news/<slug>/`**：照 `content/templates/content/article_page.html`、`_toc.html`、`comments/section.html`、`_item.html`、`_reply.html`、`_composer.html`、`_like.html`、`_own.html` 重写 `ArticleDetail.vue` 并登记路由 `/news/:slug/`（现在 404）。评论区做成 `packages/ui` 的 `CComments` 一组（5.1 表），动作 emit 给页面、页面调生成的评论接口后重拉列表——和旧站 HTMX 整节换新一个语义。评论的递归形状生成器表达不了（`replies` 生成成 `unknown[]`），在 `pending-api.ts` 收窄并注明。
5. **资讯列表 `/news/`**：照 `article_index_page.html` 重写 `News.vue`：栏目简介、分类标签（`aria-current`）、文章卡（含置顶）、分页（`CPager`，`extra_query` 保留 category）。
6. **首页 `/`**：照 `home_page.html` 重写 `Home.vue`：首屏（`section_picture "home"`、两行标题、校徽、数字条）、近期（大图卡 + 内战行）、资讯与公告（置顶标记）、战队；登录成员加「我的安排」。
7. **登记后端缺口**（页面照旧模板写好、有就显示，规格写进 STATUS「交给后端（GPT）」）：
   - **BE-4**：`GET /api/page/news/{slug}` 补文章页字段：作者卡（`user_id`、头像、`is_active`、宣言）、作者已发布文章数、`last_published_at`（「更新于」）、`comment_total`（头部事实行）、`older`/`newer`（同栏目前后篇）、`related`（同分类最新 3 篇的卡片数据）、`tournament`（关联赛事卡投影）、`seo_title`、`search_description`。依据 `ArticlePage.get_context`。
   - **BE-5**：`GET /api/page/news` 补 `categories`（`sort_order, name` 排序）、`intro_html`（栏目简介渲染后）、items 补 `default_cover_image_id`（分类默认封面）。依据 `ArticleIndexPage.get_context`。
   - **BE-7**：`GET /api/session` 的 user 补 `can_comment`（`can_use("article_comment")` 本身），评论区才能像旧站那样预先显示「你暂时无法使用此功能」——后台 caps 是另一套语义，判不了这个。

**不做**：评论功能禁用者以外的权限矩阵补测（守门矩阵归 Go）；旅程脚本；个人中心、后台其余页面；部署；不动旧站。

## 任务

| # | 任务 | 验证 |
|---|---|---|
| 1 | `pending-api.ts`：删 BE-0/1/2/3 三段，加 BE-4/BE-5/BE-7 与评论收窄段 | `pnpm test`；`grep` 确认旧段没了 |
| 2 | `StandardPage.vue`/`Search.vue`/`Submit.vue` 换生成类型 | 现有 content.test.ts 全绿（形状不变） |
| 3 | `CComments` 组件组（section/item/reply/composer），SSR 输出和旧模板同构 | 新 SSR 测试对照旧模板逐段断言 |
| 4 | `ArticleDetail.vue` 重写 + `/news/:slug/` 进路由表；评论区动作调生成的接口 | routes.test、content.test；无 `any`、无禁用类 |
| 5 | `News.vue` 重写 | 同上 |
| 6 | `Home.vue` 重写（含登录时 `/api/me/agenda`） | 同上 |
| 7 | 整组（Go + Web）、browser-check、对拍 `home,news,article,about,search,submit` | 测试机日志，退出码 0 |

## 验收标准

- `scripts/check.sh` 整组绿（测试机）。
- `browser-check.mjs` 绿（严格 CSP 零违规、激活零警告）。
- 对拍 `--only=home,news,article,search,about --wide --strict` 通过（BE-4/BE-5 缺的字段导致的差异逐条列出：文章页作者卡/上下篇/相关文章/关联赛事卡、资讯页分类标签与简介——页面已有结构，数据等后端）。
- 源码守卫：无色板类、无 `fetch("/api`、无 `:style`、无 `any`（除白名单）、路由表无标题占位页。
- STATUS 更新：前台页面进度表三行更新、交给后端表加 BE-4/BE-5/BE-7、BE-0–3 标「已接 275」。
