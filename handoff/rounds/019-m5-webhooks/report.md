# 019 实现报告

> 本轮由实现方（Claude）自己做，用户外出。下面所有输出都是真实跑出来的；没跑的会写「未验证」。

## 结论

**完成。M5 到此结束。** Webhook 投递与重试、接口文档页、每日清理任务都做完了。实现过程中发现接口文档页**在本站的 CSP 下是一片空白**（Swagger UI 默认从 CDN 取资源），已改成自托管；这个问题我的第一版测试没能发现，因为它只断言了状态码 200。

## 逐条结果

### T1 WebhookDelivery

按设计 12.10.3 建表，索引 `(status, next_attempt_at)`。迁移 `integrations/migrations/0002_webhookdelivery.py`。

### T2 事件与订阅过滤

五种事件按 11.8.1。**两层过滤**都在 `webhooks.subscribers()` 里：客户端订阅了这个事件，**并且**赛事和它相关（`upstream` / `two_stage` 模式，或者赛事是它自己推的）。另外还要求配了地址、客户端可用。

`thin` / `full` 两种请求体。`full` 的展开范围是客户端被允许的展开项**去掉 `logs`**。`tournament_external_id` 沿用赛事对象的可见性规则。

**payload 在事件产生时就生成并存库**，重试不重算。

### T3 签名与投递

签名按 11.8.2。投递：10 秒超时、2xx 成功、**`_NoRedirect` 处理器让 3xx 变成失败**、重试间隔 `(60, 300, 1800, 7200, 21600, 43200, 86400)` 秒、加首次共 8 次。

地址校验抽到了 `core/net.py`（`assert_public_https_url`），字体下载器也改成走同一份代码，两处不会再各写各的。

### T4 接到业务流程

`tournaments/registration.py` 里原来那两行 `# M5: ...` 标记换成了真实调用，全部走 `transaction.on_commit`。排队失败只记日志，不会让报名动作失败。

### T5 后台

客户端详情页加了 Webhook 配置、「发送测试事件」、最近 30 条投递；`/deliveries/` 页显示最近 200 条并可以重发。

### T6 接口文档

`/api/v1/docs/` 和 `/api/v1/schema/`，只有超级管理员能看。

### T7 清理任务

`manage.py cleanup_old_data`（带 `--dry-run`），`deploy/crontab.example` 排在每天 04:00。

## 验收输出

### 1. 检查与测试

```
$ ruff check . && ruff format --check .
All checks passed!
184 files already formatted

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ uv run python -m pytest -q
421 passed in 25.09s

$ DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod ... uv run python manage.py check --deploy
System check identified no issues (0 silenced).
```

本轮新增 49 个测试（webhooks 33、后台 9、文档页与清理 8，减去重叠计数）。

### 2. 真实接收端收到的请求

起了一个真实 HTTP 接收端（`127.0.0.1:9019`），**验签代码从设计 11.8.2 原样复制**。本站真发过去：

```
=== POST /ok  签名校验: True
  Content-Type: application/json
  X-Webhook-Id: 48c5fb8c-855f-40ae-8708-2cb6cf73eccb
  X-Webhook-Event: registration.submitted
  X-Webhook-Timestamp: 1789564351
  X-Webhook-Signature: sha256=70cf0f5d981d186c0f213d8a13dd5fd92d4f0f949665aed63b674779d3339c8a
{
  "id": "48c5fb8c-855f-40ae-8708-2cb6cf73eccb",
  "type": "registration.submitted",
  "created_at": "2026-09-16T13:12:31Z",
  "actor_type": "captain",
  "data": {
    "registration_id": 5, "tournament_id": 5, "tournament_external_id": null,
    "team_id": 7, "status": "pending", "previous_status": null, "roster_version": 1,
    "registration": { "id": 5, "team_name": "019 验证战队", "member_count": 2,
      "team": {...}, "members": [{"nickname": "验证队长", "ranks": {...}}, ...] }
  }
}
```

第二条是 `registration.status_changed`，`actor_type` 为 `upstream`，`previous_status` 为 `pending`。两条的签名校验都是 `True`。

**请求体里没有 `logs`，也没有联系方式**：在接收端收到的原始报文里搜 `987654321`（QQ）、`@example.com`、`"logs"`，三个都是 0 次。

### 3. 500 / 302 / 超时

让接收端分别返回 500、302、睡 15 秒：

```
500 服务器错误:  成功=False 状态=pending 状态码=500  错误='HTTP 500'
    尝试次数=1 下次尝试=2026-09-16 13:13:56（60 秒后）
302 重定向:      成功=False 状态=pending 状态码=302  错误='HTTP 302'
    尝试次数=1 下次尝试=2026-09-16 13:13:56（60 秒后）
超时:            成功=False 状态=pending 状态码=None 错误='连接失败：timed out'
    尝试次数=1 下次尝试=2026-09-16 13:14:06（10 秒超时 + 60 秒）
```

