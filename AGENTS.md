# AGENTS.md

写给在这个仓库里干活的 AI 编码助手（Claude Code、Codex、Cursor、Grok……）和新接手的开发者。

上海交通大学守望先锋社区网站：Wagtail 8 + Django 6 + Python 3.13，SQLite（WAL），uv 管依赖。前台是服务端渲染 + HTMX + Alpine.js（CSP 构建），公开页面由 worker 预渲染成静态 HTML。

## 开工前按顺序读

1. **`handoff/STATUS.md`**：现在做到哪、下一步做什么、在等谁。**进度只写在这一个地方**
2. **`handoff/README.md`**：一轮工作怎么做，`request` / `report` / `review` 三份文件怎么写
3. **`docs/design.md` 里和本轮有关的章节**：设计依据。3400 多行，按目录找章节读，不用通读。**前台每一页、每个部件的细节**（显示什么、缺了怎么办、太长太多怎么办、谁能看到）在 `docs/design-details.md`，和 13.2 节一起是设计依据（092 起）
4. 按需读：`README.md`（怎么运行、怎么运维）、`handoff/REVIEW-GUIDE.md`（做独立复核时）、`handoff/rounds/<轮次>/`（某个功能当初为什么这样做）

## 目录

| 路径 | 内容 |
|---|---|
| `accounts/` | 用户、游戏 ID、段位、联系方式、功能权限（`permissions.can_use`） |
| `content/` | 页面类型、文章分类、投稿、B 站嵌入、sitemap / robots |
| `core/` | 全站设置、邮件、字体、预渲染、健康检查、备份恢复与运维命令 |
| `teams/` | 战队 |
| `members/` | 成员展示、成员分组（066 轮代替了原来的组队大厅） |
| `tournaments/` | 赛事、报名（`registration.py` 是状态机，含个人报名和临时队伍）、后台审核、`teams_admin.py` 队伍编排页 |
| `integrations/` | 只剩迁移历史。067 删了开放 API 与 Webhook；`tournaments/0004` 依赖它的迁移，包不能删 |
| `scrims/` | 内战、分队算法（`teaming.py`）、拖拽分队页 |
| `moderation/` | AI 内容审核 |
| `search/` | 站内搜索（四类内容的子串匹配） |
| `comments/` | 文章评论（YouTube 式回复串、隐藏、置顶、点赞） |
| `sjtu_ow/settings/` | `base` / `dev` / `prod` |
| `deploy/` | Docker Compose、Caddy、crontab 示例、维护页 |
| `handoff/` | 进度、轮次记录、复核指南 |

## 常用命令

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py createcachetable
uv run python manage.py init_site
uv run python manage.py tailwind runserver   # 另开终端：uv run python manage.py run_worker
```

每轮提交前必须全绿（和 CI 一致）：

```bash
uv run ruff check . && uv run ruff format --check .
uv run python manage.py tailwind build   # 测试要读 static/css/app.css，CI 也先编译
uv run pytest -q
uv run python manage.py makemigrations --check --dry-run
DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod \
  DJANGO_SECRET_KEY=ci-not-for-production-use-a-long-random-string-at-least-fifty-chars \
  FIELD_ENCRYPTION_KEY=ci-not-for-production DJANGO_ALLOWED_HOSTS=example.com \
  DJANGO_CSRF_TRUSTED_ORIGINS=https://example.com SITE_URL=https://example.com \
  DJANGO_SECURE_SSL_REDIRECT=true \
  uv run python manage.py check --deploy
