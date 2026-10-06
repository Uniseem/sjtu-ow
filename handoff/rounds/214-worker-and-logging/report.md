# 214 实现报告

## 结论

完成实现与验证。210 复核建议顺序第 3 步的 C1、C2、C3（worker 和日志）全部修好：SMTP 20 秒超时、worker 启动复位残留的 RUNNING 任务、生产 500 落日志且请求编号只由服务器生成。新增 6 条测试全绿，6 处变异全部被抓到；本地全量 1958 条全绿；测试机整组检查 1959 条全绿。服务器真演练：C2（SIGKILL 复位）和 C3（生产日志落盘）在测试机上真跑过；**C1 的黑洞演练没做成**（见「顺带发现」，超时本身由测试钉住）。**正式站尚未升级**（用户关机，下次开工第一件事）。设计 v7.17 先行。

正式站升级（2026-10-07 01:40 北京时间，补记）：先核对服务器上全部跟踪文件和 213 提交一致（逐个 `git hash-object`），再 `backup`（`sjtu-ow-20261007-014008.tar.gz`，210.8 MB；异地备份未开启），ship214（10 个文件）上传后 `deploy_ship.sh 214`：镜像重建、无迁移可应用、`prerender` 全量生成成功 12 失败 0、healthz `ok`（worker 心跳 5 秒前、任务积压正常，磁盘剩 24.4%）；服务器上 10 个文件和 214 提交一致；`migrate --check` 干净；本机经域名访问首页 HTTP 200。

## 逐条结果

1. **C1（SMTP 无超时）**：`core/mail.py` 新增 `SMTP_TIMEOUT_SECONDS = 20`，`build_smtp_backend` 传给 Django 的 SMTP 后端（连接和读写都受它管）。超时后按既有节奏重试（1/5/30 分钟）。设计 10.1 同步。测试 `test_smtp_backend_gives_up_after_20_seconds` 断言后端实例的 `timeout`。
2. **C2（被杀 worker 的任务永远 RUNNING）**：`core/worker.py` 新增 `reset_orphaned_running_tasks()`——设计 16.2 写明 worker 只有 1 个实例，启动时还标着 RUNNING 的任务，认领它的进程一定死了，全部放回 READY 并记一条警告日志（几个、任务名）；`run_worker` 命令在开始接单前调用。取舍写进设计 16.2：跑到一半被杀的任务从头重跑，群发可能给一部分人重发一封。两条测试：服务函数（RUNNING→READY、started_at 清空、已完成的不动）和命令接线（patch 掉心跳和接单，断言启动时复位发生）。
3. **C3（生产 500 无日志，含 C11）**：`prod.LOGGING` 加 `django.request`（ERROR 起，落容器标准输出——Django 默认的 console 处理器有 `require_debug_true` 门、mail_admins 的 ADMINS 为空，traceback 原来哪都不去）和 `sjtu_ow.errors`；`core/views.py` 的 `server_error` 记一行 `500 request_id=… path=…`，和 django.request 的 traceback 能对上；`RequestIDMiddleware` 不再采用客户端的 `X-Request-ID`，一律服务端生成（响应头照回）。三条测试：生产配置的子进程断言（`test_security_guards.py`）、客户端伪造编号被无视（响应头不是伪造值）、500 日志行带编号和路径（caplog）。
4. **变异验证**：`mutate.py` 6 处全部被抓到，基线前后全绿（输出见下）。

## 验收输出

本地：`uv run ruff check . && uv run ruff format --check .` 全过（407 files）；`uv run pytest -q` 全量 `1958 passed, 1 skipped in 135.85s`。

变异验证（`uv run python handoff/rounds/214-worker-and-logging/mutate.py`，2026-10-06 本机）：

```
基线全绿，开始变异。
ok C1: SMTP 不带超时：改坏后红了（1 条）
ok C2: 复位不写回 READY：改坏后红了（1 条）
ok C2: run_worker 启动不复位：改坏后红了（1 条）
ok C3: 请求编号又采用客户端的：改坏后红了（1 条）
ok C3: 500 不记日志行：改坏后红了（1 条）
ok C3: 生产 django.request 不落日志：改坏后红了（1 条）
改回后基线全绿。
```

