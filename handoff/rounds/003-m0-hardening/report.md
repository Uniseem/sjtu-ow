# 003 实现报告

## 结论

R1 / R2 / R3 已完成：探活改为专用表且「忙」返回 200（约 260ms），Django 错误页改引用 `error.css` 后样式和 CSP 都正常，维护页仍自包含。

## 逐条结果

### R1 健康检查区分「忙」和「坏」

- 新增 `core.HealthProbe`（迁移 `core/migrations/0001_initial.py`）。探活向该表插入一行再回滚，不再写 `django_content_type`。
- 常量 `HEALTH_PROBE_BUSY_TIMEOUT_MS = 200`（settings 与 `core/health.py`）。探活前对该连接执行 `PRAGMA busy_timeout=200`，结束后恢复为全局 5 秒。
- SQLite `database is locked` / `database is busy`：`{"ok": true, "detail": "busy: another write in progress"}`，HTTP 200。
- 只读等真正故障：503。
- 测试：可写 → 200；第二个连接 `BEGIN IMMEDIATE` → 200 且耗时 `< 1s`；patch `OperationalError("attempt to write a readonly database")` → 503。

### R2 Django 错误页样式

- 唯一数据源：`static/css/error.css`（手写，不经 Tailwind）。
- Django 渲染的 404 / 403 / 429 / 500：`{% static 'css/error.css' %}`，模板里不再有 `<style>` / `<script>`。
- `render_error_pages` 只生成 `deploy/error_pages/maintenance.html`，把 `error.css` 内联进 `<style>`。Caddy 本来就只读维护页，因此删掉了仓库里另外四份静态错误页。
- **未改** `SECURE_CSP`。
- 实测 `DEBUG=False` 访问不存在的地址：样式表为 `/static/css/error.css`，页面有布局，CSP 违规报告 0 条。截图见 `artifacts/404.png`。

### R3 小问题

1. `WAGTAILADMIN_PATH_PREFIX` 已改名为 `ADMIN_URL_PREFIX`（settings、中间件、README）。
2. CI 的 `docker build` **保持现状**：workflow 本身已是 `push` 到 `main` 和 `pull_request` 才跑，再拆 job 没有额外收益。

## 验收输出

### 1. ruff

```
All checks passed!
87 files already formatted
```

### 2. pytest

```
collected 10 items

accounts/tests/test_models.py::test_create_user_with_email_login PASSED
accounts/tests/test_models.py::test_create_superuser_sets_agreement_timestamps PASSED
core/tests/test_pages.py::test_healthz_returns_200 PASSED
core/tests/test_pages.py::test_home_returns_200 PASSED
core/tests/test_sqlite.py::test_sqlite_pragma_and_options PASSED
core/tests/test_pages.py::test_healthz_returns_200_when_database_is_busy PASSED
core/tests/test_pages.py::test_healthz_returns_503_when_database_not_writable PASSED
core/tests/test_templates.py::test_templates_have_no_inline_style_attributes PASSED
core/tests/test_templates.py::test_django_error_pages_reference_only_error_css PASSED
core/tests/test_templates.py::test_maintenance_page_is_self_contained_and_inlines_error_css PASSED

============================== 10 passed in 0.56s ==============================
```

### 3. makemigrations --check

```
No changes detected
```

（探针表迁移 `core/migrations/0001_initial.py` 已提交。）

### 4. check --deploy

```
System check identified no issues (0 silenced).
```

### 5. 写锁占用时请求 /healthz

开发库 `data/db.sqlite3` 上第二个连接 `BEGIN IMMEDIATE`，同时 `GET http://127.0.0.1:8000/healthz`：

```
status=200
elapsed_s=0.264
{"status": "ok", "checks": {"database": {"ok": true, "detail": "busy: another write in progress"}, "disk": {"ok": true, "detail": "free space 38.4%"}, "worker_heartbeat": {"ok": true, "detail": "skipped_until_m1", "affects_status": false}, "task_backlog": {"ok": true, "detail": "skipped_until_m1", "affects_status": false}}}
database.detail= busy: another write in progress
database.ok= True
```

### 6. DEBUG=False 访问不存在的地址

用 `DJANGO_SETTINGS_MODULE=sjtu_ow.settings.base`（`DEBUG=False`）+ `runserver --insecure`。`curl -L http://127.0.0.1:8000/this-page-does-not-exist-003`：

```
HTTP/1.1 404 Not Found
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; ...
```

页面引用：

```
<link rel="stylesheet" href="/static/css/error.css">
```

无 `<style>`、无 `<script>`。浏览器：`link[rel=stylesheet]` 仅为该 URL；`h1` 计算样式 `font-size: 32px`、`.actions` 为 `flex`；`ReportingObserver` 缓冲的 `csp-violation` 为 `[]`。

### 7. 首页控制台

同一服务打开 `/`：`style` 标签 0、内联 style 属性 0、`htmx.config.includeIndicatorStyles === false`、CSP 报告 `[]`。

### 8. grep 维护页

```
rg -n '/static/|<link|<script' deploy/error_pages/maintenance.html
OK: no /static/, <link, or <script>
```

维护页含特征选择器 `.actions a.secondary`（来自 `error.css`）。

### 9. caddy validate

```
Valid configuration
```

### 10. docker build

```
Successfully built dc37ba2ba386
Successfully tagged sjtu-ow:ci
```

### 11. git

本轮提交信息以 `003:` 开头（见该提交）。

## 设计偏差

1. **12.4 core 模型表**未列出 `HealthProbe`。实现按 16.6 节加了专用探针表；请在 12.4 补一行，避免和「core 里暂时没有业务模型」的表述打架。
2. 无其它与 v1.5.2 的 13.15 / 16.6 / 附录 C 不一致之处。

## 未完成 / 不同意

无。R3.2 选择保持 CI 现状，理由见上。

## 顺带发现

- 无尾部斜杠的未知路径会先 301 到带斜杠再 404（`CommonMiddleware.APPEND_SLASH`），不是错误页本身的问题。
- 本机 `/usr/bin/git` 和 `/usr/bin/python3` 仍被 Xcode license 拦住；验收里的 git 继续用 GitHub Desktop 自带二进制。

## 需要确认

无。

## 改动文件

`core/models.py`、`core/health.py`、`core/migrations/0001_initial.py`、`core/middleware.py`、`core/management/commands/render_error_pages.py`、`core/tests/test_pages.py`、`core/tests/test_templates.py`、`sjtu_ow/settings/base.py`、`templates/errors/base.html`、`static/css/error.css`、`deploy/error_pages/maintenance.html`（删除 404/403/429/500.html）、`README.md`、`handoff/STATUS.md`、本报告。
