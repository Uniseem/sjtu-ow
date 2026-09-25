# 067 去掉上游

## 背景

用户 2026-09-25 决定：本站和上游赛事网站独立，作为交大自己的社团网站运营，并重新规划功能。原设计围绕「对接上游」展开：开放 API 与 Webhook（第 11 章、`integrations` 应用）只给上游用，赛事有上游审核和两级审核模式，赛事可由上游推送，对阵与赛果由上游负责。这些没有使用者了。

用户同一天拍板的 21 条决定记录在 `handoff/STATUS.md`「你已经拍板的」第 15 条。本轮只做「去掉上游」和「报名自动通过」，新功能（个人报名与编队、站内搜索、文章评论）按 M8 另开轮次。

## 本轮范围

做：

- 设计文档升到 v1.6：定位改为独立运营；第 11 章整章作废（保留章节号）；赛事只剩本站审核，新增赛事级开关「报名自动通过」（默认关，有报名后不能改，后台要真正拦截）；数据模型、路由、后台菜单、邮件、附录 B/C 同步
- 删除 `integrations` 的代码、模板、测试、依赖和接线；保留它的迁移历史（`tournaments/0004` 依赖 `integrations/0001`，不能像 066 那样整个删）
- `tournaments`：删 `review_mode`、`source_client`、`external_id`、`awaiting_upstream`、`actor_type=upstream`、`actor_client`；加 `auto_approve`；迁移映射旧数据；状态机、后台审核、邮件相应简化
- README、AGENTS.md、隐私政策和用户协议草稿、crontab、Caddyfile、REVIEW-GUIDE 里的上游内容
- 顺手修一处已知缺口：「已经有报名之后不能修改审核模式」只在 API 里拦过，后台从没拦（agent 复核发现）。本轮改成拦「报名自动通过」开关

明确不做：

- 个人报名与编队、站内搜索、文章评论（069–073）
- 顺带发现的其他修复（068）：内容编辑的文章分类权限、restore 加密列清单、`/me/registrations/` 占位文案、prod 中间件漏项、内战段位 0、已结束内战的游戏 ID 删除
- 域名、服务器、测试机部署（用户指示 VPS 先不管）
- 设计 15.1 规模假设的改写

## 任务

1. **设计 v1.6**（`docs/design.md`）：按附录 D 新行逐章修改；验证：全文 grep「上游」只剩附录 D 和第 11 章的删除说明
2. **删除 integrations**：只留 `__init__.py`、`apps.py`、`migrations/`（0001、0002 + 新增 0003 删模型），加包内 README；`INSTALLED_APPS` 去掉 DRF 三个包、保留 `integrations`；删中间件、`REST_FRAMEWORK`、`SPECTACULAR_SETTINGS`、`API_*`、`WEBHOOK_ALLOW_INSECURE_URLS`（base 和 prod）、`/api/v1/` 路由、`core/middleware.py` 的 API 文档 CSP 分支、`core/net.py` 的 `allow_insecure`、`cleanup_old_data` 的两项、`restore.py` 的两行、robots 的 `/api/`、crontab 的 webhook 行、Caddyfile 的 `/api/*`、`pyproject.toml` 的三个依赖并重新锁定。验证：`uv run python -c "import integrations.api"` 失败；`/api/v1/ping` 404；`pytest` 全绿
3. **tournaments 迁移 0005**：RunPython 把 `awaiting_upstream` 报名改为 `pending`，日志里 `actor_type=upstream` 改为 `system` 并在备注前加「[原上游]」；删约束和四个字段；加 `auto_approve`；改枚举 choices。`integrations/0003` 依赖它，删三张表，并删除任务表里 `task_path` 以 `integrations.` 开头的记录。验证：全新库和 066 版旧库各跑一次（旧库带两级审核赛事、待上游确认报名、API 客户端、排队的 webhook 任务）
4. **报名自动通过**：`submit()` 写完名单后若开关打开则由系统通过，日志两行，只发一封邮件；同步名单后自动重新通过；后台表单在有报名后拒绝改开关。验证：新测试 + 变异（开关分支、邮件去重、后台锁）
5. **状态机与后台**：`approve`/`reject` 去掉操作方分支；`local_actions` 只按状态；审核详情模板去掉审核模式；提交成功提示按开关区分。验证：`test_state_table.py` 重写为 6 行表
6. **测试整理**：删 `integrations/tests`；改附录 B/C pin、恢复命令测试、地址清单测试、安全守卫测试、robots 测试；加「已删除」断言
7. **文档**：README（技术栈、状态机、删「开放 API」节、「定时清理」挪到运维、升级说明含 `remove_stale_contenttypes` 和删 cron 行）、AGENTS.md（目录表、硬规则 6、坑）、隐私政策「合作赛事平台」段、用户协议一句、REVIEW-GUIDE 三处、STATUS

## 验收标准

- `uv run ruff check . && uv run ruff format --check .`
- `uv run python manage.py tailwind build --force`
- `uv run pytest -q` 全绿
- `uv run python manage.py makemigrations --check --dry-run`
- 带 prod 设置的 `check --deploy` 无警告
- 旧库演练：三张 `integrations_*` 表、`tournaments_tournament.source_client_id`、`external_id`、`review_mode`、`tournaments_registrationstatuslog.actor_client_id` 都不存在；`django_migrations` 里 integrations 只有 0001–0003；报名状态无 `awaiting_upstream`；任务表无 `integrations.` 任务
- 浏览器：去掉 `REST_FRAMEWORK` 后 Wagtail 后台侧栏「页面」资源管理器正常
- 推送后 CI 绿
