# 上海交通大学守望先锋社区网站

Django + Wagtail 站点。设计依据见 [`docs/design.md`](docs/design.md)，开发进度见 [`handoff/STATUS.md`](handoff/STATUS.md)。参与开发（包括用 AI 编码助手）先读 [`AGENTS.md`](AGENTS.md)。

本文件只讲怎么运行、怎么用、怎么运维，**不写进度**。

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
| 测试环境 | 与生产部署在同一台服务器上的另一套 Docker Compose 项目（例如 `-p sjtu-ow-test`），独立子域名、数据卷和数据库。配置 `EMAIL_ALLOWLIST`，只给名单里的邮箱发信。**设 `TEST_ENVIRONMENT=1`**：每个页面顶部显示「测试环境」横幅（预渲染的静态页也有），`robots.txt` 禁止全部抓取。 |
| 生产环境 | `sjtu_ow.settings.prod`。`PRERENDER_ENABLED=true`。静态资源收集到持久化 `static` 卷（只新增、不删除旧文件）。SMTP 在后台配置，不放环境变量。 |

复制 [`.env.example`](.env.example) 为 `.env` 后再启动 Compose。`DJANGO_SECRET_KEY` 和 `FIELD_ENCRYPTION_KEY` 必须单独备份。

## 生产 / 测试环境启动

下面是 053 轮在测试机上**实际走通**的步骤。测试机的信息见 `AGENTS.md`「测试机与部署」。

**每条 `docker compose` 命令都要带 `--env-file .env`**：Compose 默认去 `deploy/` 目录找 `.env` 来替换 `${CADDY_SITE_ADDRESS}`，找不到就用 `localhost`，Caddy 不会申请证书。容器里的环境变量则固定读仓库根目录的 `.env`（`env_file: ../.env`），所以**一份代码目录只能跑一套环境**，测试和正式要分开放两个目录。

```bash
cd /srv
git clone https://github.com/Uniseem/sjtu-ow.git
cd sjtu-ow
# 按 .env.example 写 .env：域名、SITE_URL、CADDY_SITE_ADDRESS（只写域名，不带 http://）。
# 三把密钥在服务器上随机生成，比如 openssl rand -base64 48，然后另外备份。
# 测试环境再加 TEST_ENVIRONMENT=1。
chmod 600 .env

C="docker compose -p sjtu-ow-test -f deploy/docker-compose.yml --env-file .env"   # 正式站用 -p sjtu-ow
$C build
# 先迁移再启动：worker 一启动就要读任务表
$C run --rm --no-deps web python manage.py migrate --noinput
$C run --rm --no-deps web python manage.py createcachetable
$C run --rm --no-deps web python manage.py init_site
$C up -d
$C exec web python manage.py createsuperuser
$C exec web python manage.py prerender
```

检查：

```bash
curl -I http://<域名>/          # 308 跳到 https://
curl https://<域名>/healthz     # 200，四项检查都是 ok
curl https://<域名>/robots.txt  # 测试环境只有 Disallow: /
```

Caddy 用 HTTP 验证自动申请 Let's Encrypt 证书，前提是 80 端口对外开放；HTTP 到 HTTPS 的跳转也是 Caddy 自动做的。

`web` 启动脚本会执行 `createcachetable` 和 `collectstatic --noinput`（没有 `--clear`，旧的带哈希文件会留在卷上）。`worker` 容器运行 `run_worker`（任务消费 + 心跳），**只读挂载 `static` 卷**：预渲染要读 `collectstatic` 的清单，读不到就每页都失败（064 之前就是这样）。升级时 worker 可能比 `web` 的 `collectstatic` 先渲染，所以它每次渲染前检查清单，变了就重新读。

**部署后验证 worker 做的事，要在测试机上真的触发一次**（改一篇内容，一分钟后看静态页变了没有），或看后台「半静态渲染」页有没有失败记录。在 `web` 里跑 `manage.py prerender` 成功，只能说明 `web` 的环境没问题。

