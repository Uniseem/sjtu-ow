# 254 M9 运维体系：备份恢复、运维命令、容器化与升级演练报告

## 做了什么

根据 `docs/rewrite-research/12-architecture.md` 3.4、5.1 与 11.2：

1. **备份与恢复体系 (`server/internal/ops/`)**:
   - `backup.go`:
     - 利用 SQLite 原生 `VACUUM INTO` 实行原子快照（零锁表、合并 WAL、紧凑存储）；
     - 自动检测并打包 `sjtuow.sqlite3`、`manifest.json` 元数据、`originals/` 原图目录与 `media/` 缩略图目录；
     - 严格遵循 09-1 准则：先写入临时文件、调用 `Sync()` 进行 fsync 刷盘，再原子重命名为目标 `.tar.gz` 归档；
     - 记录清单包含数据库 SHA256 校验和、大小、模式版本、媒体文件计数及生成时间戳。
   - `restore.go`:
     - 严格遵循 09-5 准则：在 `dataDir` 卷私有临时目录（0700 权限）流式解包，不落 `/tmp`；
     - 严格防范目录遍历（`safeJoin` 防 `..` 与绝对路径攻击）；
     - 解压后比对数据库文件 SHA256 校验和；
     - 运行只读 SQLite 执行 `PRAGMA integrity_check` 与 `PRAGMA foreign_key_check`；
     - 默认仅进行演练校验（dry-run，不破坏任何现有文件）；`--yes` 参数下执行原子替换（清理旧 `-wal`/`-shm`，备份旧文件，更新库与媒体）。
   - `backup_test.go`:
     - 涵盖备份、dry-run 演练、真实恢复、数据行数核验、原始媒体文件一致性比对。

2. **运维与生命周期管理子命令 (`server/internal/ops/` & `server/cmd/sjtuow/`)**:
   - `createsuperuser`:
     - 支持参数 `--email`, `--nickname`, `--password`, `--is-sjtu` 或标准输入交互；
     - 遵循规则 15：服务端背书邮箱直接标记为已验证（`email_verified_at` 填当前时间）；
     - 执行 Django 兼容的四项密码安全强度校验（`auth.Validate`）；
     - Argon2id 密码哈希派生并原子写入数据库。
   - `reconcile`:
     - 运行 `PRAGMA integrity_check` 与 `PRAGMA foreign_key_check`；
     - 统计输出用户域全量指标（总数、活跃、超管、已验证、交大成员）；
     - 输出新表与存量旧表行数比对（支持接入 Django 旧库对照验证）；
     - 抽样核验关键用户在新旧库间的超管与活跃标志一致性。
   - 子命令全面挂载至 `sjtuow` 二进制：`backup`, `restore`, `createsuperuser`, `reconcile`。

3. **容器化与 Compose 部署配置 (`deploy/`)**:
   - `Dockerfile.server`:
     - Go 1.26 多阶段构建，静态编译 `CGO_ENABLED=0`，去除符号表；
     - Alpine 3.21 运行时，非 root 用户 `app`（UID 10001），内置 `Asia/Shanghai` 时区与 CA 证书。
   - `Dockerfile.web`:
     - Node 24 LTS 多阶段构建，pnpm 依赖缓存与 SSR 生产构建；
     - 非 root 用户运行 Vue 3 SSR 服务（`dist/server/server.js`）。
   - `Caddyfile.new`:
     - 完全匹配 12 号文档 3.4 路由规格：
       - `/assets/*`: 1 年 immutable 缓存；
       - `/static/img/*`: 1 天缓存兼容静态图；
       - `/media/r/*`: 1 年缓存缩略图，缺失时转发后端 Go 懒生成；
       - `/media/images/*` 与 `/media/fonts/*`: 1 年静态分发；
       - `/media/*`: 404 严格拦截（原图防泄漏）；
       - `/api/*`, `/healthz`, `/calendar/*`, `/sitemap.xml`, `/robots.txt`: 转发 Go 后端。
   - `docker-compose.new.yml`:
     - 包含 `server`, `worker`, `web`, `proxy` 四大服务及持久化卷 `sjtuow_data`, `sjtuow_media`, `sjtuow_assets`。
   - `upgrade.sh` & `restore.sh`:
     - 生产平滑升级脚本（自动前置备份 -> 构建 -> 迁移 -> 重启 -> 冒烟检查）；
     - 灾备一键恢复与演练脚本。

## 验证

- `go test -v ./internal/ops/...`: 全部通过（备份、恢复、超管创建、一致性对账）。
- 测试机整组检查（`bash scripts/remote-check.sh`）全绿：
  - 日志：`sjtu-ow-test:/srv/sjtu-ow-check/runs/20261009-152058-e3b2282.log`
  - 退出码：0
  - Go 检查：gofmt、go vet、staticcheck、govulncheck（0 漏洞）全过。
  - Go 测试：`go test ./...` 全量包通过。
  - Web 测试：`pnpm test` 全部通过，SSR 与客户端打包正常，首页壳 gzip 79593 字节（BUDGET-OK）。

