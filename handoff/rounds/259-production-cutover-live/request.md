# 259 生产停机割接正式执行与新栈全面上线

## 背景
用户发出明确指令「那就正式替换」，指令正式将生产环境（VPS `169.58.217.180:22887` 及外部域名 `https://sjtu.ow-shanghaiuniversity.com/`）从旧 Django 6 + Wagtail 8 架构切换至 Vue 3 + Go 新栈集群架构。
前期已在测试机（`sjtu-ow-test`）使用 4.6MB 真实全量库跑通 `rehearse.sh` 模拟演练，确认全量业务契约覆盖 100%、对拍一致性 100%、12 项业务实体行数 100% MATCH。本轮正式执行停机割接流水线。

## 本轮范围
1. 建立生产环境不可逆快照与零丢数据防护：在服务器宿主备份目录保存旧栈 SQLite 只读快照及环境配置备份；
2. 自动化执行割接流水线（`deploy/cutover.sh`）：
   - 优雅下线旧栈 Django 容器；
   - 执行 Go 新栈表结构迁移（`sjtuow migrate` 至版本 16）；
   - 执行历史数据只读只增导入（`sjtuow import`）；
   - 执行数据库一致性与新旧对账自检（`sjtuow reconcile`）；
   - 启动新栈全量生产集群（`server` + `worker` + `web` + `proxy`）；
3. 容器镜像与运行时加固：
   - 修复 `cutover.sh` 中 Compose 项目名（`-p sjtu-ow`）确保挂载卷归属一致；
   - 修复 Dockerfile ENTRYPOINT 与命令行子命令调用参数；
   - 针对 Vue 3 SSR 服务配置 `ssr.noExternal: true`，消除生产容器内缺失 node_modules 的启动报错；
4. 线上验收与冒烟健康检查：
   - 验证 `/healthz` 四项健康指标（database, disk, task_backlog, worker_heartbeat）全部 OK；
   - 验证生产端口 22887 及外部 HTTPS 域名反代可达；
   - 验证前台 SSR 首屏渲染、严格 CSP 响应头以及 API 路由正常；
5. 更新项目进度文档 `handoff/STATUS.md`。

## 验收标准
- 停机窗口严格控制在 15 分钟之内（实测 16 秒）；
- 存量数据库零丢失，12 项业务实体全部 100% 对账 MATCH；
- `PRAGMA integrity_check` 与 `foreign_key_check` 全 PASS；
- 新栈 4 个容器全量处于 Running / Healthy 状态；
- `curl -fsSL http://127.0.0.1:22887/healthz` 响应 200 OK；
- 外部域名 `https://sjtu.ow-shanghaiuniversity.com/` 正常提供服务。
