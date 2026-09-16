# 003 M0 加固：健康检查与错误页样式

## 背景

002 的复核结果见 `../002-m0-fixes/review.md`。两个问题必须修。`docs/design.md` 已经按这次发现更新到 **v1.5.2**（13.10、13.15、16.6 节和附录 C），按新文档实现。

## 本轮范围

只做下面三节。不实现 M1 功能，不新增依赖，不改设计文档，不顺手重构别的部分。

## 任务

### R1 健康检查要区分「数据库忙」和「数据库坏」

复核时的实测结果：

- 另一个连接 `BEGIN IMMEDIATE` 占住写锁时，`GET /healthz` 等待 **5.2 秒**后返回 **503**，detail 是 `database is locked`
- 释放锁后 0.01 秒返回 200

原因：SQLite 的写事务是全库串行的，加上 `transaction_mode=IMMEDIATE`，探活要抢全库写锁；连接的 `timeout=5` 让它一卡 5 秒。后果是：任何一次稍慢的写事务（报名高峰、预渲染批量写、字体处理）都会让 docker healthcheck 和外部监控把站点标成挂掉，而且每次探活占住一个 Web 进程 5 秒（一共才 3 个）。

按 `docs/design.md` 16.6 节改：

1. 探活写入一张**专用探针表**（比如 `core` 应用下的 `HealthProbe`，单行即可，需要迁移），写入后回滚。不要再写 `django_content_type` 这类核心表
2. 探活的等待时间限制在 **200 毫秒**（放成常量），不要用全局的 5 秒 timeout
3. 遇到 SQLite 的 `database is locked` / `database is busy`：**视为正常**，HTTP 返回 200，detail 标记为忙，比如 `{"ok": true, "detail": "busy: another write in progress"}`。只有真正的故障（无法打开数据库、只读、表不存在等）才返回 503
4. 正常情况下探活耗时应远小于 1 秒

测试要求（新增）：

- 数据库可写 → 200
- 另一个连接占住写锁 → **200**，detail 标记为忙，并断言整个请求耗时小于 1 秒（用第二个 `sqlite3` 连接 `BEGIN IMMEDIATE` 构造）
- 数据库真的坏了（比如 patch 掉游标让它抛 `OperationalError("attempt to write a readonly database")`）→ 503

### R2 Django 渲染的错误页要恢复样式

复核时实测：404 页面的内联 `<style>` 被 CSP `style-src 'self'` 挡掉，页面显示为浏览器默认样式（无布局、蓝色下划线链接）。

按 `docs/design.md` 13.15 节改：

1. 错误页样式单独放 `static/css/error.css`（手写，不经过 Tailwind），作为**唯一数据源**
2. Django 渲染的 404 / 403 / 429 / 500：用 `{% static 'css/error.css' %}` 引用。运行时静态文件清单是存在的，不会有 001 里 A1 的构建期问题，CSP `'self'` 也允许
3. 给 Caddy 的 `maintenance.html` 保持**完全自包含**：`render_error_pages` 读取 `error.css` 的内容，内联进页面的 `<style>`
4. 维护页之外的产物怎么处理由你决定，但要满足：Caddy 只需要 `maintenance.html`；CI 的漂移检查继续有效
5. **不改 `SECURE_CSP`**，不加 `unsafe-inline`、不加 `unsafe-hashes`、不用 nonce

测试要求（更新 `core/tests/test_templates.py`）：

- Django 渲染的 4 个错误页：不含 `<style>`、不含 `<script>`，引用的样式表只有 `error.css`
- `maintenance.html` 产物：不含任何外部引用（`/static/`、`<link>`、`<script>`），并且确实包含 `error.css` 的内容（断言里面出现某个特征选择器）
- 保留原有的「templates 下没有内联 style 属性」测试

### R3 小问题

1. 自定义设置 `WAGTAILADMIN_PATH_PREFIX` 改名，避免和 Wagtail 官方设置混淆（比如 `ADMIN_URL_PREFIX`），同步改中间件和 README
2. CI 的 `docker build` 可以只在 push 到 main 和 PR 时跑；保持现状也可以，在报告里说明你的选择

## 验收标准

逐条实际执行，把真实输出贴进 `report.md`：

1. `uv run ruff check . && uv run ruff format --check .`
2. `uv run pytest`（新增测试要真的覆盖 R1 的三种情况）
3. `uv run python manage.py makemigrations --check --dry-run`（探针表的迁移要一起提交）
4. 生产配置下 `uv run python manage.py check --deploy`
5. 起开发服务器，**用第二个连接占住写锁**，同时请求 `/healthz`：贴出状态码、耗时、detail
6. `DEBUG=False` 起服务访问一个不存在的地址：贴出页面引用的样式表 URL，以及浏览器控制台有没有 CSP 报错
7. 首页控制台仍然 0 条报错
8. grep 确认 `deploy/error_pages/maintenance.html` 不含 `/static/`、`<link`、`<script`
9. `caddy validate`
10. `docker build` 成功
11. git 提交，提交信息以 `003:` 开头

## 输出要求

- 写进 `handoff/rounds/003-m0-hardening/report.md`，格式按 `handoff/README.md` 里的 report 模板：结论、逐条结果、验收输出、设计偏差、未完成 / 不同意、顺带发现、需要确认
- 写完把 `handoff/STATUS.md` 里的 `next` 改成 `claude`、`updated` 改成当天日期
- 只贴改动过的文件的完整内容，没改的不要重复贴
