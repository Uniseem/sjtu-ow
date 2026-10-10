# 开发与验收

运行检查、构建、浏览器验收、截图或变异验证前读对应小节。机器连接与操作边界见 [operations.md](operations.md)，新栈前台的完成标准见 [frontend-migration.md](frontend-migration.md)。

## 验收纪律

所有编译和测试先走测试机，单条 Go 命令也一样；只有测试机连不上才可本机兜底，报告写明原因。所有检查放助手工具的后台任务，日志写文件；等候时继续独立工作，不用 sleep 循环轮询。测试机同一时间只跑一组，对拍别连续重复排队。报告只引用真实输出，没跑的写「未验证」。

**新加的每条规则都要有「拆掉它就会红」的测试。** 039–042 轮的变异测试发现，绿灯的测试经常根本没测到它该测的东西。写完测试，把对应的检查改坏跑一遍，确认会红，再改回来。批量检查可以用 `handoff/rounds/181-soft-guards/mutate_guards.py`（042 那份加上了 `comments`、`search`，181 起 `--soft` 只跑「`messages.error` / `add_error`」式的软拒绝；全部 254 个硬拒绝 3 个并行约 70 分钟，在测试机上单独开一个工作树后台跑，别占 `remote-check.sh` 的锁；软拒绝 26 个约 20 分钟，可以直接 `remote-check.sh run`）

## 工具链与整组内容

**新栈的命令和检查**（222 起，`server/` 立起来了）：在 `server/` 目录里 `gofmt -l .`（应为空）、`go vet ./...`、`staticcheck ./...`、`govulncheck ./...`、`go test ./...`；这些已经并进 `scripts/check.sh` 的「Go（新栈）」一段，测试机上 `remote-check.sh` 整组自动带上。不用 `golangci-lint`（GPL-3.0，AGENTS.md 的依赖限制）。工具链装在测试机 `/srv/sjtu-ow-check/` 下（222 轮装好，安装脚本在本轮目录）：`go/`（**1.26.9**，242 轮从 1.26.8 升——govulncheck 报 net/http 等 9 项 GO-2026-6617 要 1.26.9 修；本机是 brew 的更新版，`go.mod` 的 go 指令记测试机这版）、`node24/`（24.13）、`gobin/`（staticcheck 2026.2.1 / v0.8.1、govulncheck v1.8.0）、`gopath/ gocache/ gomodcache/`（缓存也在这块盘）；**系统自带的 Node 20 没动**，`remote-check.sh` 的任务脚本自己把这些导进 PATH（注意 npm、pnpm 的 shebang 是 `/usr/bin/env node`，用它们前必须把 `node24/bin` 放进 PATH 最前）。231 起 `web/` 的检查是 `pnpm install --frozen-lockfile` 然后 `pnpm test`（pnpm 11.20.0），写在 `scripts/check.sh` 的「Web（新栈）」一段，和 CI 的 web 任务同一句。

整组还运行 `sjtuow apigen` 并比较 `web/packages/api/src/gen/`，命令的执行事实以仓库 [check.sh](../scripts/check.sh) 和 [CI](../.github/workflows/ci.yml) 为准。下列逐项命令用于理解整组，不构成本机执行授权。

## 整组入口

从仓库根目录在助手后台任务运行 `bash scripts/remote-check.sh`，这是每轮提交前的入口。它同步工作区后执行测试机上的 `scripts/check.sh`。Django 本地启动见 [旧站手册](legacy-guide.md)「本地开发」，不属于当前整组。

每轮提交前必须全绿（和 CI 一致，229 起只跑新栈）：

```bash
cd server
test -z "$(gofmt -l .)"
go vet ./...
staticcheck ./...
govulncheck ./...
go test ./...
cd ../web
pnpm install --frozen-lockfile
pnpm test
```

现行站冻结。pytest、ruff、迁移、生产配置、错误页、Docker 镜像不进每次推送，测试机上的整组也不跑。前端这一段要先有 `node24/bin` 在 PATH 最前。

## 前台浏览器

**前台 SSR 在真浏览器里过一遍**（233 起）：`bash scripts/remote-check.sh run bash -c 'cd web/apps/site && node browser-check.mjs /usr/bin/chromium'`（本机 Chrome 就把路径换成 `/Applications/Google Chrome.app/...`）。它起桩 API 和生产 SSR 服务（`STRICT_CSP=1` 时服务自己加 CSP 响应头）、用 CDP 驱动无头 Chromium 走激活、严格 CSP 零违规、SPA 换页、主题、右键菜单、无脚本横幅、404；要在跑它的前一步先构建（整组里 `pnpm test` 就构建了）。改了前台入口、壳或这些行为后跑一次；截图落在仓库检出里（gitignore 了）。

## 新旧对拍与 Caddy

**和旧站逐页对拍**（264 起，`docs/frontend-migration.md` 9.2）：`bash scripts/remote-check.sh run bash e2e/parity/run.sh [--only=前缀,…] [--wide] [--strict]`。旧站用 `scripts/screens.py` 的种子数据建临时库，新站 `sjtuow import` 同一个库、`import-media` 同一个媒体目录、`session` 发会话，按正式站的样子跑（Go + SSR 生产构建 + 真 Caddy 容器），逐个「地址 × 身份」比状态、标题、正文、链接、表单、坏图、截图像素差；报告在测试机 `/tmp/sjtu-ow-parity/out/`。约 6 分钟，不进整组；做完一组页面时用 `--only=那一组 --strict` 证明「对拍通过」。改了 Caddy 跑 `e2e/caddy/smoke.sh`（263）。

**这组检查在测试机上跑**（2026-10-04 起，见 [机器与运维](operations.md)）：