```

**这组检查在测试机上跑**（2026-10-04 起，见「测试机与部署」）：

```bash
bash scripts/remote-check.sh                  # 整组，和 CI 一样（scripts/check.sh），pytest 按核数分片、镜像同时构建
bash scripts/remote-check.sh run uv run pytest -q core/tests/test_announcements.py
bash scripts/remote-check.sh run uv run python handoff/rounds/NNN-名字/mutate.py
bash scripts/remote-check.sh attach           # 本机这边断了，接着看最近一次
```

**登录后的页面截图**（146 起）：`bash scripts/remote-check.sh run uv run python scripts/screens.py 375`（宽度可换，比如 1280）。在测试机上用临时数据库建一套测试数据（成员、队长、战队、个人赛、整队赛、内战），起开发服务器，在服务器里直接给测试用户生成会话（不输入任何密码），用无头 Chromium 截个人中心、战队、赛事、内战等页面的整页图到 `/tmp/sjtu-ow-screens/out/`，再 `scp "[2a0e:6a80:3:9c7::]:/tmp/sjtu-ow-screens/out/*.png" 本机目录` 拿回来看。测试机上装了 `chromium` 和 `fonts-noto-cjk`；截图里文件选择框写「Choose File」是无头浏览器的语言，不是网站的问题。要加页面就改脚本里的 `PAGES`

**在真浏览器里走一遍新人的第一晚**（168 起）：`bash scripts/remote-check.sh run uv run python scripts/journey.py`。同样在测试机上建临时站点（用 `screens.py` 的种子数据），起开发服务器和 worker，用无头 Chromium 真的填注册表单（只在这个临时站点上用测试值）、从 worker 打到控制台的邮件里读验证码、验证、加游戏 ID 和联系方式、报内战、申请战队，最后看首页「我的安排」。浏览器报的错误、未捕获的异常、内容安全策略的拦截都打印出来并算失败，有一步没走通就退出码 1。测试直接调 Django 看不到的东西（脚本被拦、按钮没反应、区块没填上）靠它发现；改了这几个页面的表单或脚本后跑一次。**`journey.py pages`**（169 起）把项目自己的每个地址以访客、成员、站长（后台只用站长）在浏览器里打开一遍，报出浏览器报错和 500 的页面；后台拖拽编队、拖拽分队这类脚本多的页面只有它看得到。改了前端脚本或后台页面后跑一次。**`journey.py admin`**（170 起）走干部那一晚：再报 10 个人，在分队页勾满 10 人、生成分队、用卡片按钮把一人移到缓冲区再移回、保存；在队伍编排页用卡片按钮把 3 个散人编进新队伍、起名、保存。改了 `static/js/scrim-split.js`、`tournament-teams.js` 或这两个页面后跑一次

它把工作区（**包括没提交的改动**，不碰暂存区）做成一个提交、打成 git bundle 传上去，测试机检出的就是本机现在的样子（换行是 LF）。检查在服务器上脱离连接跑，本机每 3 秒取一次日志，退出码就是检查的结果；同一时间只跑一个，后来的排队。整组里 pytest 按核数分片、`docker build` 同时在后台构建，全部约 1 分半。本机只在测试机连不上时才跑这组检查。

改了错误页模板或 `static/css/error.css` 后跑 `uv run python manage.py render_error_pages` 并提交 `deploy/error_pages/`。改了 `core/placeholders.py`（占位图的画法和动画）后跑 `uv run python manage.py render_placeholders` 并提交 `static/img/placeholders/`。换了校徽文件 `static/img/sjtu-emblem.svg` 后跑 `uv run python manage.py render_emblem_layers` 并提交两张图层。改了网站图标的画法（`core/icons.py`，171 起，照 `static/img/favicon.svg` 的形状）后跑 `uv run python manage.py render_icons` 并提交 `static/img/` 下的 `favicon.ico`、`apple-touch-icon.png`、`icon-192.png`、`icon-512.png`；只改 SVG 不会自动跟着变。改了 `locale/` 下的 `.po`（后台中文，117 起）后跑 `uv run python manage.py compile_translations` 并提交 `.mo`。

## 测试机与部署

**测试机是 `2a0e:6a80:3:9c7::`（只有 IPv6），各种测试检查都在这台上跑。** 用户 2026-10-04：「各种测试检查放到 IP 为 185.99.135.224 的 vps 上进行，你可以搭建完整的工作测试流」，随后「测试机换到 IP 为 2a0e:6a80:3:9c7:: 的 vps 上。这台机子所有资源都由你掌控，请务必用满性能以达最高效率」。

| 项目 | 内容 |
|---|---|
| 机器（128 核对） | Debian 13，4 核 AMD EPYC 9275F，19 GB 内存，Docker 已装；146 装了 `chromium`、`fonts-noto-cjk`（截图用）。出 IPv4（GitHub、PyPI）走 Cloudflare WARP（`warp-svc`）。还跑着 Komari 监控探针（`komari-agent`） |
| 权限 | **整台机器归本项目用**，资源随便用；`warp-svc` 和 `komari-agent` 别停（前者断了就连不上 GitHub） |
| 登录 | SSH 密钥。登录用户和密钥在开发者本机的 `~/.ssh/config`（`Host 2a0e:6a80:3:9c7:: sjtu-ow-test`），**不写进仓库**（仓库是公开的）。`scp` 要给 IPv6 地址加方括号，`remote-check.sh` 自己处理 |
| 检查目录 | `/srv/sjtu-ow-check/`：`uv/`（uv 二进制，从 GitHub 发布页下载、核对过 sha256，缓存也在这里）、`repo/`（从 GitHub 克隆，每次检查切到传过来的快照）、`shards/1…4`（pytest 分片用的 worktree，各有自己的 `.venv` 和测试库）、`runs/`（每次检查的脚本、日志、退出码，留最近 30 次）、`lock`。Docker 里留一个 `sjtu-ow:check` 镜像，每次构建后删掉上一个 |
| 怎么用 | 本机 `bash scripts/remote-check.sh`，见「常用命令」。整组检查（含 `docker build`）约 1 分半，pytest 分 4 片、每片 40 秒左右 |
| 以后要部署测试站 | 照 README「生产 / 测试环境启动」：部署目录 `/srv/sjtu-ow`、Compose 项目名 `sjtu-ow-test`、每条命令带 `--env-file .env`。要 HTTPS 得有一个解析到这个 IPv6 地址的域名 |

**原来的测试机 `185.99.135.224`**（2026-09-18 起）重装过、没有 Docker，128 在上面搭过一次，换机器后把 `/srv/sjtu-ow-check` 删了，现在不用。上面有别人的东西（Komari 探针、`/opt` 和 `/root` 下的 Flutter、Android、FlClash 工具链），再上去也只动自己建的目录，不做全局清理。

### 第二台：169.58.217.180（用户 2026-10-03 指定，v6.0 起）

用户：「当前版本部署到 169.58.217.180 的 vps 上，端口使用 22887。不需要配置反代，我自己会配」。和测试机的区别：**本项目不占 80/443**，Caddy 只在 22887 上听 HTTP，域名和 HTTPS 由用户自己的反向代理负责。

| 项目 | 内容 |
|---|---|
| 登录 | `root`，SSH 密钥（开发者本机的 `id_ed25519`），Debian 12，Docker 29 / Compose v5 |
| 部署目录 | `/srv/sjtu-ow`；`.env` 权限 600，三把密钥在服务器上生成（`secrets.token_urlsafe`），没离开过服务器 |
| Compose | 项目名 `sjtu-ow`。**每条命令**：`docker compose -p sjtu-ow -f deploy/docker-compose.yml -f deploy/docker-compose.vps.yml --env-file .env` |
| 本机专用文件（不在仓库里） | `deploy/docker-compose.vps.yml`：`proxy` 的端口用 `!override` 换成 `22887:80`，站点地址 `:80`，挂 `Caddyfile.vps`；`deploy/Caddyfile.vps`：仓库 Caddyfile 的全局块（`admin off` 下面）加 `servers { trusted_proxies static private_ranges 100.96.0.0/12` 和 `trusted_proxies_strict }`（120 起），信任反代带来的 `X-Forwarded-Proto` 和访客 IP。另一个会话 2026-10-03 20:12（服务器时间）调过资源：`.env` 的 `GUNICORN_WORKERS=5`，`docker-compose.vps.yml` 给 `web` 加了 `cpu_shares: 2048`（CPU 争用时网站优先），改前的备份是同目录下的 `*.bak-202610032012` |
| 域名与反代（120 起） | `sjtu.ow-shanghaiuniversity.com` → CNAME `anylocate.cc`（`189.24.110.12`，用户自己的反向代理，**在另一台机器上**）→ 经 **Cloudflare WARP 内网**连到本机 22887，来源地址 `100.96.0.x`。所以 `Caddyfile.vps` 要信任 `100.96.0.0/12`，否则反代带来的 `X-Forwarded-Proto: https` 和访客 IP 会被 Caddy 丢掉 |
| `.env` 要点 | `DJANGO_ALLOWED_HOSTS=sjtu.ow-shanghaiuniversity.com,169.58.217.180,localhost`；`SITE_URL=https://sjtu.ow-shanghaiuniversity.com`；`DJANGO_CSRF_TRUSTED_ORIGINS=https://sjtu.ow-shanghaiuniversity.com,http://169.58.217.180:22887`（120 改，改前备份在服务器的 `/root/sjtu-ow-backups/`；备份里有密钥，别放在仓库目录里）。**域名不在 `ALLOWED_HOSTS` 里时，Django 生成的页面（后台、登录、成员个人页）全部 400，预渲染页照常**，看起来像「有些页面坏了」。改了 `SITE_URL` 要同步 Wagtail 站点地址（`content.services.sync_default_site_from_site_url()`）再全量 `prerender`。`DJANGO_SECURE_SSL_REDIRECT=false`（跳转由用户的反向代理做）；`TEST_ENVIRONMENT=1`（横幅、禁止抓取，用户说是正式站再关） |
| 定时任务 | `/etc/cron.d/sjtu-ow`（不碰 root 的 crontab）。服务器时区是 **Europe/Berlin**，cron 不支持 `CRON_TZ`，模板的北京时间按夏令时减 6 小时写 |
| 登录后台 | 生产设置的 Cookie 只走 HTTPS，**直接用 `http://IP:22887` 登录不了**，要等反向代理配好 HTTPS。管理员账号由用户自己建：`… exec web python manage.py createsuperuser` |
| 对外演示站（102 起） | 用户要的是「已经填入了测试数据的版本，作为对外的演示站」：库是本机演示库恢复过去的（40 个演示用户、7 支战队、21 篇文章、70 条评论，邮箱都是 `demo.example.com`，SMTP 没配），之后的补充都用脚本在服务器上直接跑（`handoff/rounds/102-demo-site/`），**不要再用备份整库覆盖**：会冲掉用户在服务器上建的管理员和改动。头像是 nekos.best 的动漫插画（用户选的，版权归画师，画师和出处记在图片说明里）；111 起偶数编号的 20 人按用户要求拿掉了头像、显示默认头像，原来的图片编号在服务器 `/root/avatars_removed.json` |

