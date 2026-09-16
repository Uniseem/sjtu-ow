# 006 实现报告

## 结论

T1–T5 已完成：四种 Wagtail 页面、文章分类 snippet、首页四区块（赛事/内战占位、组队「登录后查看」）、文章列表分页与分类筛选、文章详情、普通页面，以及 title / description / canonical / Open Graph、`/sitemap.xml`、`/robots.txt`。`init_site` 写入页面树和五个初始分类，并**删除** Wagtail 自带的 Editors / Moderators。

## 逐条结果

### T1 页面类型

- `HomePage`（`max_count=1`）、`ArticleIndexPage`、`ArticlePage`、`StandardPage`。
- `ArticlePage` 字段：分类、封面、摘要（200 字）、正文 StreamField、作者。**关联赛事未建字段**，模型里注释说明 M4 再加 `ForeignKey`，没有假外键。
- 正文块：段落（h2/h3、加粗、斜体、列表、链接）、图片+图注、引用、视频嵌入。
- **B 站**：Wagtail 8 自带 `oembed_providers.all_providers` **不包含** `bilibili` / `b23.tv`。本轮只用自带提供方（YouTube、Vimeo 等）。自定义 B 站嵌入规则留到有需求时。测试 `test_bilibili_is_not_a_builtin_oembed_provider` 锁住这一点。
- 视频前台模板从 oEmbed HTML 抽出 `iframe src`，避免把供应商的内联 `style` 写进页面。CSP 增加 `frame-src`：`youtube.com` / `youtube-nocookie.com` / `player.vimeo.com`。
- 置顶文章：`HomePagePinnedArticle` 可排序子表，`InlinePanel max_num=3`，`clean()` / `save()` 再拦第四篇。

### T2 文章分类

- snippet：`name`、`slug`、`sort_order`、`allow_submission`。后台菜单「文章分类」。
- `init_site` `get_or_create`：公告 / 赛事通知（不开放投稿）、攻略 / 战报 / 心得（开放投稿）。已存在的分类不改名、不改标记。

### T3 前台页面

- 首页四个区块：最新公告（有置顶用置顶，否则最新 3 篇）；赛事、内战为「即将开放」，模板保留 `open_tournaments` / `upcoming_scrims`；组队大厅在 `lfg_open_count is not None` 时显示数量，本轮始终为 `None`，登录后仍是「登录后查看」。
- 文章列表：按 `first_published_at` 倒序，每页 12，`?category=` 筛选，分页保留查询参数。
- 文章详情：标题、分类、作者昵称、发布时间、封面、正文。
- 普通页面：`/terms/`、`/privacy/`、`/about/`。
- 模板无内联 `style`。浏览器桌面 + 375px：`document.querySelectorAll('[style]').length === 0`，控制台错误数组为空。

首页仍由 `name="home"` 的 Django 路由承接；若站点根已是已发布的 `HomePage`，则转给 `page.serve()`。

### T4 页面元信息与分享

- 全站 `content.context_processors.seo`；Wagtail 页面在 `get_context` 里覆盖。
- 文章：SEO 标题/描述，没有时用标题/摘要；封面作 `og:image`。普通页面和其他页面：站点简介 + 默认分享图。
- `build_seo(..., kind=)` 预留 `tournament` / `team` / `scrim`。
- `/sitemap.xml` 只列出已发布的文章和普通页面。
- `/robots.txt` 禁止 `/admin/`、`/api/`、`/me/`、`/accounts/`、`/_fragments/`，并带 Sitemap 行。

未上传封面且未配置默认分享图时，**不输出** `og:image`（没有可分享的图，不写空标签）。

### T5 Wagtail 自带组

选择**删除** `Editors` 和 `Moderators`，不改名。理由：本站角色是「内容编辑」等中文预置组；这两个英文空组没有业务权限，留着只会和「内容编辑」抢名字。命令幂等：没有这两个组时打印「无需删除」。

