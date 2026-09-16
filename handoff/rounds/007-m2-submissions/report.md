# 007 实现报告

## 结论

T1–T4 已完成：`init_site` 每次按 `SITE_URL` 写入 Wagtail 默认站点主机名和端口；视频嵌入只接受 B 站（含 `b23.tv`），CSP `frame-src` 只留 `player.bilibili.com`；「投稿者」组按验证邮箱 + `article_submit` 自动同步；`/submit/`、内容审核工作流、「投稿图片」集合和投稿者后台定制已接上。投稿者侧边栏页面树**已被过滤**（只含已发布页和自己的稿件）。

## 逐条结果

### T1 站点主机名

- `content.services.parse_site_url` / `sync_default_site_from_site_url`：`https` 默认 443、`http` 默认 80，带端口用给定端口。
- `init_site` 每次执行都写入默认 `Site`，并打印 `已按 SITE_URL 设置站点：{hostname}:{port}`。
- README 部署说明已写明这一点。
- 测试：改 `SITE_URL` 后跑命令，站点记录和文章 `canonical` / `og:url` 跟着变。

Wagtail 的 `Site.root_url` 在端口不是 80/443 时一律用 `http://host:port`（上游行为）。本机 `http://localhost:8000` 符合这个规则；`https://ow.example.com`（443）会得到 `https://ow.example.com`。

### T2 B 站嵌入

- `content.embeds.BilibiliEmbedFinder`：接受 `bilibili.com` / `www` / `m` / `player` 的 `/video/<BV>`，以及 `b23.tv`（跟随短链再取 BV）。
- 前台仍只渲染抽出的 `iframe src`，不带第三方内联 `style`。
- `SECURE_CSP["frame-src"]`：`CSP.SELF` + `https://player.bilibili.com`。YouTube / Vimeo 已去掉。
- 粘贴不支持的地址：`VideoBlock.clean` 捕获 `EmbedException`，中文提示「只支持哔哩哔哩（B 站）视频链接，请粘贴 bilibili.com/video/ 或 b23.tv 地址。」
- 测试覆盖长链、短链（mock）、不支持的 URL、`frame-src` 不含站外播放器。

### T3 投稿

1. **组同步**：`email_is_verified` 且 `can_use(user, "article_submit")` 才留在「投稿者」。触发：`email_confirmed`、`EmailAddress` 保存、用户启用/停用（`User.post_save`）、`article_submit` 的组限制/单用户规则增删、用户换组（`m2m_changed`）。`init_site` 末尾全量同步一次。
2. **权限**：投稿者对文章栏目 `add`；「投稿图片」集合 `add`/`choose`；无 `publish`。认证作者栏目 `add`+`publish`。内容编辑对首页和栏目有增改发和锁，根集合图片权限。
3. **工作流**：`内容审核`，一步 `内容编辑审核`，审核组=内容编辑，`WorkflowPage` 绑到所有 `ArticleIndexPage`。
4. **`/submit/`**：未登录 **200** 并列出「未登录」（不 302 到登录页，按 5.4.3 / 本轮要求）；已登录但未验证或无权限显示对应原因；通过则 `sync_submitter_group` 后 302 到第一个开放投稿栏目下的 `articlepage` 新建页。导航和个人中心有「投稿」入口。
5. **后台定制**：
   - `construct_main_menu`（`order=1000`，避免排在 `wagtail.admin` 之前被后写入的项冲掉）：投稿者只留「后台首页」「图片」。
   - 首页面板换成「我的投稿」+「新建投稿」；`construct_homepage_summary_items` 同样 `order=1000` 后清空站点统计。
   - 页面列表：`construct_explorer_page_queryset` **只作用于搜索 queryset**。列表和侧边栏实际走 `PagePermissionPolicy.explorable_instances`，因此对该方法做了同样的 `live | owner` 过滤。
   - **侧边栏页面树：已过滤。** 投稿者调 `/admin/api/main/pages/?child_of=<资讯>&for_explorer=1`，标题只有已发布页和自己的稿件；内容编辑的未发布稿「编辑未发布稿件007」不出现。
   - `author` 仅超级管理员/内容编辑可见；投稿者分类 queryset 仅 `allow_submission=True`；投稿者保存时作者写成 `owner`。
   - 图片：5MB，jpg/jpeg/png/webp；投稿者只能用「投稿图片」集合。