在服务器上跑一段脚本：`$C exec -T web python manage.py shell < /root/脚本.py`（`$C` 是上面那条 Compose 命令；Linux 上 Django 会把整段输入当脚本执行）。

**每轮升级**（120 起的做法，脚本在服务器 `/root/`，不在仓库里）：
1. 本机把改动的文件（`git status` 里除 `handoff/`、`docs/` 以外的）列成 `shipN.txt`、打成 `shipN.tar`，两个都传到 `/root/`
2. 跑 `sh /root/deploy_ship.sh N`：解包、去 CRLF、构建、迁移、重启、全量预渲染、健康检查。129 起它先检查 Compose 配置读不读得出来，读不出来就停
3. 提交推送以后跑 `sh /root/align_after_push.sh N`：**只把清单里的文件放回原样**，再 `git pull`

**服务器上有三样本机专用的未跟踪文件**：`deploy/docker-compose.vps.yml`、`deploy/Caddyfile.vps`、`.env.bak-*`，129 起写在服务器的 `.git/info/exclude` 里，`git status` 不再显示。**别按 `git status` 删未跟踪文件**：127 对齐时这样删，把 `docker-compose.vps.yml` 和它的备份一起删了（当时看的 `git status | head` 截掉了这两行），129 部署时构建、迁移、重启全失败（运行中的容器不受影响），照会话里读到过的内容恢复