## 验收输出

### 1. ruff / pytest / makemigrations / check --deploy

```
All checks passed!
124 files already formatted
```

```
108 passed in 7.56s
```

```
No changes detected
```

```
DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod \
DJANGO_SECRET_KEY=ci-not-for-production-use-a-long-random-string-at-least-fifty-chars \
FIELD_ENCRYPTION_KEY=ci-not-for-production \
DJANGO_ALLOWED_HOSTS=example.com \
DJANGO_CSRF_TRUSTED_ORIGINS=https://example.com \
SITE_URL=https://example.com \
DJANGO_SECURE_SSL_REDIRECT=true \
uv run python manage.py check --deploy
System check identified no issues (0 silenced).
```

### 2. 发布文章后前台可见

`save_revision().publish()` 发布 `/news/m2-first-guide/`（标题「M2 验收攻略」，分类攻略）。

```
HOME  status=200  （含「最新公告」「M2 验收攻略」「即将开放」「登录后查看」）
LIST  status=200  （含「M2 验收攻略」）
DETAIL status=200 （含正文「正文第一段」、引用「守望先锋，启动。」、作者「验收昵称」）
```

截图：`artifacts/home-desktop.png`、`artifacts/news-desktop.png`、`artifacts/article-desktop.png`。

### 3. 撤回发布后 404

```
live False
unpublished=404
live True
republished=200
```

### 4. 浏览器桌面 + 375px，0 条控制台报错

视口 `innerWidth=1280` 与 `innerWidth=375`。三页 `[style]` 数量均为 0；`window.__owErrors` 为空。375px 出现「打开导航菜单」，抽屉可打开并进入资讯。

截图：

- `artifacts/home-375.png`（抽屉打开，证明移动导航可用）
- `artifacts/news-375.png`
- `artifacts/article-375.png`

回归：已登录用户打开 `/me/`、`/me/game-accounts/`、`/me/contacts/`、`/me/security/` 均正常（资料页昵称「验收五乙」，游戏 ID `LiveFive#1234`，QQ `123456789`）。

### 5. 文章详情元信息

```
<title>M2 验收攻略 · 上海交通大学守望先锋社区</title>
<meta name="description" content="验收用 SEO 描述">
<link rel="canonical" href="http://localhost/news/m2-first-guide/">
<meta property="og:title" content="M2 验收攻略">
<meta property="og:description" content="验收用 SEO 描述">
<meta property="og:url" content="http://localhost/news/m2-first-guide/">
```

本篇没有封面、全站也未上传默认分享图，因此没有 `og:image`。canonical 的主机名来自 Wagtail `Site.hostname`（`localhost`），不是请求里的 `127.0.0.1`。

### 6. sitemap 与 robots

```
GET /sitemap.xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>http://localhost/news/m2-first-guide/</loc>
    <lastmod>2026-09-16</lastmod>
  </url>
  <url>
    <loc>http://localhost/terms/</loc>
    <lastmod>2026-09-16</lastmod>
  </url>
  <url>
    <loc>http://localhost/privacy/</loc>
    <lastmod>2026-09-16</lastmod>
  </url>
  <url>
    <loc>http://localhost/about/</loc>
    <lastmod>2026-09-16</lastmod>
  </url>
</urlset>
```

未包含 `/news/` 栏目页本身。撤回发布期间文章不在 sitemap 中（测试覆盖）。

```
GET /robots.txt
User-agent: *
Disallow: /admin/
Disallow: /api/
Disallow: /me/
Disallow: /accounts/
Disallow: /_fragments/
Sitemap: http://127.0.0.1:8000/sitemap.xml
```

### 7. 回归：/me/、注册登录、healthz

- 未登录：`/me/` `/me/game-accounts/` `/me/contacts/` `/me/security/` 均为 302 → `/accounts/login/?next=…`
- `/accounts/login/`、`/accounts/signup/` 200
- 已登录浏览器：四个个人中心页可用
- worker 在跑：`/healthz` **200**

