# 004 实现报告

## 结论

T1–T4 已完成：allauth 65.19.3 邮箱登录 + 6 位验证码，SiteSettings / Fernet SMTP，队列发信与 1m/5m/30m 重试，worker 进程内心跳接入 `/healthz`。本地注册到改邮箱全流程跑通；停 worker 后健康检查 503（心跳过期），写锁占用仍 200。

## 逐条结果

### T1 账号

- 依赖：`django-allauth==65.19.3`（`>=65.0,<66`）。
- 登录方式 `ACCOUNT_LOGIN_METHODS={"email"}`；强制验证 `ACCOUNT_EMAIL_VERIFICATION=mandatory`；验证码 `ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED` / `ACCOUNT_PASSWORD_RESET_BY_CODE_ENABLED`；改邮箱 `ACCOUNT_CHANGE_EMAIL=True`（新邮箱验证通过后才替换）。
- 验证码格式通过 `ALLAUTH_USER_CODE_FORMAT={"length": 6, "numeric": True, "dashed": False}`（allauth 65.19.3 全局设置，邮箱验证和找回密码都走这个默认）。有效期 / 尝试次数用 allauth 默认并写进配置：验证 15 分钟最多 3 次，找回密码 3 分钟最多 3 次；允许重发 `ACCOUNT_EMAIL_VERIFICATION_SUPPORTS_RESEND=True`。
- 注册额外字段在 `SignupExtraForm`（`ACCOUNT_SIGNUP_FORM_CLASS`，单独模块以免和 allauth 表单循环导入）：昵称 2–16 去首尾空格、是否交大单选、两个必勾同意；时间戳写入 `agreed_terms_at` / `agreed_cross_border_at`。
- `is_sjtu` 变化时 `post_save` 同步「交大用户」/「校外用户」。`init_site` 本轮只建这两个组。
- 会话 14 天；`LoggedInHintCookieMiddleware` 设置 `ow_logged_in=1`（非 HttpOnly，max-age 与会话一致），匿名时删除。
- `LOGIN_URL` / `WAGTAILADMIN_LOGIN_URL = account_login`。
- 页面覆盖 `templates/account/` + `templates/allauth/layouts/`，中文，无内联 `style`；表单标签在 `accounts/allauth_forms.py`。
- **实际生效的限流**（allauth 把 `ACCOUNT_RATE_LIMITS` 合并进默认值后的结果）：

| 动作 | 值 |
|---|---|
| signup | 20/m/ip |
| login | 30/m/ip |
| login_failed | 10/m/ip, 5/300s/key |
| reset_password | 20/m/ip, 5/m/key |
| confirm_email | 1/10s/key |
| manage_email | 10/m/user |
| change_password | 5/m/user |
| reset_password_from_key | 20/m/ip |
| reauthenticate | 10/m/user |
| request_login_code | 20/m/ip, 3/m/key（未启用登录码，保留默认） |
| change_phone / verify_phone | allauth 默认（未启用手机） |

### T2 全站设置与 SMTP

- `SiteSettings`（`BaseGenericSetting`）一次性包含 12.4.1 全部字段；SMTP 和主题前缀本轮使用，其余 `help_text=后续里程碑使用`。
- SMTP 密码 Fernet：`SHA256(FIELD_ENCRYPTION_KEY)` 再 `urlsafe_b64encode`，`cryptography==50.0.1`。后台 `PasswordInput(render_value=False)`，留空保留密文。
- 「发送测试邮件」：`/admin/settings/core/send-test-email/`，`core.change_sitesettings`，同步 SMTP 发给当前管理员，成功/失败用 Wagtail messages。未配置时 `SMTPNotConfigured` 中文提示。

### T3 异步邮件与 worker