**仓库的 `deploy/Caddyfile` 改了之后**，`Caddyfile.vps` 要跟着重新生成：它就是仓库那份在 `admin off` 下面插上一行说的 `servers` 块（105 用 `awk` 插入、`diff` 核对；120 起块里是两行：`trusted_proxies static private_ranges 100.96.0.0/12`、`trusted_proxies_strict`）；然后 `caddy validate`、`$C restart proxy`。升级后用 `docker images | grep sjtu-ow` 看一眼镜像时间：105 有一次 `build -q` 什么都没构建也没报错，容器跑的还是旧镜像

这台机器上还跑着 WordPress、HedgeDoc、FileCodeBox、相册和几个监控进程，规矩和测试机一样：只动 `/srv/sjtu-ow` 和 `sjtu-ow` 这个 Compose 项目，不做全局清理。升级照 README「生产 / 测试环境启动」，命令换成上面那条，升级后全量 `prerender`。

## 硬规则

1. **`docs/design.md` 是唯一设计依据。** 要改设计：需要用户拍板的先问；定了之后**先改文档再改代码**，在附录 D 记版本。实现和设计不一致时，要么改代码，要么改设计，不能两边各说各的
2. **按轮次工作**（流程见 `handoff/README.md`）：先写 `request.md`，再实现，写 `report.md`，再复核写 `review.md`，更新 `STATUS.md`，**一轮一个提交**，**直接推送到 `main`**（不开分支保护、不走合并请求，设计 17.5）。推送后看一眼 CI，红了优先修
3. **提交信息一律用中文。** 格式：第一行 `轮次号: 一句话说改了什么`（比如 `046: 提交信息改用中文`），空一行，正文说清楚为什么改、怎么验证的；最后的 `Co-Authored-By` 之类的署名行保持原样。045 及以前的提交是英文，不改写历史
4. **报告里只放真实跑过的命令输出。** 没跑的写「未验证」，不写推测结果
5. **不扩大本轮范围，不新增依赖。** 顺带发现的问题写进报告，留给下一轮；确实要加依赖，先停下来问，并确认它的许可证：MIT、BSD、Apache 可以，**GPL、AGPL 不行**（和本项目的 PolyForm Strict 许可证冲突，设计 17.8）
6. **分层**（设计 17.3）：业务逻辑写在各应用的 `services.py`；状态字段只能通过 service 函数改；邮件用 `transaction.on_commit` 入队；功能权限统一走 `accounts.permissions.can_use()`
7. **新加的每条规则都要有「拆掉它就会红」的测试。** 039–042 轮的变异测试发现，绿灯的测试经常根本没测到它该测的东西。写完测试，把对应的检查改坏跑一遍，确认会红，再改回来。批量检查可以用 `handoff/rounds/181-soft-guards/mutate_guards.py`（042 那份加上了 `comments`、`search`，181 起 `--soft` 只跑「`messages.error` / `add_error`」式的软拒绝；全部 254 个硬拒绝 3 个并行约 70 分钟，在测试机上单独开一个工作树后台跑，别占 `remote-check.sh` 的锁；软拒绝 26 个约 20 分钟，可以直接 `remote-check.sh run`）
8. **不提交**：`data/`、`backups/`、`media/`、`.env`、`static/css/app.css`（编译产物）。**密钥**（`DJANGO_SECRET_KEY`、`FIELD_ENCRYPTION_KEY`、`BACKUP_ENCRYPTION_KEY`、`MODERATION_API_KEY`）只放环境变量，不进数据库、不进仓库
9. **提交身份**用仓库本地 git 配置里的 `Uniseem`（GitHub noreply 邮箱），不要用个人姓名或邮箱提交，也不要改这项配置
10. **开发库**：不要一次性杀掉多个 worker 或其他写 SQLite 的进程（025 轮这样把开发库写坏过），一个一个 `kill -TERM`；不要直接删数据库文件，先移到别处