测试机整组检查（`bash scripts/remote-check.sh`，服务器时间 2026-10-06 22:14–22:15）：

```
== pytest (14:14:31)
1959 条测试分成 4 片
分片 1：490 passed in 67.66s (0:01:07)
分片 2：490 passed in 67.61s (0:01:07)
分片 3：490 passed in 70.57s (0:01:10)
分片 4：489 passed in 60.07s (0:01:00)
== 迁移 (14:15:47)
No changes detected
== 生产配置 (14:15:49)
System check identified no issues (0 silenced).
== 错误页和模板一致 (14:15:50)
== Docker 镜像 (14:15:51)
构建成功：9ff49d8168b0
== 全部通过 (14:15:52)
```

服务器真演练（064 的坑；在测试机 `/srv/sjtu-ow-check/repo`、独立草稿库 `/tmp/drill214/`）：

**C2，worker 运行途中 `kill -9`**：

```
worker 运行中认领（模拟跑到一半）: RUNNING
kill -9 之后: RUNNING                    ← 旧毛病：永远停在这
Reset 1 orphaned running task(s): prerender_page
重启 worker 之后: SUCCESSFUL             ← 新行为：复位并重跑
```

**C3，生产配置下写日志**（两条都出现在标准输出，即容器日志里）：

```
DRILL-C3 traceback 会在这里
500 request_id=drillc3def456 path=/drill
```

**C1，SMTP 黑洞（收下连接不回应）**：**未复现成功**。三轮演练里邮件任务都是 0 秒 SUCCESSFUL：第一轮发现开发配置的 `EMAIL_DELIVERY_BACKEND` 是 console（根本不碰 SMTP），改用生产配置后第二轮仍瞬间成功，原因没查完（怀疑草稿库里有两行 SiteSettings、`load()` 拿到空行走了未配置分支，或 2525 端口旧监听器残留），用户关机时间到，没有继续。SMTP 超时本身由单元测试钉住（`build_smtp_backend` 的 `timeout` 参数，变异验证确认拆掉会红）；黑洞演练留给下次开工补做。

## 顺带发现（重要，留给后面轮次/用户）

- **测试机的公网 IPv4 没了**：2026-10-06 约 21:21（服务器 13:21 UTC）前后，eth0 上只剩 IPv6（`2a0e:6a80:3:9c7::/64`），原来的 `189.24.110.12:2222` 转发口对所有来源「连上即断」（从正式站探也一样，不是封 IP）；本机 DNS 转发进程（127.0.2.2/127.0.2.3）同时消失，整机 DNS 全灭。排查后把本机 SSH 配置的 `sjtu-ow-test` 改成 IPv6 + 22 直连，并在测试机上把 eth0 的 DNS 临时指到公共解析（`resolvectl dns eth0 ...`，运行态、重启失效）。**那套线路优化转发如果还要用，需要用户去转发机上把 2222 的后端地址改成 IPv6 或新地址；Docker 的出站、容器里的 DNS 是否受影响还没查。**（2026-10-07 补记：转发恢复了，本机经 `189.24.110.12:2222` 登得上测试机，主机密钥按 `HostKeyAlias` 核对一致；本机这时反而没有 IPv6，直连报 No route to host。`sjtu-ow-test` 已改回走转发，和 `AGENTS.md` 写的一样。）
- 演练中发现 Wagtail 的 `SiteSettings.load()` 在表空时会自动建行；往表里 `objects.create()` 第二行不会生效（`load()` 拿第一行）。以后测试 SMTP 配置要改 `load()` 那一行。
- 上一轮（213）报告的「顺带发现」继续有效：赛事 `publish` 只拦 CANCELLED。

## 设计偏差

无。文档先改（design.md v7.17：10.1 SMTP 超时、16.2 worker 启动复位与取舍、15.5 应用日志带请求编号、13.15 请求编号服务器生成，附录 D 记版本），实现照文档。