三个服务都是 `restart: unless-stopped`：进程崩溃或服务器重启后会自己起来（054 在测试机上杀掉 Caddy 主进程验证过）。`web` 的健康检查是 `deploy/healthcheck.py`，它像 Caddy 一样带上站点域名和 `X-Forwarded-Proto: https` 去请求 `/healthz`；直接请求 `127.0.0.1` 会被 `ALLOWED_HOSTS` 拒成 400。

容器日志用 Docker 的 `json-file` 驱动轮转，每个容器最多 5 个 10MB 的文件，写满覆盖最旧的（设计 15.5）。看日志：`docker compose -p sjtu-ow-test -f deploy/docker-compose.yml --env-file .env logs --tail 100 web`。gunicorn 的访问日志记下的来源是 Caddy 的内网地址，**不含用户 IP**，Caddy 自己不记访问日志——隐私政策是这么写的，要改先改政策。

**定时任务**：模板是 `deploy/crontab.example`，改 `DC=` 那一行（正式站 `-p sjtu-ow`，测试环境 `-p sjtu-ow-test`）。Debian 12 默认**没装 cron**，而且它的 cron **不支持 `CRON_TZ`**，服务器时区一般又是 UTC，所以要把北京时间减 8 小时换算。测试机用的是独立文件 `/etc/cron.d/sjtu-ow-test`（不碰 root 的 crontab，这台机器上还有别的项目）：

```bash
apt-get install -y cron
# 按 crontab.example 写 /etc/cron.d/sjtu-ow-test：时间换成 UTC，每行在时间后面加一列用户名 root，
# 输出追加到 /var/log/sjtu-ow-test-cron.log。文件权限 644
journalctl -u cron | grep CMD      # 看任务有没有按时跑
```

停掉 `web` 后，Caddy 对会打到后端的请求返回维护页；已经生成的预渲染公开页面仍可访问。

`init_site` 创建全部预置用户组（交大用户、校外用户、内容编辑、赛事管理员、内战管理员、认证作者、投稿者），删除 Wagtail 自带的 Editors / Moderators，写入文章分类和页面树（首页、「资讯」、用户协议、隐私政策、关于我们），按 `SITE_URL` 设置 Wagtail 默认站点的主机名和端口（`https` 默认 443、`http` 默认 80，带端口时用给定端口），创建「内容审核」工作流并绑定到文章栏目，创建「投稿图片」集合，并为后台角色分配进入 Wagtail 的权限、为赛事/内战管理员分配查看联系方式的权限，以及各自管理赛事、内战的权限、为投稿相关角色分配栏目和图片权限。然后按「邮箱已验证且可以使用投稿功能」同步「投稿者」组成员，创建 9 个排版区域（默认系统字体）并生成初始字体样式表。命令可重复执行，不会改写已有成员关系（投稿者组除外）或已改过的分类名称：

```bash
uv run python manage.py init_site
```

## 注销账号与导出个人信息

个人中心「账号安全」页（`/me/security/`）有两个入口（设计 3.8）：

- **导出我的个人信息**（`/me/export/`）：下载 JSON，含账号、游戏 ID、联系方式、战队、入队申请、赛事和内战报名、所在的成员分组和职务、署名文章。每人每小时 5 次
- **注销账号**（`/me/delete/`）：输入当前密码。**队长要先转让或解散战队**。注销不删用户记录，而是匿名化：邮箱换成 `deleted-<ID>@deleted.invalid`、昵称改为「已注销用户」、删除游戏 ID 和联系方式、退出战队、取消内战报名、清空用户组；赛事报名的名单快照和署名文章保留。原邮箱可以重新注册

## 用户协议与隐私政策

草稿在 `content/legal/terms.md`、`content/legal/privacy.md`（060 轮起草，**【】里的内容要社团填写或决定**）。放在应用目录里而不是 `docs/`，是因为 `.dockerignore` 排除了 `docs/`，那样镜像里没有草稿。改完后发布到网站：