## 已知的坑

- **Alpine 是 CSP 构建**，HTML 属性里的表达式不会求值。交互用 `<details>` 或外部 JS 文件（020、032）
- **Wagtail 的兜底路由**让 `resolve()` 对任何路径都不抛异常。测地址存在要断言解析到的视图名（029）
- **字体切片必须可复现**：`TTFont(..., recalcTimestamp=False)`，否则同一个字体两次切出不同哈希（023）
- **邮件主题前缀由 `core.mail` 统一加**，业务代码写裸主题（026）
- **备份要找真正在用的数据库文件**：用 `core/dbfile.py` 的 `database_path()`，不是 `settings.DATABASE_PATH`（022）
- **计时测试在机器繁忙时会偶发失败**：6v6 分队 1 秒内、数据库被锁时 `/healthz` 1 秒内。并行跑测试或变异测试时注意（042）
- **`handoff/` 在 ruff 的排除列表里**（轮次报告要原样引用代码）。放在里面的脚本要指定路径单独检查
- **变异测试改回代码后**，如果文件大小和修改时间没变，Python 可能用旧的 `__pycache__`。改回后清一下缓存再跑（027）
- **预渲染**：从备份恢复后必须清空 `prerendered/`；开发环境默认关闭预渲染
- **别只用超级管理员测权限**：超级管理员能通过所有权限检查，用它测后台等于没测。至少要有一条用「能进后台、但不该有这个权限」的人（比如内容编辑）。059 补的测试里大约一半是这类（055 的内战管理员问题也是这样藏住的）
- **找「以后再接」的占位**：M2–M4 写代码时留了不少钩子和注释等后面的里程碑来接，已经发现四处没人回来接（055、056、059）。改一个功能时搜一下相关的 `M[0-9]`、「后续里程碑」、「placeholder」
- **只改模板时 `tailwind build` 会跳过**（「up to date」只看 CSS 入口文件）。模板里用了新的工具类，要 `tailwind build --force`，否则新类名不会进 `app.css`（065）
- **Wagtail 的富文本不包在 `.rich-text` 里**。按 `.rich-text p` 写的样式从 M2 起就没生效过，文章段落、列表一直没样式（065 修正）。给正文写样式，直接挂在外层容器（`.article-body p`）上
- **在 `web` 里跑通不等于 `worker` 能跑**：两个容器用同一个镜像，但挂的卷不一样。053 起全量预渲染都是 `exec web` 跑的，worker 缺静态卷、事件触发的生成全部失败，11 轮没人发现（064）。验证 worker 做的事（预渲染、邮件），要在服务器上触发一次、看结果
- **删应用之前先看迁移依赖**：`tournaments/0004` 依赖 `integrations/0001`。lfg 是叶子应用可以整个删（066），`integrations` 不行，067 只删代码，包和迁移文件留作墓碑，新迁移删表。以后要删应用先 `grep -rn "<app>" */migrations/`
- **Windows 上跑测试要设 `PYTHONUTF8=1`**：几条测试用 `read_text()` 不带编码读中文文件，系统默认 GBK 会解码失败；`tailwind build` 也会打印一条 `UnicodeDecodeError`，但 CSS 照样生成。测试里比较路径要用 `as_posix()`，`str(path)` 在 Windows 上是反斜杠（080）。CI 是 Linux，没这个问题（067）
- **前台组件是自己写的**（074 起，设计 13.2）：`assets/css/input.css` 里的 `c-*` 组件和 `l-*` 布局，模板只用语义颜色（`text-fg-2`、`border-rule`）。**Tailwind 自带的色板关掉了**，`bg-orange-500` 这种类不会生成；077 起不再加载 daisyUI，模板里写 `btn`、`badge` 之类会被测试拦下。新组件先写进设计 13.2.7，再加到样张页 `/_styleguide/`
- **Linux 容器里截图看不到苹方和 DIN**：只有文泉驿，截出来和访客看到的差很多。074 从 Google Fonts 的仓库下载 Noto Sans SC、Barlow，用 fontconfig 在扫描时注册成 `PingFang SC`、`DIN Condensed`（配置在 074 报告末尾）。`runserver --noreload` 不会重新读模板，改了模板要重启
- **表格放在网格或弹性布局里会被拉高**（074）：行高被撑开到和旁边一栏一样。`c-table` 已经设了 `align-self: start`，自己写的表格也要注意
- **变异测试前先确认测试本身是绿的**：变异脚本只看「改坏后红不红」，基线已经红的话，每处变异都会显示「被抓到」。083 就这样出过一轮假结果。084 起的 `mutate.py` 先跑一遍基线，红了直接停（083）
- **内置浏览器面板在后台时不渲染动画帧**：`requestAnimationFrame` 不回调、CSS 过渡停在起点，动效看起来像坏了（081，当时的 `motion.js` 在 086 删了）。截图和量尺寸更可靠的办法是用无头 Edge 的调试端口：`Emulation.setEmulatedMedia` 切深浅色、`Emulation.setDeviceMetricsOverride` 切手机宽度、`Page.captureScreenshot` 带 `captureBeyondViewport` 截整页（086）；站点禁止被 iframe 嵌入
- **无头 Edge 的探测脚本要按配置目录名关进程**（106）：`msedge.exe` 的启动进程马上就退出，`terminate()`、`taskkill /T` 都关不掉真正的浏览器。上一次的实例会一直占着调试端口，下一次探测连上的其实是它和它的旧缓存，106 因此一度得出错误结论（清掉 48 个残留进程）。每次用空闲端口、单独的 `--user-data-dir`，结束时按目录名找进程关掉（`handoff/rounds/106-page-transitions/loadbar_probe.py` 的 `kill_profile`）
- **调试工具在跳转进行时会压住对页面的读取**（106）：点了链接以后 `Runtime.evaluate` 要等新页面加载完才返回，读不到旧页上发生的事。要看旧页（比如加载条），在 `window` 上挂一个更晚执行的点击监听取消跳转
- **内置浏览器面板会跑旧脚本、不做预渲染**（106）：开发服务器发静态文件不带 `Cache-Control`，面板按启发式缓存，改了 JS 刷新后还是旧的（看调用栈的行号就知道）；它也关掉了 Speculation Rules 的预渲染。验证脚本和预加载用无头 Edge
- **深浅两套颜色**（086 起，091 可以手动切换）：深色值写在 `input.css` 的 `:root { @variant dark { … } }` 里，覆盖 `@theme` 的同名变量。加新颜色要两处都写，漏写深色的测试会红；模板里别写只在浅色下成立的东西（白底图、黑色文字）。**组件里区分模式只用 `@variant dark`**，直接写 `@media (prefers-color-scheme: dark)` 的话，访客在页头选了浅色或深色时不生效（有测试数这个词只出现一次）。截图测模式时，无头浏览器的 `Emulation.setEmulatedMedia` 只模拟系统设置；要测手动选择，在页面里设 `localStorage['ow-theme']` 或 `<html data-theme>`
- **Django 的 `default` 过滤器会先算参数**：`{{ members|default:team.member_count }}` 即使 `members` 有值也会求 `team.member_count`，列表里每一项多查一次数据库（088）。参数有代价时用 `{% if %}`
- **前端脚本里别用 `DOMParser` 解析带 `style=""` 的 SVG**（091）：解析出的文档沿用页面的内容安全策略，每个 `style` 属性都报一次违规（校徽有 50 条）。要拆 SVG 就用字符串处理（现在校徽在服务端由 `core/emblem.py` 拆）
- **Django 的 `{# #}` 注释只能写一行**（091）：跨行的 `{# … #}` 会原样显示在页面上，多行用 `{% comment %}`
- **Windows 上改了 Python 文件后 `tailwind runserver` 可能卡死**（090、091 各两三次）：进程还在、端口不再响应，或者干脆退出。重启开发服务器就好；变异测试这类连续改文件的脚本跑完先确认服务器还活着
- **`tailwind runserver` 会改写 `static/css/app.css`**（091）：它的监视进程在你改任何被扫描的文件（包括 `.py`）后重新编译出**不压缩、保留 CSS 嵌套**的版本，覆盖掉 `tailwind build` 的压缩版。读 `app.css` 的测试要两种写法都认；要确定性地跑全量测试，先 `tailwind build --force`，跑完之前别改文件。**最稳的是跑全量前停掉开发服务器**：096–098 里开发服务器卡死重启后，它的监视进程好几次在测试中途重写 `app.css`，`test_body_text_rules_match_what_wagtail_renders` 就红了
- **挂载的数据卷只能清空、不能删**（102 发现，103 修了）：Compose 里 `/app/media`、`/app/prerendered` 都是挂载点，`shutil.rmtree` 删光里面的文件后删目录本身时报 `Device or resource busy`。102 的 `restore` 就这样换好了数据库、上传文件却全没了。现在 `restore` 用 `empty_folder()` 只清内容，再 `copytree(..., dirs_exist_ok=True)`；以后写会碰这些目录的代码也一样，测试里的临时目录删得掉，测不出来（103 的测试把 `os.rmdir` 换成对这两个目录报错）
- **从 Windows 打包文件传到服务器会带 CRLF**（105）：本机工作区是 CRLF（仓库里是 LF），`tar` 原样打包。Caddy、Python 照样能读，但按行匹配的脚本（`awk '/^\tadmin off$/'`）会对不上，105 生成 `Caddyfile.vps` 时 `trusted_proxies` 就这样漏插了一次。传上去后 `sed -i 's/\r$//'`，或者等提交推送后在服务器上 `git pull`。**二进制文件不能这样去 CRLF**（171）：演示站的 `/root/deploy_ship.sh` 原来只跳过 png、webp、jpg、woff2、mo，`favicon.ico` 被删掉 3 个字节，浏览器拿到的是坏图标；现在按扩展名跳过常见的二进制类型，其余用 `grep -I`（有 NUL 字节才当二进制）判断
- **Windows 上别用 `manage.py shell < 文件`**（102）：Windows 的管道不支持 `select`，Django 退回交互式控制台逐行执行，函数和循环中间的空行会把语句截断，脚本只跑了一半还不报错退出。本机用 `manage.py shell -c "exec(open(r'路径', encoding='utf-8').read())"`；服务器（Linux）上 `<` 没问题
- **本机推送 403**（101）：本机 `gh` 登录了两个 GitHub 账号，当前激活的不是 `Uniseem` 时，`git push` 会被拒（Permission denied）。不要切换全局账号，只给这一次推送指定凭据：`git -c credential.helper= -c 'credential.helper=!f() { test "$1" = get && echo username=Uniseem && echo "password=$(gh auth token -h github.com -u Uniseem)"; }; f' push origin main`
- **Git Bash 的 heredoc 会吃掉一层反斜杠**（092）：在 Bash 工具里用 `python - << 'EOF'` 跑内联脚本时，脚本源码里写的两个反斜杠加 n 到 Python 那里只剩一个，替换进文件的就成了真换行；正则里的反斜杠也会少一层。091、092 几次把测试文件写坏（字符串字面量被拆成两行）。改文件用编辑工具，或者先把脚本写成 `.py` 文件再运行
- **到测试机的长连接可能被半路掐断**（128）：连原来那台 `185.99.135.224` 时，输出一直在走、开着保活，`ssh` 照样在 1 分 53 秒、5 分 08 秒被断开，两头都说是对方断的，服务器上跟着连接的进程一起被杀。所以 `remote-check.sh` 让检查在服务器上脱离连接跑（`setsid`），本机每 3 秒用短连接取一次日志。在远程机器上跑长任务都这样做，别 `ssh host 长命令`
- **`manage.py tailwind download_cli` 每次都重新下载**（144）：django-tailwind-cli 这个命令是强制下载（112 MB），原来 `check.sh` 和 Dockerfile 每次都调，GitHub 一返回 503，检查和部署都失败。现在 Dockerfile 在 `COPY . .` 之前用 `deploy/fetch_tailwind_cli.py`（带重试）下载固定版本，这一层能缓存；`check.sh` 只在文件不在时才下载。升级 `TAILWIND_CLI_VERSION` 时 Dockerfile 的 `ARG` 要一起改（有测试比对）
- **测试里的密码哈希是 MD5**（128，根目录 `conftest.py`）：网站用 Argon2，每次哈希要 100 MB、几十毫秒，测试建几百个用户和登录，换掉后 pytest 快了一倍半。要测和哈希有关的东西，在那条测试里自己设 `settings.PASSWORD_HASHERS`
- **测试库是固定文件 `data/test.sqlite3`**（128）：两个 pytest 不能在同一个目录里同时跑。`scripts/pytest-shards.sh` 给每个分片一个 git worktree（各自的库、`prerendered/`、`.venv`）
- **`page.get_url()`、`page.url` 不带请求，在循环里就是 N+1**（163）：Wagtail 每次都去缓存里读站点根路径，本站的默认缓存是数据库表，一次调用一次查询。列表里用 `{% pageurl %}`（模板里有请求）或 `page.get_url(request)`。搜索就这样每篇命中的文章多查一次
- **`ArticlePage.objects…` 别再 `.specific()`**（163）：拿到的已经是文章本身，`.specific()` 让 Wagtail 再取一遍，前面写的 `select_related` 也跟着丢了
- **量查询数时，数据要覆盖页面上的每一类内容**（163）：临时探测给搜索只放了战队，结论「平的」；正式守卫放了文章才发现每篇多两次查询。`core/tests/test_chapter15_audit.py` 的 `assert_no_n_plus_one` 比 3 份和 10 份数据
- **Wagtail 自带的复制页拿原对象预填表单**（159）：表单提交到新建地址时没事，但直接提交回复制地址的话，状态、发布时间这些不在表单里的字段会一起带进新的一条。本站的内战、赛事复制改成只照抄列出的字段新建对象（`core.services.copy_ahead`），别的模型要开复制也照这样做
- **编号一律过一道关**（166、167）：地址里写 `<id:pk>` 不写 `<int:pk>`（最多 18 位，有测试拦 `<int:`）；从表单或查询参数里取的编号用 `core.converters.as_id()`，不是编号就是 None。直接把 `request.POST.get(...)` 交给 `pk=` 的话，「abc」是 `ValueError`，20 位数字查一对一外键（Wagtail 页面）是 `OverflowError`，都是 500。`core/tests/test_garbage_input.py` 把全站地址乱填一遍，新加的页面出 500 它会红
- **Wagtail 的标题面板在表单里没有 slug 字段时会留一个空选择器**（169）：它照样挂上 `w-sync` 控制器，`data-w-sync-target-value` 是空的，浏览器里报「Error connecting controller」。投稿者的表单去掉了 slug（130），所以文章页用自己的 `content.panels.TitlePanel`。以后去掉别的页面的 slug 也要换这个面板
- **用了 `account/_form.html` 就别再自己写 `form.non_field_errors`**（168）：这个共用的表单片段已经显示整表单的错误，战队的申请、新建、管理页又写了一遍，同一句话显示两次。有测试拦
- **`querydict_from_html` 的两个坑**（159）：没写 `value` 的勾选框读出来是空字符串，Django 会当成没勾（浏览器发的是 `on`，测试里按 `checked` 改回 `on`）；Django 在 `<textarea>` 后面加一个换行，读出来的值开头多一个换行，比较前 `strip()`
- **别用一个短词断言页面里「没有」某样东西**（175）：`"cdn" not in html.lower()` 会碰上页面里的 CSRF 令牌、内容安全策略随机串，偶尔就红（171 的 CI 这样红过一次）。断言具体的结构，比如没有 `src="https://…"` 的 `<script>`
- **本地全绿不等于 CI 全绿**：CI 机器上没有 gitignore 掉的编译产物，磁盘、时区、速度也和本地不同。仓库 042 轮之前从没在 GitHub 上跑过 CI，第一次跑就红了三条（044）。推送后要看 CI 结果