6. **审核邮件**：Wagtail `send_mail` 走 `get_connection()` → `QueuedEmailBackend`；worker 打出 `core.tasks.deliver_queued_email` `SUCCESSFUL`。提交时通知内容编辑，通过时通知投稿人。

「投稿者-only」判定：在「投稿者」组、非超管、且不在内容编辑/认证作者/赛事管理员/内战管理员。内容编辑会被同步进「投稿者」，但菜单仍是完整后台。

### T4 回归与锁定

投稿者菜单无赛事/内战/用户/功能权限/设置。直达：

| 网址 | 投稿者响应 |
|---|---|
| `/admin/` | 200 |
| `/admin/images/` | 200 |
| `/admin/pages/` | 302 → `/admin/pages/4/`（资讯 explorer，已过滤） |
| `/admin/users/` | 302 → `/admin/` |
| `/admin/feature_group_restrictions/` | 302 → `/admin/` |
| `/admin/settings/core/sitesettings/` | 302 → 实例页再 302 → `/admin/` |
| `/admin/settings/` | 404 |
| `/admin/tournaments/` | 404（本里程碑无此后台） |

Wagtail 对无权限的已注册后台 URL 是送回控制面板，不是 403。测试按重定向链和页面正文断言（设置页看不到 SMTP 表单）。

## 验收输出

### 1. ruff / pytest / makemigrations / check --deploy

```
All checks passed!
131 files already formatted
```

```
122 passed in 9.63s
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

### 2. SITE_URL → 站点记录和 canonical

`SITE_URL=https://ow.example.com uv run python manage.py init_site`：

```
已按 SITE_URL 设置站点：ow.example.com:443
```

默认站点：`hostname=ow.example.com` `port=443` `root_url=https://ow.example.com`。

文章 `get_full_url()`：`https://ow.example.com/news/m2-first-guide/`。

当时用 `http://127.0.0.1:8000/news/m2-first-guide/` 拉到的标签：

```
<link rel="canonical" href="https://ow.example.com/news/m2-first-guide/">
<meta property="og:url" content="https://ow.example.com/news/m2-first-guide/">
```

随后无参再跑 `init_site`，恢复为 `localhost:8000`。

### 3. B 站 iframe 与 CSP

发布 `/news/bilibili-007/`，正文视频 URL `https://www.bilibili.com/video/BV1GJ411x7h7`。

前台 iframe：

```
src="https://player.bilibili.com/player.html?bvid=BV1GJ411x7h7"
```

无 `style` 属性。浏览器 `document.querySelectorAll('[style]').length === 0`。截图：`artifacts/bilibili-article.png`。

```
SECURE_CSP["frame-src"] = ["'self'", "https://player.bilibili.com"]
```

### 4. 投稿全流程

用户 `submitter007@example.com`（验证邮箱后自动进「投稿者」+「校外用户」）。未登录 `/submit/` 显示「未登录」（`artifacts/submit-anon.png`）。登录后 `/submit/` → `/admin/pages/add/content/articlepage/4/`（`artifacts/submitter-admin-create.png`）。

本轮用该用户建草稿「007 投稿稿件」，`unpublish()` 后 `live=False`，工作流「内容审核」`start` → 状态 `in_progress`；内容编辑 `editor007@example.com` `approve` 后 `live=True`，前台 `/news/submit-007/` 200。首页「最新公告」和资讯列表都能看到（`artifacts/home.png`、`artifacts/news-list.png`）。

### 5. 投稿者后台菜单与直达网址

菜单只有「后台首页」「图片」（`artifacts/submitter-admin-home.png`、`artifacts/submitter-admin-create.png`）。首页有「我的投稿」和「新建投稿」，站点统计摘要已去掉。

直达响应码见上表。侧边栏 API 标题样例：`['M2 验收攻略', 'B站嵌入验收', '007 投稿稿件']`，不含内容编辑未发布稿。

### 6. 工作流邮件（worker 控制台）

`Task ... path=core.tasks.deliver_queued_email state=SUCCESSFUL`

提交审核 → 内容编辑：

```
To: editor007@example.com
Subject: [SJTU OW] 页面“007 投稿稿件”已提交到审核阶段“内容编辑审核”审批。

editor007@example.com 你好，

页面“007 投稿稿件”已提交到审核阶段“内容编辑审核”审批。

可以在此预览页面： http://localhost:8000/admin/pages/workflow/preview/15/2/
你可以在此编辑页面： http://localhost:8000/admin/pages/15/edit/

在此编辑通知选择 http://localhost:8000/admin/account/#tab-notifications
```

