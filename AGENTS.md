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

改了错误页模板或 `static/css/error.css` 后跑 `uv run python manage.py render_error_pages` 并提交 `deploy/error_pages/`。改了 `core/placeholders.py`（占位图的画法和动画）后跑 `uv run python manage.py render_placeholders` 并提交 `static/img/placeholders/`。换了校徽文件 `static/img/sjtu-emblem.svg` 后跑 `uv run python manage.py render_emblem_layers` 并提交两张图层。

## 测试机与部署

**测试机是 `185.99.135.224`，部署先放在这台机器上。** 用户 2026-09-18 指定。

| 项目 | 内容 |
|---|---|
| 域名 | `sjtu.ow-shanghaiuniversity.com`，经 CNAME 指向一个线路优化服务，最终解析到 `185.99.135.224`。模拟交大、国内、海外来源查询，结果都是这个 IP（050 轮核对） |
| 权限 | **助手拥有这台机器的全部权限**，可以直接部署、改配置、重启服务 |
| 登录 | SSH 密钥登录。登录用户和密钥位置在开发者本机的 SSH 配置里，**不写进仓库**（仓库是公开的） |
| 部署目录 | `/srv/sjtu-ow`（和 `deploy/crontab.example` 里的路径一致）。`.env` 在服务器上，权限 600，密钥是在服务器上生成的 |
| Compose | 项目名 `sjtu-ow-test`。**每条命令都带 `--env-file .env`**，完整步骤见 `README.md`「生产 / 测试环境启动」 |
| 证书 | Caddy 自动申请和续期，走 **HTTP 验证**，不用 DNS 验证。前提是 80 端口对外开放；`CADDY_SITE_ADDRESS` 填域名本身（不带 `http://`），Caddy 才会申请证书 |
| 跳转 | **HTTP 必须自动跳转到 HTTPS**。站点地址是域名时 Caddy 默认会做，部署后要实测：`curl -I http://sjtu.ow-shanghaiuniversity.com/` 应返回跳转到 `https://` 的 3xx |

**机器上还跑着别的项目**（另一套 Docker Compose 和一个监控探针）。只动 `/srv/sjtu-ow` 和本项目的 Compose 项目：

- 不停、不重启、不删别人的容器、网络和数据卷
- **不要**执行 `docker system prune`、`docker volume prune` 这类全局清理
- 本项目的 Caddy 会占用 80 和 443 端口。以后这台机器上别的网站要用域名访问，得经过这个 Caddy 转发

### 第二台：169.58.217.180（用户 2026-10-03 指定，v6.0 起）

用户：「当前版本部署到 169.58.217.180 的 vps 上，端口使用 22887。不需要配置反代，我自己会配」。和测试机的区别：**本项目不占 80/443**，Caddy 只在 22887 上听 HTTP，域名和 HTTPS 由用户自己的反向代理负责。

