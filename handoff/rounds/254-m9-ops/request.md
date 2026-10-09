# 254 M9 运维体系：备份恢复、运维命令、容器化与升级演练

## 背景

在 M1–M8 分别完成 Go 底座、前端底座、账号、内容、战队/成员、赛事/内战、通知与后台管理后，进入 M9（运维）。
根据 `docs/rewrite-research/12-architecture.md` 5.1、3.4 与 11.2：
1. 运维与生命周期管理子命令：`sjtuow backup`、`sjtuow restore`、`sjtuow createsuperuser`、`sjtuow reconcile`；
2. 备份恢复标准：
   - 包含 SQLite 完整热备份（使用 VACUUM INTO 或在线备份，零锁表）、全量图片媒体库、`manifest.json` 元数据校验清单；
   - 支持打包为标准 `.tar.gz` 归档；
   - 恢复支持新机器一条命令一键还原与完整性验证（`PRAGMA integrity_check`）；
3. 容器与 Compose 体系：
   - Go 服务端容器镜像构建（`Dockerfile.server`）：多阶段构建、静态编译、无 root 权限、内置上海时区；
   - 前端 SSR 与静态资产容器镜像（`Dockerfile.web`）：Node 24 LTS 构建、客户端产物与 SSR 服务分发；
   - 生产 Compose 配置（`deploy/docker-compose.new.yml`）与 Caddyfile（`deploy/Caddyfile.new`）匹配 12 号文档 3.4 路由规则；
4. 自动化升级与灾备恢复脚本：
   - `deploy/upgrade.sh`：自动备份当前库 -> 跑迁移 -> 平滑重启 -> 健康检查 `/healthz`；
   - `deploy/restore.sh`：一键冷备恢复脚本。

## 本轮范围

做：
1. `server/internal/ops/`:
   - `backup.go`: 实现 `Backup(ctx, dataDir, outPath)`，利用 `VACUUM INTO` 导出事务一致的 SQLite 副本，结合 `media/` 目录与 `manifest.json` 打包为 `.tar.gz`；
   - `restore.go`: 实现 `Restore(ctx, tarPath, dataDir)`，校验签名/元数据，解压至数据库与媒体目录，运行 `PRAGMA integrity_check` 校验；
   - `superuser.go`: 实现 `CreateSuperuser(...)` 命令行直接创建已验证的超级管理员；
   - `reconcile.go`: 实现 `Reconcile(...)` 检查库内健康度、孤立媒体、悬空队长等；
   - `backup_test.go`: 完整备份与恢复演练单元测试。
2. 扩展 `server/cmd/sjtuow/main.go`:
   - 接入子命令：`backup`, `restore`, `createsuperuser`, `reconcile`。
3. 生产部署配置与脚本：
   - `deploy/Dockerfile.server`
   - `deploy/Dockerfile.web`
   - `deploy/docker-compose.new.yml`
   - `deploy/Caddyfile.new`
   - `deploy/upgrade.sh`
   - `deploy/restore.sh`
4. 测试机整组检查全绿验证。

不做：
- 异地 R2 存储定时同步脚本（割接前后配合用户配置 R2 密钥时完成）。

## 验收

- `go test ./internal/ops/...` 及整组测试全过。
- 备份和恢复功能在临时目录测试成功演练。
- 测试机整组检查 `scripts/remote-check.sh` 退出码 0。
