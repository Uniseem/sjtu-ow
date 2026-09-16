# 上海交通大学守望先锋社区网站

Django + Wagtail 站点。设计依据见 [`docs/design.md`](docs/design.md)（v1.5.7）。M0–M2 已完成；**M3 战队与组队大厅**也已完成。下一个里程碑是 M4 赛事与报名。

## 技术栈

- Python 3.13，依赖用 [uv](https://docs.astral.sh/uv/) 管理
- Django 6.0、Wagtail 8.0、SQLite（WAL）
- 账号：django-allauth（邮箱登录、验证码注册 / 找回密码 / 改邮箱）
- 前台：Django 模板 + HTMX + Alpine.js（CSP 构建）+ Tailwind CSS v4 + daisyUI
- 样式由 `django-tailwind-cli` 编译，不安装 Node。源文件在 `assets/css/input.css`（不能放进 `STATICFILES_DIRS`，否则 WhiteNoise 哈希存储会处理 `@import "tailwindcss"` 并失败），编译结果在 `static/css/app.css`。
- 静态资源：WhiteNoise 存储后端（内容哈希 + 预压缩）；生产由 Caddy 直接提供
- 异步任务：Django Tasks + `django-tasks-db`；应用层发信走队列，由 worker 按后台 SMTP 发送
- 字体：fontTools + brotli 在 worker 里把字体切成带 `unicode-range` 的 WOFF2 分片，全部托管在本站
- 代码检查：ruff；测试：pytest + pytest-django

### 自托管前端脚本（不走 CDN）

| 文件 | 版本 | 来源 |
|---|---|---|
| `static/vendor/htmx.min.js` | 2.0.10 | [htmx v2.0.10](https://github.com/bigskysoftware/htmx/releases/tag/v2.0.10) |
| `static/vendor/alpine.csp.min.js` | 3.17.1 | npm `@alpinejs/csp` |
| `static/vendor/Sortable.min.js` | 1.15.6 | [SortableJS 1.15.6](https://github.com/SortableJS/Sortable/releases/tag/v1.15.6) |

前台不加载 Google Fonts 或其他网络字体：管理员可以在后台从 Google Fonts **下载**字体，下载后只使用本站保存的副本。

## 本地开发

需要 Python 3.13 和 [uv](https://docs.astral.sh/uv/getting-started/installation/)。

```bash
cd sjtu-ow
uv sync
uv run python manage.py migrate
uv run python manage.py createcachetable
uv run python manage.py init_site
uv run python manage.py createsuperuser
uv run python manage.py tailwind runserver
```

`tailwind runserver` 会编译 `static/css/app.css`（已 gitignore，不要提交）。只编译、不启动服务器可以用 `uv run python manage.py tailwind build`。首次 `tailwind` 命令会下载 Tailwind CLI Extra 二进制到 `.django_tailwind_cli/`（已 gitignore）。

**必须另开一个终端跑 worker。** 验证码、找回密码和改邮箱邮件都先入队，没有 worker 就不会发出去，`/healthz` 也会在心跳超过 2 分钟后返回 503：

```bash
uv run python manage.py run_worker
```

开发配置是 `sjtu_ow.settings.dev`：worker 把邮件打到控制台（仍走队列），默认关闭预渲染。缓存用数据库表（`createcachetable`），这样 web 进程能读到 worker 心跳。

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
```

提交前可以用 pre-commit（可选）：

```bash
uvx pre-commit install
```

### 后台配置 SMTP

1. 用超级管理员登录 `/admin/`（登录页就是前台 allauth 登录页）。
2. 打开 **设置 → 全站设置**。
3. 填写 SMTP 服务器、端口、加密方式（无 / STARTTLS / SSL）、账号、密码、发件地址、发件人名称、主题前缀。
4. 密码加密存储，表单不回显原值；留空表示不修改已保存的密码。
5. 点「发送测试邮件」：会同步发给当前管理员自己的邮箱，成功或失败原因直接显示在页面上。测试邮件不走队列。

本地开发不配 SMTP 也可以完成注册：worker 会把验证码打印到运行 `run_worker` 的终端。生产环境必须在后台配好 SMTP，不读环境变量。

`FIELD_ENCRYPTION_KEY` 用于加密 SMTP 密码。开发有默认值；生产必须在 `.env` 里单独设置并备份。

### 本地跑通注册

1. `migrate`、`createcachetable`、`init_site` 已执行。
2. 终端 A：`uv run python manage.py tailwind runserver`
3. 终端 B：`uv run python manage.py run_worker`
4. 打开 `/accounts/signup/`，填写邮箱、密码、昵称、是否来自交大，并分别勾选两项同意。
5. 在 worker 终端里找到 6 位验证码，在验证页提交。
6. 验证通过后会自动登录。之后可以退出、用「忘记密码」走验证码重置，或登录后在 `/accounts/email/` 修改邮箱（新邮箱验证通过后才替换）。

## 环境区别（设计文档 16.10 节）

| 环境 | 说明 |
|---|---|
| 本地开发 | `sjtu_ow.settings.dev`。邮件入队后由 worker 打到控制台。`PRERENDER_ENABLED` 默认 `false`，页面由 Django 实时渲染。 |
| 测试环境 | 与生产部署在同一台服务器上的另一套 Docker Compose 项目（例如 `-p sjtu-ow-test`），独立子域名、数据卷和数据库。配置 `EMAIL_ALLOWLIST`，只给名单里的邮箱发信。页面应显示「测试环境」横幅、`robots.txt` 禁止抓取（横幅和 robots 在后续里程碑落地）。 |
| 生产环境 | `sjtu_ow.settings.prod`。`PRERENDER_ENABLED=true`。静态资源收集到持久化 `static` 卷（只新增、不删除旧文件）。SMTP 在后台配置，不放环境变量。 |

复制 [`.env.example`](.env.example) 为 `.env` 后再启动 Compose。`DJANGO_SECRET_KEY` 和 `FIELD_ENCRYPTION_KEY` 必须单独备份。

## 生产 / 测试环境启动

先执行迁移（不要指望容器自动 migrate，升级流程见设计 16.8 节）：

```bash
cp .env.example .env
# 编辑密钥、域名、CADDY_SITE_ADDRESS
docker compose -f deploy/docker-compose.yml build
docker compose -f deploy/docker-compose.yml up -d
docker compose -f deploy/docker-compose.yml exec web python manage.py migrate
docker compose -f deploy/docker-compose.yml exec web python manage.py createcachetable
docker compose -f deploy/docker-compose.yml exec web python manage.py init_site
docker compose -f deploy/docker-compose.yml exec web python manage.py createsuperuser
```

`web` 启动脚本会执行 `createcachetable` 和 `collectstatic --noinput`（没有 `--clear`，旧的带哈希文件会留在卷上）。`worker` 容器运行 `run_worker`（任务消费 + 心跳）。

测试环境用独立项目名，避免和正式站抢数据卷：

```bash
docker compose -p sjtu-ow-test -f deploy/docker-compose.yml --env-file .env.test up -d
```

停掉 `web` 后，Caddy 对会打到后端的请求返回维护页；已经生成的预渲染公开页面仍可访问。

`init_site` 创建全部预置用户组（交大用户、校外用户、内容编辑、赛事管理员、内战管理员、认证作者、投稿者），删除 Wagtail 自带的 Editors / Moderators，写入文章分类和页面树（首页、「资讯」、用户协议、隐私政策、关于我们），按 `SITE_URL` 设置 Wagtail 默认站点的主机名和端口（`https` 默认 443、`http` 默认 80，带端口时用给定端口），创建「内容审核」工作流并绑定到文章栏目，创建「投稿图片」集合，并为后台角色分配进入 Wagtail 的权限、为赛事/内战管理员分配查看联系方式的权限、为投稿相关角色分配栏目和图片权限。然后按「邮箱已验证且可以使用投稿功能」同步「投稿者」组成员，创建 9 个排版区域（默认系统字体）并生成初始字体样式表。赛事/内战权限在后续里程碑写入。命令可重复执行，不会改写已有成员关系（投稿者组除外）或已改过的分类名称：

```bash
uv run python manage.py init_site
```

## 字体与排版

「设置 → 字体库」添加字体（上传文件 / 从 Google Fonts 下载 / 从网址下载），worker 用 fontTools 把字体切成 WOFF2 分片，浏览器只下载页面用到的分片。「设置 → 排版设置」为 9 个区域（正文、一至四级标题、导航栏、按钮、数字与数据、游戏 ID 与代码）分别设置字体、字重、字号、行高和字间距，保存后生成 `media/fonts/css/fonts.<哈希>.css`，全站布局在 `<head>` 里引用它。两个页面都只对超级管理员开放。

- 模板里不写字体名称，只用 `assets/css/input.css` 里的 `--font-*` 变量和 `.font-nav` / `.font-button` / `.font-numeric` / `.font-code` 类。
- 处理一个中文字重要几十秒到几分钟，队列同一时间只处理一个字重。
- 被排版区域引用的字体不能删除。

## 半静态渲染

公开页面（首页、资讯列表、文章、普通页面）由 worker **以未登录访客的身份**预先渲染成静态 HTML，放在 `prerendered` 数据卷里，由 Caddy 直接返回，不经过 Django。页面里因人而异的部分（账号区域、操作提示等）留成占位，加载后用一次 `/_fragments/state/` 请求补上。

- **未登录访客不发这个请求**：`<head>` 里的 `static/js/state.js` 只在 `ow_logged_in` / `ow_flash` 两个提示 Cookie 存在时才发请求，两个 Cookie 都不含身份信息。
- **静态文件只是加速层**：文件不在就由 Django 实时渲染，同时排一个生成任务，结果一样。
- 开关：`PRERENDER_ENABLED`（生产默认开，开发默认关）；目录：`PRERENDER_ROOT`（默认 `prerendered/`）。
- 后台「设置 → 静态页面」可以看生成情况、重新生成单页或全部、清空全部静态文件。

```bash
uv run python manage.py prerender            # 全量生成
uv run python manage.py prerender --path /news/hello/
uv run python manage.py prerender --list
uv run python manage.py prerender --clear    # 清空，网站回落到实时渲染
```

宿主机 cron（设计 16.5，北京时间）：

```
CRON_TZ=Asia/Shanghai
15 4 * * * docker compose -f /srv/sjtu-ow/deploy/docker-compose.yml exec -T web python manage.py prerender
```

**从备份恢复数据后必须清空预渲染目录**（`manage.py prerender --clear` 或后台按钮），否则静态页面会比数据库更新。升级版本不需要清空。

## 战队

- `/teams/` 战队列表（可只看招募中）、`/teams/<id>/` 战队主页（公开，不显示成员的游戏 ID）、`/teams/<id>/manage/` 战队管理（只有队长能看，显示成员和申请人的游戏 ID）。
- 创建战队要有 `team_create` 功能权限，每人最多同时担任 3 支战队的队长（「设置 → 全站设置」里可调）；申请入队要有 `team_apply` 权限和至少一个游戏 ID。
- 限流：创建每人每天 3 次、申请每人每天 20 次。
- 解散是软删除：历史报名仍然引用这支战队，队名可以被新战队使用。
- 后台「社区 → 战队」：超级管理员可以查看、编辑、指定队长、解散。
- 战队页面进预渲染和 sitemap；「申请加入」按钮是占位区域，未登录访客看到的是「登录后申请」。

## 组队大厅

- `/lfg/` 是**静态外壳**：导航和筛选栏预渲染，车帖列表由 HTMX 请求 `/​_fragments/lfg/`，登录检查在列表请求里做，所以静态文件里没有任何车帖数据。
- 列表每 30 秒自动刷新；开车时间在浏览器里显示成相对时间（`<time datetime>`），游戏 ID 旁边有复制按钮。
- 发车要有 `lfg_post` 权限和至少一个游戏 ID；每人同时最多 3 个未过期车帖，过期时间 = 开车时间 + 2 小时（都在「设置 → 全站设置」里调）。限流每人每小时 10 次。
- 过期不靠定时任务，只靠列表的查询条件过滤。
- 后台「社区 → 车帖」可以查看并关闭违规车帖；游戏模式在「游戏模式」里维护。

## AI 内容审核

站内内容（昵称、稿件、已发布的文章和普通页面）由 worker 送到大模型过一遍，疑似有问题的进后台「社区 → 内容审核」由管理员判断。

**AI 只有读取权限**：请求里不带任何工具、不带身份信息，模型唯一的产出是一条待复核记录；关闭车帖、退回稿件、停用账号等处置全部由管理员在对应功能里执行。

- 默认接 DeepSeek 的 OpenAI 兼容接口，模型在「设置 → 全站设置」里改（默认 `deepseek-v4.1-flash`）。
- 环境变量：`MODERATION_API_KEY`、`MODERATION_BASE_URL`（自建或聚合平台时填）、`MODERATION_EXTRA_BODY`（一段 JSON，比如关闭思考模式的参数，原样并进请求体）、`MODERATION_TIMEOUT`、`MODERATION_MAX_OUTPUT_TOKENS`。
- **没配密钥就不送审**，不会产生「无法判定」的噪音。后台还可以整体关掉。
- 省钱措施：短内容一次最多合并 20 条、相同文本 30 天内不重复送审、每天调用上限（默认 2000）、后台显示本月调用次数和估算花费。

```bash
uv run python manage.py moderate_scan               # 全量扫描现有内容
uv run python manage.py moderate_scan --what pages --limit 50
uv run python manage.py moderate_scan --digest      # 发送每日汇总邮件
```

宿主机 cron（每天一封汇总）：

```
CRON_TZ=Asia/Shanghai
30 9 * * * docker compose -f /srv/sjtu-ow/deploy/docker-compose.yml exec -T web python manage.py moderate_scan --digest
```

## 健康检查

`GET /healthz` 在以下全部通过时返回 200，否则 503：

- 数据库可读写，数据盘剩余空间大于 20%
- worker 心跳在 2 分钟内更新过（worker 每 30 秒写一次缓存）
- 没有等待超过 10 分钟的就绪任务

数据库探活写入专用表 `HealthProbe` 后回滚，等待最多 200 毫秒；遇到 SQLite `database is locked` 视为正常忙碌（仍返回 200）。

Wagtail 后台 URL 前缀由设置 `ADMIN_URL_PREFIX`（默认 `/admin/`）控制，供 CSP 中间件识别后台请求。不要和 Wagtail 官方设置混淆。

## CI

使用 **GitHub Actions**（[`.github/workflows/ci.yml`](.github/workflows/ci.yml)）：ruff、pytest、`makemigrations --check`、生产配置下的 `check --deploy`、重新生成错误页后 `git diff` 必须为空、`docker build`。

Django 渲染的 404 / 403 / 429 / 500 引用 `static/css/error.css`。给 Caddy 的维护页是自包含 HTML（生成时把 `error.css` 内联进去），提交在 `deploy/error_pages/maintenance.html`。改错误页模板或 `error.css` 后运行：

```bash
uv run python manage.py render_error_pages
```