审核通过 → 投稿人：

```
To: submitter007@example.com
Subject: [SJTU OW] 页面“007 投稿稿件”已在工作流“内容审核”中批准。

submitter007@example.com 你好，

页面“007 投稿稿件”已在工作流“内容审核”中批准。
在这里查看页面： http://localhost:8000/news/submit-007/

在此编辑通知选择 http://localhost:8000/admin/account/#tab-notifications
```

### 7. 回归

未登录：`/me/`、`/me/game-accounts/`、`/me/contacts/`、`/me/security/` 均为 **302** → `/accounts/login/?next=…`。

已登录投稿者：上述四页 **200**（基本资料含「投稿」按钮；游戏 ID / 联系方式 / 账号安全页面正常）。

`/`、`/news/`、`/news/submit-007/` **200**。

`/healthz` **200**（worker 在跑）：

```
{"status": "ok", "checks": {"database": {"ok": true, "detail": "ok"}, "disk": {"ok": true, "detail": "free space 36.7%"}, "worker_heartbeat": {"ok": true, "detail": "ok (19s ago)", "affects_status": true}, "task_backlog": {"ok": true, "detail": "ok", "affects_status": true}}}
```

### 8. docker / caddy

```
Successfully built dd2b0592cadf
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

提交信息以 `007:` 开头。

## 设计偏差

1. **13.4 vs 5.4.3**：路由表写 `/submit/` 访问权限「已登录」，且「需要登录的页面未登录会跳登录页」。5.4.3 和本轮要求是未登录就地提示「未登录」。实现按 5.4.3，未做登录跳转。建议 13.4 把 `/submit/` 改成公开（未登录也可看原因）。
2. **无权限后台 URL**：Wagtail 8 是 302 到控制面板，不是 403。设置页会先 302 到实例再弹回。直达进不去目标功能，但状态码不是 403。
3. **控制面板搜索框**：Wagtail 8 把「Search all pages」和账号摘要写死在 `wagtailadmin/home.html`，`construct_homepage_panels` 清不掉。站点统计摘要已用钩子清掉。搜索走 explorer，结果仍受 `live | owner` 过滤。
4. **非 80/443 的 `Site.root_url`** 始终是 `http://`（Wagtail）。生产用 443/80 即可。

## 未完成 / 不同意

无。字体库、半静态渲染、AI 审核、战队/赛事/内战/开放 API 按范围不做。

## 顺带发现

- `construct_explorer_page_queryset` 在 Wagtail 8 **只**给搜索用。页面列表和侧边栏依赖 `explorable_instances`。只挂钩子不够，设计 14.3 可补一句。侧边栏实测**已过滤**，隐藏页面树菜单仍有必要（避免投稿者走 explorer 界面），但直达 `/admin/pages/` 仍会进过滤后的栏目列表。
- 内容 app 在 `INSTALLED_APPS` 里排在 `wagtail.admin` 前面，同 `order=0` 的 `construct_*` 钩子会先跑、再被 Wagtail 自己的钩子加回去。投稿者菜单/摘要钩子用了 `order=1000`。
- 投稿者账号按钮会显示邮箱（Wagtail 默认账号菜单），不是用户管理列表。
- 部分 Wagtail 自带文案仍是英文（「Search all pages…」、发布计划说明）。
- 新建页没有「发布」，只有「保存草稿」；页脚仍有 Wagtail 自带的 “publishing permissions” 英文说明。
- Cursor 内置浏览器对 `<a>` / 按钮的 click 常常只聚焦，Enter 才会提交或跳转。

## 需要确认

无。侧边栏过滤结果见上，交给 Claude 是否改 14.3 表述。

## 改动文件

嵌入与 CSP：`content/embeds.py`、`content/blocks.py`、`sjtu_ow/settings/base.py`。

站点与权限：`content/services.py`、`content/permissions.py`、`content/forms.py`、`content/models.py`、`core/management/commands/init_site.py`。

投稿入口与后台：`content/views.py`、`content/urls.py`、`content/wagtail_hooks.py`、`content/templates/content/submit.html`、`content/templates/content/admin/submitter_home.html`、`templates/base.html`、`templates/me/profile.html`。

组同步：`accounts/services.py`、`accounts/signals.py`。

测试：`content/tests/test_submissions.py`。

文档：`README.md`、`handoff/STATUS.md`、本报告与 `artifacts/*.png`。
