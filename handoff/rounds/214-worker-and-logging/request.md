# 214 轮要求：worker 和日志（C1、C2、C3）

210 全站复核（`rounds/210-full-review/review.md`）建议顺序第 3 步：worker 和日志，改完在服务器上真演练一次（064 的坑：web 里跑通不等于 worker 能跑）。

## 范围

### C1：SMTP 连接没有超时

`core/mail.py` 的 `build_smtp_backend` 不传 `timeout`，一次 TLS 握手后不响应的发信让单线程 worker 永久停摆，而心跳线程照写、`/healthz` 照绿（复核 C1，`core/mail.py:188-202`）。

修法：SMTP 后端加连接/读写超时（固定 20 秒，写进设计 10.1；不加环境变量，少一个旋钮）。超时后走既有的失败重试（1 分钟、5 分钟、30 分钟）。

### C2：worker 被 SIGKILL 后认领的任务永远 RUNNING

升级重建容器默认 10 秒宽限，正在跑的任务卡成 RUNNING 后没有任何代码复位它（复核 C2）。

修法：设计 16.2 写明 worker 只允许 1 个实例，所以 `run_worker` 启动时把所有 RUNNING 任务放回 READY 是安全的——正在跑它的进程已经死了（否则新 worker 不会启动）。在 `run_worker` 命令里、开始接单之前复位，记一条日志（任务数、任务名）。复跑可能让发了一半的群发重发一遍，设计里写明这个取舍。

### C3：生产环境 500 没有任何日志（含 C11）

`prod.LOGGING` 只配了 `sjtu_ow.mail`，`django.request` 的 ERROR 落到 Django 默认的 `console`（`require_debug_true`，生产为 False）和 `mail_admins`（`ADMINS` 空），traceback 哪都不去；500 页上的「请求编号」从没写进日志，还优先取客户端自带的 `X-Request-ID`（C11，复核 C3）。

修法：
1. `prod.LOGGING` 加 `django.request`（ERROR 起）输出到容器标准输出。
2. 请求编号一律由服务端生成，不再采用客户端的 `X-Request-ID`（响应头照回）。
3. 500 视图用自己的 logger 记一行（请求编号、路径），和 `django.request` 的 traceback 能对上。

## 不做

- 不加 Sentry/GlitchTip（设计 16.6 本来就是「建议」，不新增依赖）
- 不动 worker 容器 healthcheck、不动 `mail_admins`
- 低优先级的其余条目按复核原话「按顺手修」，不在本轮

## 验收

- 每条新规则有「拆掉就红」的测试，跑变异验证（先基线）
- 本地全量 + 测试机整组检查全绿
- **在测试机上真演练**（064 的坑）：
  1. C2：排一个慢任务，`kill -9` worker 容器，重启后任务被复位并跑完
  2. C1：把测试机站点的 SMTP 指到黑洞地址，触发一封信，worker 约 20 秒后报超时失败、继续跑后面的任务，完事恢复设置
  3. C3：测试机 web 容器里用 `django.request` logger 发一条 ERROR，确认出现在 `docker logs`；本地用生产配置跑一条 500 测试确认 traceback 落日志
- 设计文档先改（10.1、16.2/16.5、15.5/13.15），附录 D 记版本
