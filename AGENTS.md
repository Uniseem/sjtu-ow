# AGENTS.md

写给在这个仓库里干活的 AI 编码助手（Claude Code、Codex、Cursor、Grok……）和新接手的开发者。

上海交通大学守望先锋社区网站：Wagtail 8 + Django 6 + Python 3.13，SQLite（WAL），uv 管依赖。前台是服务端渲染 + HTMX + Alpine.js（CSP 构建），公开页面由 worker 预渲染成静态 HTML。

## 开工前按顺序读

1. **`handoff/STATUS.md`**：现在做到哪、下一步做什么、在等谁。**进度只写在这一个地方**
2. **`handoff/README.md`**：一轮工作怎么做，`request` / `report` / `review` 三份文件怎么写
3. **`docs/design.md` 里和本轮有关的章节**：唯一的设计依据。3400 多行，按目录找章节读，不用通读
4. 按需读：`README.md`（怎么运行、怎么运维）、`handoff/REVIEW-GUIDE.md`（做独立复核时）、`handoff/rounds/<轮次>/`（某个功能当初为什么这样做）

## 目录

| 路径 | 内容 |
|---|---|
| `accounts/` | 用户、游戏 ID、段位、联系方式、功能权限（`permissions.can_use`） |
| `content/` | 页面类型、文章分类、投稿、B 站嵌入、sitemap / robots |
| `core/` | 全站设置、邮件、字体、预渲染、健康检查、备份恢复与运维命令 |
| `teams/` | 战队 |
| `lfg/` | 组队大厅（车帖） |
| `tournaments/` | 赛事、报名（`registration.py` 是状态机）、后台审核 |
| `integrations/` | 开放 API、签名认证、Webhook |
| `scrims/` | 内战、分队算法（`teaming.py`）、拖拽分队页 |
| `moderation/` | AI 内容审核 |
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

改了错误页模板或 `static/css/error.css` 后跑 `uv run python manage.py render_error_pages` 并提交 `deploy/error_pages/`。

## 测试机与部署

**测试机是 `185.99.135.224`，部署先放在这台机器上。** 用户 2026-09-18 指定。

| 项目 | 内容 |
|---|---|
| 域名 | `sjtu.ow-shanghaiuniversity.com`，经 CNAME 指向一个线路优化服务，最终解析到 `185.99.135.224`。模拟交大、国内、海外来源查询，结果都是这个 IP（050 轮核对） |
| 权限 | **助手拥有这台机器的全部权限**，可以直接部署、改配置、重启服务 |
| 登录 | SSH 密钥登录。登录用户和密钥位置在开发者本机的 SSH 配置里，**不写进仓库**（仓库是公开的） |
| 部署目录 | `/srv/sjtu-ow`（和 `deploy/crontab.example` 里的路径一致） |
| 证书 | Caddy 自动申请和续期，走 **HTTP 验证**，不用 DNS 验证。前提是 80 端口对外开放；`CADDY_SITE_ADDRESS` 填域名本身（不带 `http://`），Caddy 才会申请证书 |
| 跳转 | **HTTP 必须自动跳转到 HTTPS**。站点地址是域名时 Caddy 默认会做，部署后要实测：`curl -I http://sjtu.ow-shanghaiuniversity.com/` 应返回跳转到 `https://` 的 3xx |

**机器上还跑着别的项目**（另一套 Docker Compose 和一个监控探针）。只动 `/srv/sjtu-ow` 和本项目的 Compose 项目：

- 不停、不重启、不删别人的容器、网络和数据卷
- **不要**执行 `docker system prune`、`docker volume prune` 这类全局清理
- 本项目的 Caddy 会占用 80 和 443 端口。以后这台机器上别的网站要用域名访问，得经过这个 Caddy 转发

## 硬规则

1. **`docs/design.md` 是唯一设计依据。** 要改设计：需要用户拍板的先问；定了之后**先改文档再改代码**，在附录 D 记版本。实现和设计不一致时，要么改代码，要么改设计，不能两边各说各的
2. **按轮次工作**（流程见 `handoff/README.md`）：先写 `request.md`，再实现，写 `report.md`，再复核写 `review.md`，更新 `STATUS.md`，**一轮一个提交**，**直接推送到 `main`**（不开分支保护、不走合并请求，设计 17.5）。推送后看一眼 CI，红了优先修
3. **提交信息一律用中文。** 格式：第一行 `轮次号: 一句话说改了什么`（比如 `046: 提交信息改用中文`），空一行，正文说清楚为什么改、怎么验证的；最后的 `Co-Authored-By` 之类的署名行保持原样。045 及以前的提交是英文，不改写历史
4. **报告里只放真实跑过的命令输出。** 没跑的写「未验证」，不写推测结果
5. **不扩大本轮范围，不新增依赖。** 顺带发现的问题写进报告，留给下一轮；确实要加依赖，先停下来问，并确认它的许可证：MIT、BSD、Apache 可以，**GPL、AGPL 不行**（和本项目的 PolyForm Strict 许可证冲突，设计 17.8）
6. **分层**（设计 17.3）：业务逻辑写在各应用的 `services.py`；状态字段只能通过 service 函数改；邮件和 Webhook 用 `transaction.on_commit` 入队；功能权限统一走 `accounts.permissions.can_use()`
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
- **drf-spectacular** 的视图要写明 `operation_id`，否则 `check --deploy` 出警告（018）
- **计时测试在机器繁忙时会偶发失败**：6v6 分队 1 秒内、数据库被锁时 `/healthz` 1 秒内。并行跑测试或变异测试时注意（042）
- **`handoff/` 在 ruff 的排除列表里**（轮次报告要原样引用代码）。放在里面的脚本要指定路径单独检查
- **变异测试改回代码后**，如果文件大小和修改时间没变，Python 可能用旧的 `__pycache__`。改回后清一下缓存再跑（027）
- **预渲染**：从备份恢复后必须清空 `prerendered/`；开发环境默认关闭预渲染
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
