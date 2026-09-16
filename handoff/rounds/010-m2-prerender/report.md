# 010 实现报告

> 用户外出期间由 Claude 实现 + 自查。

## 结论

T1–T8 已完成：公开页面由 worker 以未登录访客身份预渲染成静态 HTML（带 `.br` / `.gz`），Caddy 直接返回；个人相关区域用一次 `/_fragments/state/` 片段请求补上；**未登录访客一个额外请求都不发**。发布 / 改网址 / 撤回都会实时更新或删除静态文件。179 个测试通过。

## 逐条结果

### T1 数据表

`PrerenderedPage`（`core/migrations/0006_prerendered_page.py`）：`path` 唯一、`kind`、`status`、`requested_at`、`generated_at`、`content_hash`、`bytes`、`error`，字段按设计 12.4.6。

### T2 生成器（`core/prerender.py`）

- 用 `django.test.Client` 以**干净的匿名请求**渲染（无 Cookie、无会话），`SERVER_NAME` 取 Wagtail 默认站点的主机名，`secure` 按端口判断，走的是线上同一套视图和模板。
- 写 `<目录>/<路径>/index.html`，同时写 brotli（质量 11）和 gzip（级别 9，`mtime=0` 保证同内容同字节）；每个文件都是**先写临时文件再 `os.replace`**。
- 内容哈希没变、且文件还在，就不重写。
- **安全闸门**三道：响应带任何 `Set-Cookie` → 拒绝；正文里出现 `csrfmiddlewaretoken` / `csrf_token` / `sessionid` → 拒绝；非 200 或非 HTML → 拒绝。拒绝时写 `error`，不产出文件。
- 404 / 410 单独处理：说明这个地址已经不再公开，**直接删文件和记录**，不留「生成失败」让管理员排查（设计已补）。

### T3 任务与合并

- `prerender_page(path)` / `prerender_all()` / `remove_prerendered(path)` 三个任务。
- 合并：`request_page()` 记 `requested_at` 并排一个 30 秒后的任务；30 秒内的再次请求直接并进去（返回 `False`）。
- 兜底：`PrerenderMissMiddleware` 在「匿名 + GET + 无查询参数 + 200 HTML + 属于公开页面清单 + 文件不存在」时排一个生成任务；出任何异常只记日志，不影响页面。
- `PRERENDER_ENABLED` 为关时，所有入口直接返回，不碰磁盘也不排队。

### T4 触发事件（`content/signals.py`）

`page_published` / `page_unpublished` / `page_slug_changed` / `post_page_move` / `Page` 的 `post_delete` / `ArticleCategory` 的 `post_save`：

- 发布、修改 → 该页 + 资讯列表 + 首页
- 撤回、删除 → **立刻删**该页文件，再刷新列表和首页
- 改网址、移动 → 立刻删旧地址，生成新地址
- 分类改名 → 列表页 + 该分类下的全部文章
- 字体样式表变化（保存排版设置）→ 全量重新生成（`regenerate_font_css()` 里触发）

### T5 页面状态片段

- `GET /_fragments/state/?slots=account,messages`，一次返回全部占位区域，都是 `hx-swap-oob="true"`。
- 服务端维护已知占位区域清单（`account`、`messages`、`home-lfg`），**清单外的名字忽略**，方便模板先留位、功能后接（首页的赛事 / 内战 / 文章三个 `data-slot` 就是这种情况）。
- `Cache-Control: private, no-store`，`Vary: Cookie`；调用 `get_token()` 确保 `csrftoken` Cookie 存在（预渲染页面里没有 token）。
- 会话已失效但还带着 `ow_logged_in` 时，返回未登录内容并删除这个提示 Cookie。
- 限流 120 次 / 分钟 / IP，超了返回 429 + `Retry-After: 60`。IP 取 `X-Forwarded-For` 的最后一段（Caddy 记的来访 IP），没有这个头就用 `REMOTE_ADDR`。

### T6 提示 Cookie 脚本

`static/js/state.js`，`<head>` 同步加载，**未压缩 1182 字节**（gzip 后约 0.5KB）。两个 Cookie 都没有就直接返回；有就先给 `<html>` 加 `ow-state-pending`（占位区显示骨架，样式在 `input.css` 里），DOM 就绪后收集页面上所有 `data-slot` 名字，用 HTMX 发一次请求，填完去掉骨架。脚本失败时页面保持未登录内容，链接照常可用。

### T7 后台「设置 → 静态页面」

超级管理员可见：是否开启、已生成页数、最近生成时间、失败列表和原因、磁盘占用和目录；按钮：全部重新生成、清空全部静态文件；每行一个「重新生成」。

### T8 命令与文档