- `EMAIL_BACKEND=core.mail.QueuedEmailBackend`。标准 `send_mail` / allauth / Wagtail 都入队。worker 用 `EMAIL_DELIVERY_BACKEND` 真正发出（dev：console；prod：`SiteSettingsEmailBackend`）。
- 事务内 `transaction.on_commit` 后入队，否则立即入队。
- 失败重试：首次失败后间隔 60s / 300s / 1800s 再入队（初始发送 + 3 次重试）。
- 投递时补纯文本 + HTML，主题加前缀（adapter `format_email_subject` 不再加前缀，避免加两次）。
- **心跳实现**：`run_worker` 在 `db_worker` 之前启动守护线程，每 30 秒把 ISO 时间写入 `DatabaseCache`（key `sjtu_ow:worker_heartbeat`）。选进程内线程而不是自重排任务，是因为 worker 挂了任务也跑不了，心跳必须和消费进程同生共死。开发环境去掉 locmem 缓存，否则 web 进程看不到 worker 心跳。
- `/healthz`：心跳缺失或超过 2 分钟 → 503；READY 任务等待超过 10 分钟 → 503。数据库忙仍 200（003 行为保留）。
- 原 `DiscardLogEmailBackend` 已删除，生产走队列 + SiteSettings SMTP。

### T4 文档

README 补充：后台 SMTP、本地注册必须跑 `run_worker`、健康检查含心跳/积压。`init_site` 与 `createcachetable` 写进本地和生产步骤。

## 验收输出

### 1. ruff / pytest / makemigrations / check --deploy

```
All checks passed!
103 files already formatted
```

```
...........................                                              [100%]
27 passed in 6.09s
```

```
No changes detected
```

```
DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod \
DJANGO_SECRET_KEY=ci-not-for-production-use-a-long-random-string-at-least-fifty-chars \
...
System check identified no issues (0 silenced).
```

说明：Django 测试环境会把 `EMAIL_BACKEND` 改成 locmem。邮件测试里显式恢复 `QueuedEmailBackend`。`ALLAUTH_DEFAULT_AUTO_FIELD=django.db.models.AutoField`，与 allauth 自带迁移一致，否则 `makemigrations --check` 会想改 `.venv` 里的 PK。

### 2. 本地注册全流程（console 投递）

`runserver`（dev）+ `run_worker`。邮箱 `live004-1789539519@example.com`。

| 步骤 | 结果 |
|---|---|
| POST `/accounts/signup/` | 200，跳转 `/accounts/confirm-email/`，session 验证码 `254041` |
| POST 验证码 | 200，跳转 `/`，`ow_logged_in=1`，消息「已验证邮箱 …」「已登录为 验收昵称」 |
| POST logout | `ow_logged_in` 清除，session 无 `_auth_user_id` |
| POST login | `ow_logged_in=1` |
| 找回密码 | 验证码 `524555` → 设新密码 → 新密码登录成功 |
| 改邮箱 | 新邮箱 `live004-new-1789539519@example.com`，验证码 `672508`，验证后 `user.email` 已替换且 `verified/primary=True` |

worker 控制台（注册验证码，主题带前缀，同时有 text/html）：

```
Subject: [SJTU OW] 请验证你的邮箱
To: live004-1789539519@example.com
验证码：254041
Content-Type: text/plain
Content-Type: text/html
Task ... state=SUCCESSFUL
```

找回密码同样由 worker 打到控制台：`验证码：524555`。

### 3. 停 worker 后健康检查

worker 在跑时：

```
HTTP/1.1 200 OK
{"status": "ok", ..., "worker_heartbeat": {"ok": true, "detail": "ok (24s ago)", "affects_status": true}, ...}
```

`pkill` worker 约 2 分钟后：

```
HTTP/1.1 503 Service Unavailable
{"status": "error", "checks": {..., "worker_heartbeat": {"ok": false, "detail": "心跳过期（158 秒未更新）", "affects_status": true}, ...}}
```

重启 `run_worker` 后：

```
HTTP/1.1 200 OK
{"status": "ok", ..., "worker_heartbeat": {"ok": true, "detail": "ok (6s ago)", "affects_status": true}, ...}
```

### 4. 写锁占用时 /healthz 仍 200

第二个连接 `BEGIN IMMEDIATE` 期间请求 `/healthz`（worker 心跳有效）：

```
status=200
elapsed_s=0.239
{"status": "ok", "checks": {"database": {"ok": true, "detail": "busy: another write in progress"}, "disk": {"ok": true, "detail": "free space 38.4%"}, "worker_heartbeat": {"ok": true, "detail": "ok (14s ago)", "affects_status": true}, "task_backlog": {"ok": true, "detail": "ok", "affects_status": true}}}
```