```bash
python manage.py load_legal_pages          # 页面还没有正文时写入
python manage.py load_legal_pages --force  # 覆盖后台里已有的正文
```

不加 `--force` 时，已经有正文的页面会跳过，不会覆盖在后台里改过的内容。

## 视觉风格与首页

风格照上海交大官网（设计 13.2 节）：交大红、米色、宋体、直角，只做浅色。颜色和形状都在 `assets/css/input.css` 的 daisyUI 主题 `sjtu` 和 `--sj-*` 变量里，模板只用语义类名。**不用交大的校徽、书法校名和照片**；页脚写明不是官方网站。

首页版式见设计 5.2 节。后台要维护的只有两处，都在「页面 → 首页 → 编辑」：

- **焦点图**：首页顶部的轮播，最多 6 张。每张填图片（横图，1600×700 以上）、标题、链接（选一个页面，或填以 `/` 开头的站内地址、`https://` 开头的站外地址）。一张都不填时，自动用最近 5 篇带封面的文章
- **置顶文章**：最多 3 篇，排在「社区要闻」最前面

图片新闻、赛事卡片、内战日历、战队都是自动取的。**文章有封面才会进焦点图和图片新闻**，发文章时尽量配一张横图。

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

## 成员展示

组队大厅在 066 轮按用户要求删除，换成成员展示（设计第 6 章）。

- `/members/` 公开、预渲染。列出所有**已加入**的用户：账号没停用，并且验证过邮箱。只显示昵称、所在分组和职务、所在战队；游戏 ID、段位、联系方式、邮箱都不显示
- **分组在后台「成员分组」里自定义**：名称、简介、是否显示、排序；同一个编辑页里添加成员（下拉框里显示「昵称（邮箱）」）、填职务、拖动排序。只能加已加入的用户，同一个人在一个组里只能出现一次
- 一个人可以在多个组，也可以不在任何组；所有人都在页面最后的「全部成员」里，按加入先后排列
- 超级管理员和内容编辑可以管理分组（`init_site` 分配权限）
- 分组、成员、昵称、邮箱验证、账号停用或注销、战队变化都会刷新这一页

**从有组队大厅的旧版本升级**：迁移会删掉车帖表和游戏模式表。之后跑一次下面的命令，清掉旧功能留下的内容类型和权限：

```bash
python manage.py remove_stale_contenttypes --include-stale-apps --noinput
```

**从有开放 API 的旧版本升级**（067 之前）：迁移会删掉 API 客户端、调用日志、Webhook 投递三张表，并清掉排队中的 Webhook 任务；`integrations` 包只剩迁移历史。之后同样跑一次上面的 `remove_stale_contenttypes`；测试机的 `/etc/cron.d/sjtu-ow-test` 里删掉每 10 分钟扫 Webhook 的那一行。

## 赛事

- `/tournaments/` 公开列表，按「报名中 / 即将开始报名 / 已截止 / 已结束」分组；草稿和已取消的不在列表里，已取消的详情页保留并显示「已取消」。
- 后台「社区 → 赛事」由赛事管理员和超级管理员管理：编辑全部字段，行内「更多」里可以发布、标记已结束、取消（取消要填说明，会通知已报名的队长）。
- 参赛人数下限大于全站战队人数上限时保存后给出警告；发布过的赛事不能删除，只能取消。
- 赛事页面进预渲染和 sitemap；报名开始和截止的时间点会自动排队重新生成。「报名入口」是占位区域，静态页里是「登录后报名」。
## 报名