- `manage.py prerender`（默认全量）、`--path`、`--list`、`--clear`、`--force`（`PRERENDER_ENABLED` 为关时也执行）。
- README 加「半静态渲染」一节：开关、目录、命令、cron 示例（`CRON_TZ=Asia/Shanghai`，每天 04:15）、**从备份恢复后必须清空**。
- 设计补了 009 遗留的「被替换的字体分片延迟一天删除」（13.12.2），并按本轮结果更新到 **v1.5.6**。

## 验收输出

### 1. 检查与测试

```
$ uv run ruff check . && uv run ruff format --check .
All checks passed!
157 files already formatted

$ uv run python -m pytest -q
180 passed in 12.45s

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod ... uv run python manage.py check --deploy
System check identified no issues (0 silenced).
```

本轮新增 23 个测试（`core/tests/test_prerender.py`）：生成三件套文件、同内容不重写、全量覆盖、**扫描全部生成文件不含 CSRF / 会话 / 邮箱 / 已登录账号区**、404 直接删记录、真实失败会留记录、清空、发布排队、撤回删除、改 slug 删旧地址、30 秒合并、开关为关时不动作、片段接口未登录 / 已登录 / 响应头 / 清理失效提示 Cookie / 忽略未知占位 / 限流、`ow_flash` 的设置与清除、兜底排队、已登录不排队、后台只对超级管理员开放、后台清空。

### 2. 全量生成

```
$ PRERENDER_ENABLED=true uv run python manage.py prerender --force
全量生成完成：成功 8，失败 0，删除 0；目录占用 62 KB
```

```
prerendered/index.html                        4715 字节
prerendered/index.html.br                     1299
prerendered/index.html.gz                     1743
prerendered/news/index.html
prerendered/news/m2-first-guide/index.html
prerendered/news/bilibili-007/index.html
prerendered/news/submit-007/index.html
prerendered/about/index.html
prerendered/privacy/index.html
prerendered/terms/index.html
（每个目录下都有对应的 .br 和 .gz）
```

Caddy 真机验证（把 `prerendered/` 挂进 `caddy:2.10-alpine`，用仓库里的 Caddyfile）：

```
$ curl -sI http://localhost:8099/
HTTP/1.1 200 OK
Cache-Control: public, max-age=0, must-revalidate
Etag: "dlgob4v935i35ss"
Content-Type: text/html; charset=utf-8

$ curl -sI -H "Accept-Encoding: br" http://localhost:8099/news/m2-first-guide/
Content-Encoding: br
Content-Length: 1299

$ curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8099/me/            → 502（转给 Django，容器里没有 web，符合预期）
$ curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:8099/news/?category=guide" → 502（带查询参数也转给 Django）
```

即：静态命中直接由 Caddy 返回并带 ETag 和预压缩；`/me/` 和带查询参数的请求不会被静态文件截胡。

### 3. 浏览器（**真的经过 Caddy**）

把 `prerendered/` 挂进 `caddy:2.10-alpine`，用仓库里的 Caddyfile，`--add-host web:host-gateway` 指向本机 Django（`0.0.0.0:8000`），浏览器访问 `http://localhost:8099`。这样静态命中真的由 Caddy 返回，`/_fragments/` 真的转给 Django。

**未登录**（`/news/`，Caddy 返回静态文件）：

```js
{fragments: 0, filled: "0", account: "登录 注册"}
```

**一个 `/_fragments/` 请求都没有**，控制台 0 条报错。

**登录后**（同一个静态文件）：

```js
{fragments: ["http://localhost:8099/_fragments/state/?slots=account,messages"],
 filled: "0",
 account: "静态验收 个人中心 退出",
 cookies: "ow_logged_in=1; csrftoken=…",
 html: ""}
```

页面本身仍然是那份匿名生成的静态文件（`filled="0"`），登录用户只发**一次**片段请求就把账号区域换成了昵称，骨架类在填充后移除。

**实时渲染页**（`/me/`，登录状态）：

```js
{fragments: 0, filled: "1", account: "静态验收 个人中心 退出"}
```

Django 已经按登录身份渲染好了，脚本看到 `data-state-filled="1"` 就不发请求（见「设计偏差 5」）。

在 dev 直连（无 Caddy）时，首页占位更多，片段请求会带上全部名字，服务端只回它认识的三个：

```js
{requests: ["slots=account,messages,home-articles,home-tournaments,home-scrims,home-lfg"],
 lfg: "组队大厅 登录后查看 进入组队大厅", account: "片段验收 个人中心 退出"}
```

### 4–5. 发布 / 改网址 / 撤回（worker 真跑）

```
已发布 /news/prerender-live/
静态文件生成：True（33s）          ← 30 秒合并窗口 + worker 轮询
记录: ready 4460 字节 article
含 csrf/session/邮箱: False
含未登录账号区: True

改 slug → /news/prerender-live-2/
旧地址已删除：True（3s）| 新地址已生成：True（30s）

撤回发布
静态文件已删除：True（3s）
```