### 5. 浏览器注册 / 登录 / 找回密码

390px 视口可用，汉堡菜单 + 表单全宽按钮。CSP `ReportingObserver` 缓冲 `csp-violation` 均为 `[]`；页面 `[style]` 数量 0。截图：

- `artifacts/signup-desktop.png`
- `artifacts/signup-mobile.png`
- `artifacts/login-mobile.png`
- `artifacts/reset-mobile.png`

daisyUI 5 没有 `input-bordered`，表单控件改用 `input`。

### 6. `ow_logged_in`

见第 2 节：验证/登录后值为 `1`，登出后 Cookie 删除。

### 7. SMTP 密码密文

```
SELECT id, length(smtp_password), substr(smtp_password,1,32) FROM core_sitesettings;
[(1, 120, 'gAAAAABqqjTN8E-WtQ9_9fpoWErcBJxz')]
```

Fernet token 前缀 `gAAAAA`，不是明文。

### 8. docker build / caddy validate

```
Successfully built 0699fe9226c0
Successfully tagged sjtu-ow:ci
```

```
docker run --rm -e CADDY_SITE_ADDRESS=http://localhost \
  -v $PWD/deploy/Caddyfile:/etc/caddy/Caddyfile:ro \
  caddy:2.10-alpine caddy validate --config /etc/caddy/Caddyfile
Valid configuration
```

### 9. git

提交信息以 `004:` 开头。

## 设计偏差

1. 开发缓存从 locmem 改为 `DatabaseCache`，否则跨进程读不到 worker 心跳。和 16.10「开发用内存缓存」不完全一致；心跳可见性优先。
2. Django 测试 runner 强制 locmem `EMAIL_BACKEND`。应用配置仍永远是 `QueuedEmailBackend`；仅测试里改回去。
3. `ALLAUTH_DEFAULT_AUTO_FIELD` 设为 `AutoField` 以匹配 allauth 自带迁移，不用项目的 `BigAutoField`。

## 未完成 / 不同意

无。个人资料、游戏 ID、功能权限、其余角色组按范围留给 005。

## 顺带发现

- 工作区里已有 Claude 在 003 复核时写入的 `docs/design.md` v1.5.3（HealthProbe）和 `003-m0-hardening/review.md`，本轮一并提交；Grok 没有改设计正文。
- daisyUI 5（随 tailwind-cli-extra 2.9）去掉了 `input-bordered`，`@apply` 会直接编译失败。
- 本机 `/usr/bin/git` 仍被 Xcode license 拦住，git 继续用 GitHub Desktop 自带二进制。

## 需要确认

无。

## 改动文件

账号：`accounts/adapter.py`、`accounts/allauth_forms.py`、`accounts/forms.py`、`accounts/signals.py`、`accounts/apps.py`、`accounts/services.py`、`accounts/tests/test_signup.py`。

邮件与设置：`core/crypto.py`、`core/mail.py`、`core/tasks.py`、`core/worker.py`、`core/forms.py`、`core/models.py`、`core/health.py`、`core/middleware.py`、`core/views.py`、`core/wagtail_hooks.py`、`core/apps.py`、`core/migrations/0002_sitesettings.py`、`core/management/commands/run_worker.py`、`core/management/commands/init_site.py`、`core/tests/test_mail.py`、`core/tests/test_pages.py`。

配置与模板：`sjtu_ow/settings/{base,dev,prod}.py`、`sjtu_ow/urls.py`、`conftest.py`、`pyproject.toml`、`uv.lock`、`deploy/entrypoint-worker.sh`、`.env.example`、`README.md`、`assets/css/input.css`、`templates/account/**`、`templates/allauth/**`、`templates/wagtailsettings/edit.html`、`templates/components/{account_area,form_field}.html`。

交接：`handoff/STATUS.md`、本报告、`handoff/rounds/003-m0-hardening/review.md`、`docs/design.md`（仅提交已有的 v1.5.3 补丁）。