| 项目 | 内容 |
|---|---|
| 登录 | `root`，SSH 密钥（开发者本机的 `id_ed25519`），Debian 12，Docker 29 / Compose v5 |
| 部署目录 | `/srv/sjtu-ow`；`.env` 权限 600，三把密钥在服务器上生成（`secrets.token_urlsafe`），没离开过服务器 |
| Compose | 项目名 `sjtu-ow`。**每条命令**：`docker compose -p sjtu-ow -f deploy/docker-compose.yml -f deploy/docker-compose.vps.yml --env-file .env` |
| 本机专用文件（不在仓库里） | `deploy/docker-compose.vps.yml`：`proxy` 的端口用 `!override` 换成 `22887:80`，站点地址 `:80`，挂 `Caddyfile.vps`；`deploy/Caddyfile.vps`：仓库 Caddyfile 的全局块加 `servers { trusted_proxies static private_ranges }`，信任同机反向代理带来的 `X-Forwarded-Proto` |
| `.env` 要点 | `DJANGO_ALLOWED_HOSTS=169.58.217.180,localhost`、`SITE_URL` 和 `DJANGO_CSRF_TRUSTED_ORIGINS` 是 `http://169.58.217.180:22887`（**用户给了域名后要加上域名并改成 https**，然后 `up -d`）；`DJANGO_SECURE_SSL_REDIRECT=false`（跳转由用户的反向代理做）；`TEST_ENVIRONMENT=1`（横幅、禁止抓取，用户说是正式站再关） |
| 定时任务 | `/etc/cron.d/sjtu-ow`（不碰 root 的 crontab）。服务器时区是 **Europe/Berlin**，cron 不支持 `CRON_TZ`，模板的北京时间按夏令时减 6 小时写 |
| 登录后台 | 生产设置的 Cookie 只走 HTTPS，**直接用 `http://IP:22887` 登录不了**，要等反向代理配好 HTTPS。管理员账号由用户自己建：`… exec web python manage.py createsuperuser` |
| 对外演示站（102 起） | 用户要的是「已经填入了测试数据的版本，作为对外的演示站」：库是本机演示库恢复过去的（40 个演示用户、7 支战队、21 篇文章、70 条评论，邮箱都是 `demo.example.com`，SMTP 没配），之后的补充都用脚本在服务器上直接跑（`handoff/rounds/102-demo-site/`），**不要再用备份整库覆盖**：会冲掉用户在服务器上建的管理员和改动。头像是 nekos.best 的动漫插画（用户选的，版权归画师，画师和出处记在图片说明里） |

在服务器上跑一段脚本：`$C exec -T web python manage.py shell < /root/脚本.py`（`$C` 是上面那条 Compose 命令；Linux 上 Django 会把整段输入当脚本执行）。

这台机器上还跑着 WordPress、HedgeDoc、FileCodeBox、相册和几个监控进程，规矩和测试机一样：只动 `/srv/sjtu-ow` 和 `sjtu-ow` 这个 Compose 项目，不做全局清理。升级照 README「生产 / 测试环境启动」，命令换成上面那条，升级后全量 `prerender`。

## 硬规则

