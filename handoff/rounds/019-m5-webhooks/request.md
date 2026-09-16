# 019 Webhook、接口文档与清理任务

M5 的最后一轮。做完 M5 就完整了：设计 3213 行的 M5 验收标准要求「用第 11 章的示例代码写一个模拟上游，跑通读取、审核、推送赛事、**接收 Webhook**」。

## 范围

设计 11.8（Webhook）、11.11（接口文档）、12.10.3（WebhookDelivery）、16.5（每天 04:00 的清理任务）。

## 任务

### T1 WebhookDelivery 数据表

按设计 12.10.3 建表：`client`、`event_id`（uuid 唯一）、`event_type`、`payload`（JSON，事件产生时就固定下来）、`status`（`pending` / `succeeded` / `failed`）、`attempts`、`next_attempt_at`、`last_status_code`、`last_error`、`delivered_at`。索引 `(status, next_attempt_at)`。

### T2 事件构造与订阅过滤

五种事件（11.8.1）：`registration.submitted`、`registration.roster_synced`、`registration.withdrawn`、`registration.status_changed`、`ping`。

两层过滤，缺一不可：

1. 客户端订阅了这个事件（`webhook_events`）
2. 这个赛事和这个客户端相关：审核模式是 `upstream` 或 `two_stage`，**或者**赛事是这个客户端自己推送的

还要：配了 `webhook_url`、客户端可用（`is_active` 且未吊销）。

`thin` 和 `full` 两种请求体（11.8.2）。`full` 在 `data` 里多一个 `registration` 对象，展开范围是这个客户端**被允许的全部展开项，但不含 `logs`**。`tournament_external_id` 沿用赛事对象的规则：只有赛事是这个客户端推的才有值。

**payload 在事件产生时就生成并存下来**，重试时不重新生成——这是设计 12.10.3 明确写的，不要偷懒改成投递时再算。

### T3 签名与投递

请求头按 11.8.2：`X-Webhook-Id`、`X-Webhook-Event`、`X-Webhook-Timestamp`、`X-Webhook-Signature`（`sha256=` + HMAC-SHA256(secret, `timestamp` + `.` + 原始请求体)）。

投递规则（11.8.3）：

- 10 秒超时，2xx 算成功
- **不跟随重定向，3xx 算失败**
- `webhook_url` 必须是 HTTPS，且不能指向内网或本机——**复用 008/009 的 SSRF 防护思路**，在保存客户端时校验，投递时再查一次（DNS 可能变）
- 重试间隔 1 分钟、5 分钟、30 分钟、2 小时、6 小时、12 小时、24 小时，**加首次一共 8 次**
- 重试时 `X-Webhook-Id` 不变
- 全部失败后标记 `failed`，发邮件给超级管理员

### T4 接到业务流程上

`tournaments/registration.py:264` 已经留了 `# M5: deliver the registration.submitted / roster_synced webhook here.` 的标记。所有触发点都要用 `transaction.on_commit`，事务回滚不能发事件。

触发点：提交 / 重新提交、同步名单、撤回、状态变化（本站管理员和上游审核都算，`actor_type` 要如实填）。

### T5 后台

客户端详情页：Webhook 配置、「发送测试事件」按钮（`ping`）、最近的投递记录（事件类型、状态、尝试次数、最后状态码、时间）、失败的可以手动重发（**事件 ID 不变**）。

### T6 接口文档页

`/api/v1/docs/`，drf-spectacular 生成，**只有登录后台的超级管理员能看**（设计 11.11）。非超管和匿名访问都不能看到内容。

### T7 清理任务

设计 16.5 每天 04:00 的那一条：API 调用日志 90 天、Webhook 投递记录 180 天、已完成任务记录 30 天、过期会话。做成一个 management command，在 `deploy/` 的 crontab 示例里排到 04:00（`CRON_TZ=Asia/Shanghai`）。

## 测试要求

至少覆盖：五种事件的构造、两层订阅过滤（订阅了但赛事无关 / 赛事相关但没订阅 / 都满足）、`thin` 和 `full` 两种请求体、`full` 不含 `logs`、`tournament_external_id` 的可见性、签名算法**用设计 11.8.2 的 `verify_webhook` 示例代码原样校验**、2xx 成功、3xx 不跟随且算失败、超时算失败、8 次重试的间隔序列、重试时事件 ID 不变、全失败后发邮件、手动重发、HTTPS 与内网地址校验、`on_commit` 语义（事务回滚不发事件）、文档页的权限、清理任务的四类数据各删对了。

## 验收标准

1. `ruff` / `pytest` / `makemigrations --check` / 生产 `check --deploy` 全部干净
2. **起一个真实的 HTTP 接收端**，让本站真发 Webhook 过去，用设计 11.8.2 的示例代码验签，贴出收到的请求头和请求体
3. 让接收端分别返回 500、302、超时，贴出三次的投递记录和 `next_attempt_at`
4. 贴出后台「发送测试事件」和手动重发的结果
5. 贴出 `/api/v1/docs/` 对超管和非超管的不同结果
6. 跑一次清理任务，贴出删除计数
7. 回归 + `docker build` + `caddy validate`
8. 清理验证数据，**并查一次全库计数确认干净**（018 的教训）
9. git 提交，信息以 `019:` 开头

## 复核清单（给 Grok）

1. payload 是不是真的在事件产生时固定下来的？改了报名之后重试，发出去的还是不是老 payload？
2. 两层订阅过滤有没有漏？一个只订阅了 `ping` 的客户端会不会收到状态变化？
3. `full` 模式会不会把 `logs` 或联系方式带出去？
4. 3xx 真的没跟随吗？（用一个 302 到内网地址的接收端试）
5. 事务回滚时会不会已经把事件发出去了？
6. `/api/v1/docs/` 匿名访问会不会泄漏接口结构？