- 队长在 `/tournaments/<id>/register/` 为**整支战队**报名，为每个队员选一个游戏 ID；页面上会先把每个人的问题标出来。
- 提交时在一个写事务里做 8 项校验（时间、队长身份、人数、资料完整、账号与权限、仅限交大、游戏 ID 归属、同赛事重复报名），**所有问题一次性列出**；数据库还有一条部分唯一约束兜底「同一赛事每人只能在一支战队的有效名单里」。
- 名单在提交时锁定：之后改昵称、段位、成员都不影响已提交的名单。队长可以在截止前「同步名单」，版本加 1、状态回到待审核。
- 状态机按设计 8.5：待审核 / 已通过 / 已驳回 / 已撤回。赛事管理员在后台审核；赛事打开「报名自动通过」时由系统在提交时通过（有报名之后这个开关不能再改，后台会拦）。驳回和撤销通过必须填备注；已驳回和已撤回的名单不占名额。
- 每次变化都写进只增不改的状态日志；队长和名单成员可以在 `/registrations/<id>/` 和 `/me/registrations/` 查看。
- 后台「社区 → 报名审核」：按赛事和状态筛选、批量通过、导出 CSV；详情页显示名单快照、与战队当前成员的差异、状态日志，操作按钮按报名当前状态显示。
- **联系方式只对有 `accounts.view_contactmethod` 权限的人显示**，导出带联系方式时会在 Wagtail 操作日志里留痕。
- **个人报名（散人池）**：赛事打开「开放个人报名」后，不是队长的用户在赛事页点「个人报名」，到 `/tournaments/<id>/signup/` 选游戏 ID、勾能打的位置（校验和队员一样：权限、资料完整、仅限交大、不在别的名单里；不要求段位）。赛事页公开人数、昵称和位置，不显示段位和游戏 ID；截止前可以改或取消；个人中心「我的报名」里也能取消。编队由赛事管理员在后台完成。
- **队伍编排（临时队伍）**：后台「社区 → 赛事」列表的「队伍编排」进入，把散人拖进队伍或用卡片上的按钮移动；满员拒绝拖入，低于下限标红但能保存；改队名、解散。保存即已通过：临时队伍是一条没有战队的报名记录，只出现在这个赛事的「已报名战队」里，标「临时队伍」。成员截止前可在报名详情页「退出队伍」回到散人池（赛事管理员收邮件），最后一人退出自动解散；编入、移出、解散都给成员发邮件。已在战队名单里的散人不能编入，卡片上会标出来。

## 内战

- 个人中心「我的内战」（`/me/scrims/`）列出自己报过的内战。删除游戏 ID 时，只有未结束的内战会拦住；已结束或已取消的内战里那条报名保留，游戏 ID 显示为「已删除」。
后台「社区 → 内战」创建活动，规格四选一：角色限定 5v5 / 6v6、不限位置 5v5 / 6v6。

- 状态 `draft` / `published` / `finished` / `cancelled`。**草稿在前台是 404**（不泄漏存在性），已取消的不在列表里但详情页保留并显示「已取消」。
- 列表显示已发布的，以及最近 30 天内已结束的。
- 报名截止时间留空表示开始前都能报。
- **发布后自动安排提醒任务**，开始前若干小时给报名者发邮件（小时数在「设置 → 全站设置 → 社区参数」里改，默认 2）。改了开始时间会重排，`reminder_sent_at` 保证只发一次。取消活动会邮件通知所有报名者。

报名规则：

- 必须选一个自己的游戏 ID，位置至少勾一个。
- **角色限定**：勾选的每个位置，在所选游戏 ID 上都要填了段位。
- **不限位置**：所选游戏 ID 至少有一个位置填了段位。
- 截止前可以改或取消。取消时如果已经被勾选上场或分过队，会自动移出，后台能看到「分队有变化」。
- 报名用到的游戏 ID 在活动结束前不能删除。

**前台不展示段位、游戏 ID 和分队结果**：名单只显示昵称和能打的位置。分队在后台做，管理员复制结果发到群里。

### 分队

后台内战列表的「分队」进入分队页：

