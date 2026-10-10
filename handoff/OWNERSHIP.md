# 改动范围与前后端交接

改任何文件前先查本文件。用户明确指定的本轮例外记在该轮 request 和 STATUS，结束后失效，不混进长期规则。历史表的「GPT」是后端职责称呼，当前具体助手看 STATUS。

**2026-10-10 用户交班补充**：「GLM 接替后端，前端仍由 Claude 做」。下文的 GPT 是后端职责的称呼，GLM 接班沿用完全相同的可改范围、BE/FE 交接规则和轮流工作规则；提交署名写实际运行的 GLM 具体模型，不沿用 GPT 或 Claude 的署名。

**Claude 和 GPT 分开做，各改各的**（270 起，用户 2026-10-10：「你把前端往下推进，后端之后让 gpt 去写」「规范一下 claude 和 gpt 的各自的可改动范围避免冲突」）。**Claude 管前端，GPT 管后端**；改动范围按下表，表外的东西先问用户。范围和交接规则只维护在本文件，其他入口指过来。

| 范围 | 归谁 | 说明 |
|---|---|---|
| `web/`（`apps/`、`packages/ui`、`shared`、`styles`、`packages/api/src/client.ts`、`pending-api.ts`、`package.json`、锁文件） | Claude | 加依赖照旧先问用户（AGENTS.md「常驻约束」） |
| `web/packages/api/src/gen/`、`docs/api-reference.md` | GPT | **只由 `sjtuow apigen` 生成，谁都不手改**（CI 比对生成物）。这是前后端的接口契约 |
| `server/`（含迁移、`apigen`、`sjtuow` 各命令） | GPT | |
| `deploy/` 里新栈的文件（`Caddyfile.new`、`docker-compose.new.yml`、`Dockerfile.server`、`Dockerfile.web`、`cutover.sh`、`rehearse.sh`）、`e2e/caddy/`、`docs/cutover.md` | GPT | 部署到任何服务器仍要用户点头 |
| `e2e/parity/`、`scripts/screens.py` 的种子数据、`scripts/journey.mjs`、`scripts/screens.mjs`、`browser-check.mjs`、`budget.mjs` | Claude | 前台的验收工具。GPT 改了它调用的 `sjtuow` 命令（`import`、`session`、`import-media`）的参数时，可以只改调用那一行，并在报告里写明 |
| `scripts/check.sh`、`.github/workflows/ci.yml` | 按段分 | 「Go（新栈）」段和 CI 的 go 任务归 GPT，「Web（新栈）」段和 web 任务归 Claude；`scripts/remote-check.sh` 两边都用，改它先问用户 |
| `docs/frontend-migration.md`、12 号文档第 6 节（前端） | Claude | |
| 12 号文档其余各节、`05-business-rules.md`、`08-contracts.md` | GPT | |
| 调研 00–11 的其余文档、`docs/admin-inventory.md` | 不改 | 当时的调研记录。发现写错了照旧加更正，不改原文 |
| `README.md`、`.env.example`、`THIRD_PARTY_NOTICES.md`、`.gitignore`、`.gitattributes`、`.dockerignore` | 按内容分 | 新栈 Go、部署、环境变量的部分归 GPT，前端的部分归 Claude；只改自己那部分，改动小、推送前 `pull --rebase` |
| `docs/design.md`、`design-next.md`、`design-details.md`、`admin.md` | 谁的轮次要改谁改 | 设计变化本来就要用户拍板（AGENTS.md「常驻约束」）；改之前在 STATUS 写一句，免得两边同时改 |
| `13-ideas-and-followups.md`、`docs/pitfalls.md` | 两边都可以加 | 只追加，不改对方写的条目。`AGENTS.md`、协作与文档维护规则照用户的话改 |
| `handoff/rounds/<轮次>/` | 写那一轮的人 | 不改对方的轮次文件（发现写错照旧在原文位置加「NNN 轮更正」） |
| `handoff/STATUS.md` | 按段分 | 头部 `next_frontend`、`milestone`、「前台迁移」各表（底座、F2、前台页面进度）归 Claude；`next_backend` 归 GPT；`round`、`updated`、`blocked_on` 谁提交谁改（`blocked_on` 只加自己发现的、只删自己解决的）；「交给后端（GPT）」表 Claude 加行、GPT 只改「状态」一栏；「交给前端（Claude）」表反过来；「最近轮次」各自在最上面加自己那一条 |
| 旧站（Django：各应用、`templates/`、`static/`、`assets/`、`locale/`、`sjtu_ow/`、`deploy/` 里旧站的文件、根目录的 `Dockerfile`、`manage.py`、`pyproject.toml`、`uv.lock`、`conftest.py`、`scripts/journey.py`、`scripts/pytest-shards.sh`） | 冻结 | 只读，是对拍的参照。安全和丢数据的修复照「冻结」那条先问用户，问完由用户指定谁做 |