```
{"status": "ok", "checks": {"database": {"ok": true, "detail": "ok"}, "disk": {"ok": true, "detail": "free space 36.8%"}, "worker_heartbeat": {"ok": true, "detail": "ok (7s ago)", "affects_status": true}, "task_backlog": {"ok": true, "detail": "ok", "affects_status": true}}}
```

### 8. docker / caddy

```
Successfully built a00b797a7b11
Successfully tagged sjtu-ow:ci
```

```
docker run --rm -e CADDY_SITE_ADDRESS=http://localhost \
  -v $PWD/deploy/Caddyfile:/etc/caddy/Caddyfile:ro \
  caddy:2.10-alpine caddy validate --config /etc/caddy/Caddyfile
...
Valid configuration
```

### 9. git

提交信息以 `006:` 开头。

### init_site 幂等

第一次（本机已有 Wagtail 初始数据）：删除 Editors、Moderators，创建分类和页面树。第二次：

```
Wagtail 自带的 Editors / Moderators 组不存在，无需删除。
已确保文章分类：公告（notice）、赛事通知（event-notice）、攻略（guide）、战报（match-report）、心得（experience）
已确保页面树：首页、资讯、用户协议、隐私政策、关于我们
```

不重复建页、不改已有分类。

## 设计偏差

1. 文章详情的 canonical / `og:url` 用 Wagtail `Site.hostname`（默认 `localhost`），和用 `127.0.0.1` 访问时的 Host 不一致。生产配好 Site 主机名即可。若希望永远跟请求 Host，需要 Claude 拍板。
2. 未配置分享图时省略 `og:image`，没有输出空标签。
3. 前台 CSP 增加了 YouTube / Vimeo 的 `frame-src`，否则嵌入视频会被拦住。设计 15.2 只写了后台放宽，没写前台嵌入。
4. 首页四个卡片在宽屏是两列；375px 单列。赛事/内战占位用了现成的 `empty_state`（内部也是 `h2`），卡片标题再套一层，标题层级略重复，能用。

## 未完成 / 不同意

无。投稿、字体、预渲染、AI 审核按范围不做。

## 顺带发现

- 栏目子页面 slug 若叫 `teams` / `lfg` 等会和 Django 固定路由抢路径。本轮给 `HomePage` 的子页面加了保留 slug 校验（设计 13.4 的默认）。文章自己的 slug 在 `/news/<slug>/` 下，不拦。
- pytest 的 `--reuse-db` 测试库有时没有 Wagtail 0002 写入的 Root 页。`init_site` 在根节点缺失时会 `Page.add_root`，避免命令直接报错。
- 本机 `/usr/bin/git` 仍被 Xcode license 拦住，提交继续用 GitHub Desktop 自带 git。
- Cursor 内置浏览器对 `<a>` 的 click 常常只聚焦不跳转，用 Enter 可以打开链接；这是浏览器自动化的限制，不是站点问题。

## 需要确认

无。

## 改动文件

模型与后台：`content/models.py`、`content/blocks.py`、`content/wagtail_hooks.py`、`content/migrations/0001_initial.py`。

初始化：`content/services.py`、`core/management/commands/init_site.py`。

前台与 SEO：`content/views.py`、`content/urls.py`、`content/seo.py`、`content/context_processors.py`、`content/templates/content/**`、`templates/base.html`、`templates/components/pagination.html`、`assets/css/input.css`、`sjtu_ow/urls.py`、`sjtu_ow/settings/base.py`、`core/views.py`、`core/models.py`、`core/migrations/0004_alter_sitesettings_default_share_image_and_more.py`。

测试：`content/tests/test_content.py`、`core/tests/test_templates.py`。

文档：`README.md`、`handoff/STATUS.md`、本报告。