1. 勾选本次上场的人，页面实时显示「已选 X / 需要 Y 人」，**人数正好时「生成分队」才可用**。
2. 生成后两队并排显示，下面有一块**缓冲区**（不上场）。角色限定规格下，**拖进哪个位置区就是分到哪个位置**。每张卡片上也有 A / B / 缓冲 按钮，效果和拖拽一样。总分和分差实时更新，不发请求。
3. **满员的队伍拖不进去**。要换人，先把队里的一个人拖到缓冲区，再把另一个人拖进来。
4. 位置人数不符合规格会标红，**但仍然允许保存**（管理员可能有特殊安排）。保存后留在缓冲区的人仍保持「已勾选上场」。
5. 「复制结果」下面的文本框全选复制，发到群里；`/admin/scrims/<id>/split/text/` 是同样内容的纯文本。

分队算法（设计 9.4）：角色限定规格穷举所有分法和每队的合法位置分配，按「两队总分差」→「各位置对位分差之和」两级评分取最小，并列时随机选一个（所以再点一次「生成分队」可能给出另一个等价方案）。不限位置规格取每人最高段位分，只均衡总分。6v6 最坏情况（12 人全能打三个位置）实测约 0.3 秒。

分队页的拖拽用 SortableJS，交互写在外部文件 `static/js/scrim-split.js` 里，**没有用 Alpine**——本站装的是 Alpine CSP 构建，属性里的表达式不会求值。

## AI 内容审核

站内内容（昵称、稿件、已发布的文章和普通页面）由 worker 送到大模型过一遍，疑似有问题的进后台「社区 → 内容审核」由管理员判断。

**AI 只有读取权限**：请求里不带任何工具、不带身份信息，模型唯一的产出是一条待复核记录；退回稿件、清空战队简介、停用账号等处置全部由管理员在对应功能里执行。

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

## 站内搜索

页头搜索框，或直接访问 `/search/?q=词`。搜文章（标题、摘要、正文）、赛事与内战（标题、说明）、战队（队名、简介）、成员（昵称）；只搜公开内容。多个词用空格隔开，每个词都要命中，中文按字面匹配，不分词。每类最多 20 条，每 IP 每分钟 30 次。结果页实时渲染，`robots.txt` 禁止抓取。

## 备份与恢复

```bash
uv run python manage.py backup                 # 备份到 BACKUP_ROOT，保留 14 天
uv run python manage.py backup --keep-days 30
uv run python manage.py restore backups/sjtu-ow-20260916-221549.tar.gz        # 只演练
uv run python manage.py restore backups/sjtu-ow-20260916-221549.tar.gz --yes  # 真的恢复
```

- 数据库用 **SQLite 的在线备份 API** 生成快照，不是复制文件——开了 WAL 的库直接复制可能拿到不一致的状态。
- 备份里有数据库和 `media`；`static` 和 `prerendered` 不备份，都能重新生成。
- **本地那份没有加密**，里面有用户邮箱和联系方式。没开异地备份时，命令每次都会提醒。
- **异地备份（Cloudflare R2 等 S3 兼容对象存储）**：在「设置 → 全站设置 → 异地备份」里填地址、存储桶、Access Key。开启之后每次备份会**先加密再上传**一份。
  - 加密密钥来自环境变量 `BACKUP_ENCRYPTION_KEY`，**不在数据库里**——放数据库里的话，密钥就在它保护的那份备份里，服务器整个丢了就等于打不开。和 `DJANGO_SECRET_KEY`、`FIELD_ENCRYPTION_KEY` 一起放密码管理工具。
  - 没设密钥就不会上传，不会把明文传出去。
  - 上传失败会让整条命令失败，不会让一次没送出去的备份看起来像成功了。
  - 上传成功后，删掉存储桶里超过保留天数（和本地同一个 `--keep-days`，默认 14）的本站备份。只删直接放在前缀下、名字是 `sjtu-ow-年月日-时分秒.tar.gz.enc` 的文件，同一个桶里别的东西不动。清理失败只警告，这次备份仍算成功。**API 令牌要有删除权限**（R2 选「对象读和写」），否则每次都会警告清理失败。
  - 从对象存储恢复：`manage.py restore --list-s3` 看有哪些，`manage.py restore --from-s3 <KEY> --yes` 下载解密并恢复。