1. **`docs/design.md` 是唯一设计依据。** 要改设计：需要用户拍板的先问；定了之后**先改文档再改代码**，在附录 D 记版本。实现和设计不一致时，要么改代码，要么改设计，不能两边各说各的
2. **按轮次工作**（流程见 `handoff/README.md`）：先写 `request.md`，再实现，写 `report.md`，再复核写 `review.md`，更新 `STATUS.md`，**一轮一个提交**，**直接推送到 `main`**（不开分支保护、不走合并请求，设计 17.5）。推送后看一眼 CI，红了优先修
3. **提交信息一律用中文。** 格式：第一行 `轮次号: 一句话说改了什么`（比如 `046: 提交信息改用中文`），空一行，正文说清楚为什么改、怎么验证的；最后的 `Co-Authored-By` 之类的署名行保持原样。045 及以前的提交是英文，不改写历史
4. **报告里只放真实跑过的命令输出。** 没跑的写「未验证」，不写推测结果
5. **不扩大本轮范围，不新增依赖。** 顺带发现的问题写进报告，留给下一轮；确实要加依赖，先停下来问，并确认它的许可证：MIT、BSD、Apache 可以，**GPL、AGPL 不行**（和本项目的 PolyForm Strict 许可证冲突，设计 17.8）
6. **分层**（设计 17.3）：业务逻辑写在各应用的 `services.py`；状态字段只能通过 service 函数改；邮件用 `transaction.on_commit` 入队；功能权限统一走 `accounts.permissions.can_use()`
7. **新加的每条规则都要有「拆掉它就会红」的测试。** 039–042 轮的变异测试发现，绿灯的测试经常根本没测到它该测的东西。写完测试，把对应的检查改坏跑一遍，确认会红，再改回来。批量检查可以用 `handoff/rounds/042-guard-sweep/mutate_guards.py`
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
- **深浅两套颜色**（086 起，091 可以手动切换）：深色值写在 `input.css` 的 `:root { @variant dark { … } }` 里，覆盖 `@theme` 的同名变量。加新颜色要两处都写，漏写深色的测试会红；模板里别写只在浅色下成立的东西（白底图、黑色文字）。**组件里区分模式只用 `@variant dark`**，直接写 `@media (prefers-color-scheme: dark)` 的话，访客在页头选了浅色或深色时不生效（有测试数这个词只出现一次）。截图测模式时，无头浏览器的 `Emulation.setEmulatedMedia` 只模拟系统设置；要测手动选择，在页面里设 `localStorage['ow-theme']` 或 `<html data-theme>`
- **Django 的 `default` 过滤器会先算参数**：`{{ members|default:team.member_count }}` 即使 `members` 有值也会求 `team.member_count`，列表里每一项多查一次数据库（088）。参数有代价时用 `{% if %}`
- **前端脚本里别用 `DOMParser` 解析带 `style=""` 的 SVG**（091）：解析出的文档沿用页面的内容安全策略，每个 `style` 属性都报一次违规（校徽有 50 条）。要拆 SVG 就用字符串处理（现在校徽在服务端由 `core/emblem.py` 拆）
- **Django 的 `{# #}` 注释只能写一行**（091）：跨行的 `{# … #}` 会原样显示在页面上，多行用 `{% comment %}`
- **Windows 上改了 Python 文件后 `tailwind runserver` 可能卡死**（090、091 各两三次）：进程还在、端口不再响应，或者干脆退出。重启开发服务器就好；变异测试这类连续改文件的脚本跑完先确认服务器还活着
- **`tailwind runserver` 会改写 `static/css/app.css`**（091）：它的监视进程在你改任何被扫描的文件（包括 `.py`）后重新编译出**不压缩、保留 CSS 嵌套**的版本，覆盖掉 `tailwind build` 的压缩版。读 `app.css` 的测试要两种写法都认；要确定性地跑全量测试，先 `tailwind build --force`，跑完之前别改文件。**最稳的是跑全量前停掉开发服务器**：096–098 里开发服务器卡死重启后，它的监视进程好几次在测试中途重写 `app.css`，`test_body_text_rules_match_what_wagtail_renders` 就红了
- **挂载的数据卷只能清空、不能删**（102 发现，103 修了）：Compose 里 `/app/media`、`/app/prerendered` 都是挂载点，`shutil.rmtree` 删光里面的文件后删目录本身时报 `Device or resource busy`。102 的 `restore` 就这样换好了数据库、上传文件却全没了。现在 `restore` 用 `empty_folder()` 只清内容，再 `copytree(..., dirs_exist_ok=True)`；以后写会碰这些目录的代码也一样，测试里的临时目录删得掉，测不出来（103 的测试把 `os.rmdir` 换成对这两个目录报错）
- **Windows 上别用 `manage.py shell < 文件`**（102）：Windows 的管道不支持 `select`，Django 退回交互式控制台逐行执行，函数和循环中间的空行会把语句截断，脚本只跑了一半还不报错退出。本机用 `manage.py shell -c "exec(open(r'路径', encoding='utf-8').read())"`；服务器（Linux）上 `<` 没问题
- **本机推送 403**（101）：本机 `gh` 登录了两个 GitHub 账号，当前激活的不是 `Uniseem` 时，`git push` 会被拒（Permission denied）。不要切换全局账号，只给这一次推送指定凭据：`git -c credential.helper= -c 'credential.helper=!f() { test "$1" = get && echo username=Uniseem && echo "password=$(gh auth token -h github.com -u Uniseem)"; }; f' push origin main`
- **Git Bash 的 heredoc 会吃掉一层反斜杠**（092）：在 Bash 工具里用 `python - << 'EOF'` 跑内联脚本时，脚本源码里写的两个反斜杠加 n 到 Python 那里只剩一个，替换进文件的就成了真换行；正则里的反斜杠也会少一层。091、092 几次把测试文件写坏（字符串字面量被拆成两行）。改文件用编辑工具，或者先把脚本写成 `.py` 文件再运行
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