**302 确实没有跟随**。接收端自己的日志可以佐证——`/moved` 会 302 到 `/ok`，如果跟随了 `/ok` 会多收到一条：

```
接收端收到的请求（按路径统计）:
  /boom: 1 次
  /moved: 1 次
  /ok: 2 次     ← 只有最初两条业务事件，没有多出来的
  /slow: 1 次
```

### 4. 后台测试事件与手动重发

在浏览器里真实点击（超管登录）：

- 点「发送测试事件」→ 生成 `ping` 投递，事件 ID `8bc1737c-9521-4989-9659-2c6e495dd4b3`，投递到接收端返回 200，状态「已送达」。
- 把它改成「已失败」，在 `/deliveries/` 页点「重发」→

```
后台点「重发」之后:
  event_id   8bc1737c-9521-4989-9659-2c6e495dd4b3 （和重发前一致）
  status     pending
  attempts   1
```

### 5. `/api/v1/docs/` 的权限

真实 HTTP：

```
超管（浏览器登录）:  /api/v1/docs/ -> 200，Swagger UI 完整渲染
                    /api/v1/schema/ -> 200
非超管（有后台权限）: /api/v1/docs/ -> 403
                    /api/v1/schema/ -> 403，正文里 "tournaments" 出现 0 次
匿名:               /api/v1/docs/ -> 403
                    /api/v1/schema/ -> 403
                    正文: error: code: validation_error / 身份认证信息未提供。
```

页面上实际加载的资源，全部来自本站：

```
GET /static/drf_spectacular_sidecar/swagger-ui-dist/swagger-ui.css              200
GET /static/drf_spectacular_sidecar/swagger-ui-dist/swagger-ui-bundle.js        200
GET /static/drf_spectacular_sidecar/swagger-ui-dist/swagger-ui-standalone-preset.js  200
GET /api/v1/schema/                                                             200
```

页面 HTML 里 `cdn.jsdelivr` / `unpkg` / `cdnjs` 出现 0 次。schema 里 `admin/api` 出现 0 次（Wagtail 后台 API 没有混进来）。

### 6. 清理任务

造了 3 条过期调用日志、3 条投递记录（200 天已送达 / 300 天已失败 / **400 天但仍待投递**）、1 条过期会话：

```
$ python manage.py cleanup_old_data --dry-run
将删除 API 调用日志（90 天前）：3
将删除 Webhook 投递记录（180 天前）：2
将删除 已完成的任务记录（30 天前）：0
将删除 过期会话：1

$ python manage.py cleanup_old_data
已删除 API 调用日志（90 天前）：3
已删除 Webhook 投递记录（180 天前）：2
已删除 已完成的任务记录（30 天前）：0
已删除 过期会话：1

$ python manage.py cleanup_old_data          # 再跑一次
已删除 ...：0 （四项全 0，幂等）
```

那条 400 天的**待投递**记录被留下了（删的是 2 条不是 3 条）——正在重试的事件不能被清理任务从 worker 脚下抽走。

### 7. 生产拒绝开发用的开关

```
$ WEBHOOK_ALLOW_INSECURE_URLS=1 DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod ... manage.py check --deploy
django.core.exceptions.ImproperlyConfigured: WEBHOOK_ALLOW_INSECURE_URLS must not be set in production.
```

顺带一个真实佐证：验证期间有从前几轮留下的 worker 进程在跑，它们的环境**没有**这个开关，于是从队列里捡到我的 `http://127.0.0.1:9019/...` 任务时一律拒绝，投递记录里留下「地址不可用：地址必须是 https。」。这正是生产环境该有的行为。

### 8. 回归 + docker / caddy

```
$ uv run python -m pytest -q
421 passed in 25.09s

$ docker build -t sjtu-ow:019 .
sha256:bfa4080090d4da0f73338fef1636d5b7d3c706eccd57e7e6aa482805ca8057b8

$ docker run --rm -v ./deploy:/etc/caddy:ro caddy:2-alpine caddy validate --config /etc/caddy/Caddyfile
Valid configuration
```

### 9. 清理（这次查了全库）

本轮验证数据全删：赛事 1、报名 1、战队 1、账号 4、API 客户端 1、投递记录 7、调用日志 20、临时用户组 1、会话 22。

按 018 的教训**查了一次全库计数**，又清掉三类前几轮的残留：

- `wagtailembeds.Embed` 1 条（007 轮 B 站嵌入验收留下的）
- `core.PrerenderedPage` 11 条 + `prerendered/` 目录下的静态文件（010 轮留下的，其中 3 条指向 018 已经删掉的文章页）