- 恢复会：校验 `FIELD_ENCRYPTION_KEY` 能不能解开备份里的加密字段（**解不开就拒绝**，不然会恢复出一堆没人能读的密文）→ 关掉数据库连接 → 删除旧 WAL → 替换数据库文件 → 恢复 media → **清空 `prerendered`**（否则静态页面会比数据新）。
- 不加 `--yes` 只打印要做什么，什么都不改。
- 恢复前要先停 `web` 和 `worker`，恢复后启动并触发全量重新生成——这两步命令做不了，输出里有提示。

## 定时维护

```bash
uv run python manage.py cleanup_old_data   # 任务记录、已处理的 AI 审核记录、会话
uv run python manage.py cleanup_static     # 不属于当前版本且超过 30 天的静态文件
uv run python manage.py optimize_db        # PRAGMA optimize + WAL 检查点
```

`cleanup_old_data` 删已完成的任务记录（30 天）、过期会话，以及**已处理的** AI 审核记录（180 天）——`pending`（还没人复核过）的审核记录**一条都不删，不管多久以前**（设计 15.5）。加 `--dry-run` 只统计。宿主机 cron 的完整示例见 `deploy/crontab.example`。

`cleanup_static` 按 `staticfiles.json` 判断哪些文件还在用：**读不到清单就什么都不删**。升级后旧文件要留一个月，让还拿着缓存页面的访客能取到它引用的资源（设计 16.8）。

完整的 cron 时间表见 `deploy/crontab.example`。

## 健康检查

`GET /healthz` 在以下全部通过时返回 200，否则 503：

- 数据库可读写，数据盘剩余空间大于 20%
- worker 心跳在 2 分钟内更新过（worker 每 30 秒写一次缓存）
- 没有等待超过 10 分钟的就绪任务

数据库探活写入专用表 `HealthProbe` 后回滚，等待最多 200 毫秒；遇到 SQLite `database is locked` 视为正常忙碌（仍返回 200）。

Wagtail 后台 URL 前缀由设置 `ADMIN_URL_PREFIX`（默认 `/admin/`）控制，供 CSP 中间件识别后台请求。不要和 Wagtail 官方设置混淆。

## CI

使用 **GitHub Actions**（[`.github/workflows/ci.yml`](.github/workflows/ci.yml)），每次推送到 `main` 时执行：ruff、编译 Tailwind、pytest、`makemigrations --check`、生产配置下的 `check --deploy`、重新生成错误页后 `git diff` 必须为空、`docker build`。

Django 渲染的 404 / 403 / 429 / 500 引用 `static/css/error.css`。给 Caddy 的维护页是自包含 HTML（生成时把 `error.css` 内联进去），提交在 `deploy/error_pages/maintenance.html`。改错误页模板或 `error.css` 后运行：

```bash
uv run python manage.py render_error_pages
```

## 许可证

本项目按 [PolyForm Strict License 1.0.0](LICENSE.md) 授权。**这不是开源许可证**，简单说：

- **允许**：出于非商业目的使用本软件——个人学习、研究、测试、业余项目，以及教育机构、公益组织、政府机构等的使用
- **不允许**：分发本软件，修改本软件，或者基于它做新的作品
- **商业用途**不在授权范围内
- 法律规定的合理使用（比如为评论、说明问题适当引用）不受这份许可证限制

以上只是帮助理解的概括，以 `LICENSE.md` 原文为准。

`static/vendor/` 下的第三方文件不适用上面的许可证，按各自的许可证授权，见 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。