## 改了什么，就更新哪份文档

**原则：一件事只写在一个地方，其他地方指过去。** 进度写在 `STATUS.md`，设计写在 `design.md`，用法写在 `README.md`。以前进度在三份文档里各写一遍，结果三份都过时了（043 轮修正）。

| 文档 | 管什么 | 什么时候更新 |
|---|---|---|
| `handoff/STATUS.md` | 进度：做到哪、下一步、在等谁、待用户拍板的事 | **每轮结束**：头部的 `round` / `next` / `updated`、「下次开工的第一件事」、里程碑表、轮次表加一行 |
| `handoff/rounds/<轮次>/` | 每轮的要求、报告、复核 | 开工前写 `request.md`，完工写 `report.md`，复核写 `review.md`。**写完不再改**；后来发现写错了，在原文对应位置加「NNN 轮更正」说明，不删原文 |
| `docs/design.md` | 设计：要做成什么样 | 设计变化时，先改文档再改代码，附录 D 记一行。**不写进度** |
| `README.md` | 怎么运行、怎么用、怎么运维 | 同一轮里改了命令、环境变量、后台入口或用户可见的行为时。**不写进度** |
| `handoff/REVIEW-GUIDE.md` | 给独立复核的人指路：哪里最可能还有问题 | 某轮改变了这个判断时（发现新的薄弱处、推翻旧结论） |
| `.env.example`、`deploy/crontab.example` | 环境变量、定时任务 | 新增或修改时 |
| `THIRD_PARTY_NOTICES.md` | 仓库里原样收录的第三方文件及其许可证 | 往 `static/vendor/` 之类的地方新增或升级第三方文件时 |
| `AGENTS.md`（本文件） | 工作方式、命令、硬规则、坑 | 流程或命令变了；踩到值得提醒后来者的新坑 |