现在库里只剩正常骨架：6 个页面（Root / 首页 / 资讯 / 用户协议 / 隐私政策 / 关于我们）、5 个文章分类、站点设置、5 个游戏模式、9 条排版规则，加 Wagtail 自己的权限和工作流结构。`User`、`Team`、`Tournament`、`ApiClient`、`WebhookDelivery`、`ApiRequestLog`、`PrerenderedPage` 全是 0。

**唯一没清的是 `django_tasks_database.DBTaskResult` 246 条**（231 成功 / 10 失败 / 5 就绪）。这是任务队列本身，不是验证夹具，而且有 worker 进程正在跑，从它脚下删行可能让它报错。清理任务的 30 天规则会处理它们。

## 设计偏差

**没有改设计文档。** 四点说明：

1. **`WEBHOOK_ALLOW_INSECURE_URLS` 是设计里没有的开关**。设计 11.8.3 要求接收地址必须是公网 https，但本地开发和验收都只能指向 `127.0.0.1`。加了这个开关，默认关，**生产设置里硬编码为 False 并且检测到环境变量就拒绝启动**。
2. **接口文档页放宽了 CSP**（只放开 `unsafe-inline`，不放开 `unsafe-eval`，不允许任何外部源），做法和已有的 `WagtailAdminCSPMiddleware` 一致。见「顺带发现」第 1 条。
3. **新增依赖 `drf-spectacular-sidecar`**，用来自托管 Swagger UI 的资源。这是 drf-spectacular 官方配套包，不走 CDN 只能这么做。
4. **多了一个兜底任务 `deliver_due_webhooks`**：扫描到期但没被执行的投递重新入队。设计没写，但延时任务丢了就再也没人管这条事件了。

## 未完成 / 不同意

1. `deploy/crontab.example` 里备份、静态资源清理、`PRAGMA optimize` 三条**注释掉了**，因为对应的命令（`backup` / `cleanup_static` / `optimize_db`）属于 M7 还没实现。写成可执行的会让 cron 每天失败一次。M7 做完要记得取消注释。
2. 重试依赖 `django-tasks` 的 `run_after` 延时任务。**没有验证过真实 worker 隔 24 小时后确实会执行**——验收里只验证了 `next_attempt_at` 的计算和任务返回值。标记为**未验证**。
3. Webhook「不保证顺序」是设计明确接受的，没有做顺序保证。

## 顺带发现

1. **Swagger UI 默认从 jsdelivr 取全部资源**，在本站 CSP 下整页空白（控制台 6 条 CSP 拦截），而且违反 README 里「自托管前端脚本（不走 CDN）」的规矩。详见 `review.md` A1。
2. `prerender --clear` 会保留记录并置为 `pending`，只删文件。这是有意设计（记录表就是「该生成哪些页」的清单），不是 bug。
3. `core/prerender.py` 的 `request_removal()` 在 `PRERENDER_ENABLED` 为关时直接返回，所以开发库里删页面不会清掉预渲染记录。这也是对的，但意味着开发库里的记录会慢慢和现实脱节。

## 需要确认

1. **备份命令 `manage.py backup` 什么时候做？** 设计 16.5 要求每天 03:00 备份，现在没有这个命令，crontab 里只能注释掉。这是 M7 的事，但它是所有定时任务里最不该缺的一条。
2. 018 留下的两个问题仍未定：报名的可见范围是否按 `source_client` 收窄；`review_not_allowed` / `invalid_state_transition` 是否补进设计 11.4 的错误码总表。

## 改动文件

```
integrations/models.py                     WebhookDelivery、WebhookEvent、DeliveryStatus
integrations/migrations/0002_*.py          新增
integrations/webhooks.py                   新增：payload、订阅过滤、签名、投递、重试
integrations/tasks.py                      新增：deliver_webhook、deliver_due_webhooks
integrations/notifications.py              新增：全部失败后通知超管
integrations/views.py                      文档页与 schema（超管限定）
integrations/urls.py                       /docs/ 与 /schema/
integrations/wagtail_hooks.py              Webhook 配置、测试事件、重发、投递列表
integrations/templates/integrations/       detail.html 增补、deliveries.html 新增
integrations/tests/test_webhooks.py        新增 33 个测试
integrations/tests/test_webhook_admin.py   新增 9 个测试
integrations/tests/test_docs_and_cleanup.py 新增 8 个测试
core/net.py                                新增：公网 https 地址校验（字体下载器也改用它）
core/fonts/download.py                     改用 core/net.py
core/middleware.py                         文档页的 CSP
core/management/commands/cleanup_old_data.py 新增
tournaments/registration.py                五种事件的触发点
sjtu_ow/settings/base.py                   SIDECAR、WEBHOOK_ALLOW_INSECURE_URLS
sjtu_ow/settings/prod.py                   生产拒绝该开关
deploy/crontab.example                     新增
pyproject.toml                             drf-spectacular-sidecar
README.md                                  Webhook、文档页、清理任务
```