越界的事不自己动手，写进对方的表：

- **前端要 Go 的字段或接口**（Claude → GPT）：前端照旧模板写好（有就显示），期望的形状写进 `web/apps/site/src/pending-api.ts`（每段带 `[BE-n]`），规格写进 STATUS「交给后端（GPT）」。Claude 发现的后端 bug 也写成一行 BE（例如 270 的 BE-0）
- **后端做完一条 BE**：GPT 改 Go、跑 `apigen`、整组绿，在表里把状态改成「✓ 轮次号」。**GPT 不动 `pending-api.ts` 和页面**；Claude 下一个前端轮次删掉对应的那段、改用生成的类型、跑那几页的对拍，再把状态改成「已接 轮次号」
- **后端要改一个页面已经在读的字段**：只许加字段，不许改名、删除、改含义。确实要改，GPT 先在「交给前端（Claude）」加一行 FE，等 Claude 把页面换过去，再在后面的轮次删旧字段。GPT 发现的前端 bug 同样写成 FE

轮流干，防冲突：

- **轮流干，共用一个检出目录**（用户 2026-10-10 拍板：「轮流干的」）：同一时间只有一个助手在干活。**交班时工作区必须干净**：自己的改动要么提交推送，要么删掉，草稿不留在目录里（266–270 GPT 没提交的草稿留在目录里，`remote-check.sh` 会把目录里所有没提交的改动打包上测试机，接班的人的检查就带上了它；`git add` 也容易带上它）。**接班先 `git status`**：干净就 `git pull --rebase` 开工；不干净就停下来问用户，不替对方提交、不删对方的文件。哪天要两边同时开工，先问用户，各用一个克隆
- 开工前 `git pull --rebase`；提交以后、推送之前再 `git pull --rebase` 一次（工作区有改动时 git 不让拉，所以是先提交再拉），然后马上推送、看 CI。`git add` 只写自己范围里的路径，不用 `git add -A`、`git add .`
- **轮次号**：开工时拉一次，取当时最大号加一；提交前拉下来发现这个号被对方用了，就把自己这轮改成下一个空号（目录名、三份文件里的标题、STATUS、提交标题一起改）。目录名前端用 `NNN-f<阶段>-…`，后端用 `NNN-be-…`，一眼看出是谁的
- 测试机是共用的：`remote-check.sh` 同一时间只跑一个，后来的排队；对拍一次约 6 分钟，别连着排多次
- 提交署名照实写模型（handoff/README.md「提交与交班」）：Claude 的提交只署 Claude，GPT 的只署 GPT，不替对方署名

## 文档整理后的归属

原 AGENTS 的规则搬到新文件后沿用原归属：开发验收与运行说明按前后端内容分，运维归后端；踩坑两边可以追加，不改对方条目。文档入口和协作规则按用户授权修改。本轮文档重组的范围例外见 278 request，不授予网站代码的额外权限。