```bash
bash scripts/remote-check.sh                  # 整组，和 CI 一样（scripts/check.sh）：只跑新栈
bash scripts/remote-check.sh run uv run python handoff/rounds/NNN-名字/mutate.py
bash scripts/remote-check.sh attach           # 本机这边断了，接着看最近一次
```

## 旧站截图与旅程

**登录后的页面截图**（146 起）：`bash scripts/remote-check.sh run uv run python scripts/screens.py 375`（宽度可换，比如 1280）。在测试机上用临时数据库建一套测试数据（成员、队长、战队、个人赛、整队赛、内战），起开发服务器，在服务器里直接给测试用户生成会话（不输入任何密码），用无头 Chromium 截个人中心、战队、赛事、内战等页面的整页图到 `/tmp/sjtu-ow-screens/out/`，再 `scp "sjtu-ow-test:/tmp/sjtu-ow-screens/out/*.png" 本机目录` 拿回来看（`sjtu-ow-test` 是本机 SSH 别名，见 [机器与运维](operations.md)）。测试机上装了 `chromium` 和 `fonts-noto-cjk`；截图里文件选择框写「Choose File」是无头浏览器的语言，不是网站的问题。要加页面就改脚本里的 `PAGES`

**在真浏览器里走一遍新人的第一晚**（168 起）：`bash scripts/remote-check.sh run uv run python scripts/journey.py`。同样在测试机上建临时站点（用 `screens.py` 的种子数据），起开发服务器和 worker，用无头 Chromium 真的填注册表单（只在这个临时站点上用测试值）、从 worker 打到控制台的邮件里读验证码、验证、加游戏 ID 和联系方式、报内战、申请战队，最后看首页「我的安排」。浏览器报的错误、未捕获的异常、内容安全策略的拦截都打印出来并算失败，有一步没走通就退出码 1。测试直接调 Django 看不到的东西（脚本被拦、按钮没反应、区块没填上）靠它发现；改了这几个页面的表单或脚本后跑一次。**`journey.py pages`**（169 起）把项目自己的每个地址以访客、成员、站长（后台只用站长）在浏览器里打开一遍，报出浏览器报错和 500 的页面；后台拖拽编队、拖拽分队这类脚本多的页面只有它看得到。改了前端脚本或后台页面后跑一次。**`journey.py admin`**（170 起）走干部那一晚：再报 10 个人，在分队页勾满 10 人、生成分队、用卡片按钮把一人移到缓冲区再移回、保存；在队伍编排页用卡片按钮把 3 个散人编进新队伍、起名、保存。改了 `static/js/scrim-split.js`、`tournament-teams.js` 或这两个页面后跑一次

它把工作区（**包括没提交的改动**，不碰暂存区）做成一个提交、打成 git bundle 传上去，测试机检出的就是本机现在的样子（换行是 LF）。检查在服务器上脱离连接跑，本机每 3 秒取一次日志，退出码就是检查的结果；同一时间只跑一个，后来的排队。整组内容以 `scripts/check.sh` 为准；旧站 pytest 分片和 Docker 构建不在当前整组里。**所有编译和测试一律先在测试机上做**（用户 2026-10-08 写死的规矩）：不止这组整组检查，新栈单条 `go test`、`go build` 也走 `remote-check.sh run`；本机只在测试机连不上时才跑（这组检查和新栈的命令都一样），并在报告里写明。

**所有测试和检查都放到后台跑，别让对话卡住**（用户 2026-10-07：「所有的测试都后台运行，不要被卡住」）：`remote-check.sh` 整组、单条 `run`、变异脚本、`journey.py`、截图、真环境演练，一律用助手工具的后台运行（Claude Code 的 `run_in_background`），输出写到文件，跑完等完成通知再读结果；等的时候接着做不依赖结果的事（写报告、改文档、准备下一步）。不要前台阻塞地等，也不要用 `sleep` 循环轮询。几个检查有先后依赖时，串成一条后台命令按顺序跑（测试机同一时间只跑一个，后来的本来就排队）

## 旧站生成资源

改了错误页模板或 `static/css/error.css` 后跑 `uv run python manage.py render_error_pages` 并提交 `deploy/error_pages/`。改了 `core/placeholders.py`（占位图的画法和动画）后跑 `uv run python manage.py render_placeholders` 并提交 `static/img/placeholders/`。换了校徽文件 `static/img/sjtu-emblem.svg` 后跑 `uv run python manage.py render_emblem_layers` 并提交两张图层。改了网站图标的画法（`core/icons.py`，171 起，照 `static/img/favicon.svg` 的形状）后跑 `uv run python manage.py render_icons` 并提交 `static/img/` 下的 `favicon.ico`、`apple-touch-icon.png`、`icon-192.png`、`icon-512.png`；只改 SVG 不会自动跟着变。改了邮件页头的图（`core/email_art.py`，200 起：站点标志反色、两道山脊，照站点的地平线和图标的数字画）或者它借用的地平线、图标数字后跑 `uv run python manage.py render_email_art` 并提交 `static/img/email/`；信里的图是随信内嵌的（`core.mail.LetterMessage`），邮箱不显示 SVG。改了 `locale/` 下的 `.po`（后台中文，117 起）后跑 `uv run python manage.py compile_translations` 并提交 `.mo`。

## 旧站分层

仅用于获用户授权的旧站修复，旧站冻结范围见 [OWNERSHIP](../handoff/OWNERSHIP.md)。

**分层**（设计 17.3）：业务逻辑写在各应用的 `services.py`；状态字段只能通过 service 函数改；邮件用 `transaction.on_commit` 入队；功能权限统一走 `accounts.permissions.can_use()`