### 6. 安全扫描

```
$ grep -rl "csrfmiddlewaretoken\|sessionid\|@example.com" prerendered/
（无输出）
```

自动化测试里也有同样的扫描，另外还检查了「退出」这类只有登录用户才会看到的字样。

### 7. 回归

```
/                       200      /news/        200
/news/m2-first-guide/   200      /about/       200
/submit/                200      /healthz      200
/admin/settings/fonts/  302（未登录）
```

`/healthz` 里 worker 心跳正常；后台字体库、排版设置、静态页面三个页面都能打开。

### 8. docker / caddy

```
Successfully built e16fb1d7d554
Valid configuration
```

### 9. 清理

验收账号 `state010@example.com`、`static010@example.com` 已删除；验收文章已删除；`prerendered/` 里留着 8 个页面的静态文件（目录已 gitignore）；本机 dev 服务器和 worker 恢复成默认（`PRERENDER_ENABLED` 关）。

## 设计偏差

已写进 `docs/design.md` v1.5.6：

1. **占位区域清单在服务端维护**，页面用 `data-slot` 自动上报，清单外的名字忽略。设计 13.13.3 只列了占位区域表，没说没实现的占位怎么办。
2. **404 / 410 视为「已不再公开」**：删文件和记录，不留「生成失败」。设计只写了「生成失败记录原因」。
3. **限流取 `X-Forwarded-For` 最后一段**。设计附录 C 只写了「每个 IP」，没写反向代理后面怎么取 IP。注意：allauth 那几个限流仍然用 `REMOTE_ADDR`，本轮没动（不在范围内），上线前要一起处理。
4. `ow_flash` 的判定用「这次响应新加了提示、但没有显示出来」，即提交后跳转的场景；设计只说「有待显示的操作提示时设置」。
5. **实时渲染的页面不再发片段请求**：`<body data-state-filled="1">` 表示这份 HTML 是 Django 按当前登录身份渲染的，占位区域已经正确，脚本直接跳过。预渲染文件里这个值永远是 `0`。设计 13.13.3 只说「已登录用户只发一次请求」，没区分静态页和实时页——不跳过的话，`/me/` 这类页面每次都会多一次没有意义的请求。

## 未完成 / 不同意

1. **只接了 M2 现有的页面**（首页、资讯列表、文章、普通页面）。赛事 / 战队 / 内战 / 组队大厅的预渲染和它们的占位区域，等各自的里程碑接进来——`page_targets()` 和 `STATE_SLOTS` 都是一处加一行的事。
2. **每天 04:15 的 cron 只写进了 README**，没有在仓库里放 crontab 文件（部署方式是 docker compose，crontab 属于宿主机配置）。
3. **升级后触发一次全量生成**没有自动化（设计 13.13.4 提到），目前靠运维手动执行 `manage.py prerender`，README 已写。

## 顺带发现

1. `init_site` 发布页面树时会触发 `page_published`，于是第一次初始化就会排好预渲染任务——符合预期，但写测试时要注意记录已经存在。
2. Caddy 的 `try_files {path}/index.html` 对根路径 `/` 也能正确命中 `prerendered/index.html`（实测），不用为首页单独写规则。
3. `ArticlePage` 的摘要字段叫 `summary`（不是 `excerpt`），`author` 由 `owner` 派生。
4. HEAD 请求带 `Accept-Encoding: br` 时 Caddy 返回 206 + `Content-Encoding: br`，是 curl 的 range 行为，不是配置问题。

## 需要确认

1. allauth 的限流现在用 `REMOTE_ADDR`，在 Caddy 后面会把所有人算成同一个 IP。要不要在上线前统一改成读 `X-Forwarded-For`？（需要同时确认只信任自己的代理。）
2. 预渲染目录的清理策略：目前只在「全量生成」时删掉不再存在的页面。要不要也加一个每天的孤儿文件清理？

## 改动文件

新增：`core/prerender.py`、`core/prerender_admin.py`、`core/ratelimit.py`、`core/migrations/0006_prerendered_page.py`、`core/templates/core/prerender/index.html`、`core/management/commands/prerender.py`、`content/signals.py`、`templates/slots/{account,messages,home_lfg}.html`、`static/js/state.js`、`core/tests/test_prerender.py`。

修改：`core/models.py`、`core/tasks.py`、`core/views.py`、`core/urls.py`、`core/middleware.py`、`core/wagtail_hooks.py`、`core/fonts/css.py`、`content/apps.py`、`content/templates/content/home_page.html`、`templates/base.html`、`assets/css/input.css`、`sjtu_ow/settings/base.py`、`README.md`、`docs/design.md`、`handoff/STATUS.md`。
