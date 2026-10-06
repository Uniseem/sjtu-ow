# 214 复核结果（自查）

## 结论

自查通过。连做轮次，等独立复核后按 `REVIEW-GUIDE.md` 追加结论。**两项未了**：C1 的黑洞演练没复现成功（测试钉住、演练待补）；正式站未升级（用户关机）。都写进了 report.md 和 STATUS.md。

## 验证记录

- **变异验证 6 处全部被抓**（`mutate.py`，先基线后变异；恢复后清 `__pycache__`）：C1 超时参数、C2 服务函数和命令接线各一处、C3 三处（中间件、500 日志行、生产 LOGGING）。改回后基线全绿。
- **整组检查在测试机**：1959 条分 4 片全绿，ruff / Tailwind / 迁移 / `check --deploy` / 错误页一致性 / Docker 构建全部通过。
- **真演练在测试机上做**（064 的坑）：C2 用 `kill -9` 真杀——杀掉后任务停在 RUNNING（旧毛病重现），重启 worker 日志打出 `Reset 1 orphaned running task(s)`、任务跑到 SUCCESSFUL；C3 用生产配置起进程，django.request 和 sjtu_ow.errors 两条日志都落标准输出。C1 未复现（见报告）。
- **逐行重读关键 diff**：
  - C2 的安全前提核过：设计 16.2「worker 只能有 1 个实例」，compose 里 worker 单副本；复位只在 `run_worker` 启动时跑一次，不会把正在跑的任务抢走。
  - C2 的复位只动 `status` 和 `started_at`，`worker_ids` 历史保留；`task_name` 属性对找不到代码的任务有 ImportError 兜底，日志不会因此炸。
  - C3 的中间件：响应头回的仍是服务器生成的编号；`server_error` 不再读客户端头（`request.request_id` 由中间件保证，兜空字符串）。
  - C1：`timeout` 传给 Django SMTP 后端，连接和读横幅都受它管（Django 源码里 `self.timeout` 用于 `socket.create_connection` 和 `self.connection.timeout`）。

## 发现的问题

- **必须修，本轮已修**：C1、C2、C3 本体。
- **没修完/没做**：C1 黑洞演练未复现（两轮没走通投递路径：dev 配置的投递后端是 console；换生产配置后仍瞬间成功，原因没查完）；正式站未升级。两者都是下次开工的第一件事。
- **建议修（留给后面轮次）**：测试机 IPv4 消失带来一串运维问题（转发机后端地址、容器出站 DNS），报告里写了；赛事 `publish` 同形洞（213 起挂着）。

## 判断里最没把握的

- C1 的超时语义：Django SMTP 后端的 `timeout` 经 `socket.create_connection` 作用于连接期，连接成功后赋给 `self.connection.timeout` 作用于读写——读的是 Django 13 源码，但黑洞演练没跑成，行为级证据只有单元测试。
- 测试机的 DNS 修复是运行态的（`resolvectl dns eth0`），重启失效；那台机器本来的 DNS 是谁提供的（127.0.2.2/127.0.2.3）没查到，可能和消失的转发是同一套。

## 文档更新

- `docs/design.md`：v7.17（10.1、16.2、15.5、13.15 四处 + 附录 D 一行）
- `handoff/STATUS.md`：214 段落、头部 round/next/updated、轮次表加一行
- 轮次目录：request.md / report.md / review.md（本文件）/ mutate.py
