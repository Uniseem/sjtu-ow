# 222 M1 第一轮：Go 底座的骨架、配置、数据库和迁移

## 背景

重构（Vue 3 + Go）的 M0 已完成：D1–D4 拍板、五个实验做完（220）、设计草案（221）。按 `docs/rewrite-research/12-architecture.md` 11.2，M1（Go 底座）估计约 12 轮，本轮是第一轮：把 `server/` 立起来，做底座里最靠底的三样——配置、数据库访问（两池、WriteTx、看门狗）、迁移——外加 13 号文档 C 节点名的两件开工前准备。

## 本轮范围

### 做

1. **测试机装工具链**（13 号文档 C 节）：Go 1.26.5、Node 24.13、pnpm 装进 `/srv/sjtu-ow-check/`（官方 tarball / npm，核对 sha256），不动系统自带的 Node 20；staticcheck、govulncheck 用 `go install` 装进检查目录（版本钉死）。本机已有 Go 1.26.5、Node 24.13、pnpm 11.20（12 号文档 10 节）。
2. **`server/` 骨架**：`go.mod`（模块 `github.com/Uniseem/sjtu-ow/server`）、`cmd/sjtuow`（本轮只有 `migrate` 真实现；`serve`、`worker` 加载配置后明确报「后续轮次实现」）；`internal/platform/` 目录按 12 号文档 5.1 起。
3. **配置**（5.16）：环境变量读取，`SITE_URL`、`SIGNING_KEY`、`FIELD_ENCRYPTION_KEY` 缺了拒绝启动并指出缺哪个；`DATA_DIR` / `MEDIA_DIR` / `ASSETS_DIR` 有默认值；`TRUSTED_PROXIES` 解析成网段。新增依赖只有 12 号文档第 4 节选型表里已列的（`modernc.org/sqlite` BSD-3、`pressly/goose` MIT），许可证合规。
4. **数据库**（5.6）：
   - 两个连接池：写池 `MaxOpenConns(1)`、`_txlock=immediate`、`busy_timeout(5000)`、`journal_mode(WAL)`、`synchronous(NORMAL)`、`foreign_keys(ON)`；读池只读（`mode=ro`）若干连接；
   - `WriteTx`：对 `<库>.wlock` 拿 `flock(LOCK_EX)` → `BEGIN IMMEDIATE` → 提交或回滚 → 放锁；进程内用一个互斥量保证同一时刻只有一个 goroutine 处于锁区间（flock 是按打开的文件描述符算的，共享 fd 挡不住同进程的 goroutine）；
   - 看门狗：写事务超时——开发和测试里失败回滚（默认 1 秒，可注入），生产里记警告（默认 200 毫秒）；两个阈值可配置（13 号 C 节：最终数值等真实数据再定）；
   - 查询计数（测试用）：读池包一层按 context 计数的连接器，为后面的查询预算测试打底；
   - 时间格式：库里一律 UTC 文本 `YYYY-MM-DDTHH:MM:SS.ffffffZ`，格式化 / 解析函数 + 测试；二进制嵌 `time/tzdata`。
5. **迁移**：goose 的 SQL 文件嵌进二进制，`sjtuow migrate` 应用；00001 是空基线（第一个领域表在各自里程碑加），迁移可重复执行。
6. **两进程并发写测试**（M1 完成标准之一，种子是 220 的 E3）：`go test` 里测试进程 re-exec 自己做第二个进程，两边同时跑「读—改—写」步，断言零 `SQLITE_BUSY`、计数器和日志行数一致（不丢更新）。
7. **两容器共享数据卷的 flock 实测**（13 号 C 节）：测试机上 Docker 起两个容器挂同一个卷，用 `tools/txhammer`（走真实 `WriteTx` 的压测小程序）各压一轮，断言零失败、数据一致；脚本和结果放本轮目录。
8. **检查与 CI**：`scripts/check.sh` 加 Go 一段（`server/` 存在且找得到 go 才跑：gofmt、`go vet`、staticcheck、govulncheck、`go test ./...`），`remote-check.sh` 不用改就带上；CI 加一个 Go 任务（Action 按 SHA 固定、`permissions: contents: read`，14-7）。AGENTS.md「重构进行中」里的占位命令换成真的。

### 不做

- 注册表、错误形状、幂等键、限流、会话、Django 哈希、djsign、Fernet、任务队列、信纸、待发信、healthz、apigen——M1 后续轮次；
- `web/`、`e2e/`——M2；
- 镜像构建和 Compose 文件——M9（本轮的两容器实测用静态二进制 + scratch 直接跑，不构建项目镜像）；
- 看门狗生产阈值的最终数值（等导入后的真实事务时长分布）；
- `.env.example` 的更新（等 `serve` 真正能起来的那一轮一起）。

## 任务（每条带验证）

| # | 任务 | 验证 | 期望 |
|---|---|---|---|
| 1 | 测试机工具链 | 安装脚本输出 | 版本对、sha256 全过、系统 Node 20 没被动 |
| 2 | `server/` 骨架 + `migrate` | `go run ./cmd/sjtuow migrate`（带测试环境变量） | 建库、应用基线、再跑一遍不报错 |
| 3 | 配置 | `go test ./internal/platform/config/` | 缺必填报出缺哪个；有默认值的不缺也行 |
| 4 | WriteTx + 看门狗 | `go test ./internal/platform/db/` | 并发写零 busy 零丢失；超时事务回滚并报错；生产模式只警告 |
| 5 | 迁移 | `go test ./internal/platform/db/` | 幂等；版本表有记录 |
| 6 | 两进程并发写 | 同 4（re-exec 模式） | 零 busy、counter = 日志行数 |
| 7 | 两容器 flock | 测试机上的压测脚本 | 两容器各压一轮：failed=0、counter = 日志行数 |
| 8 | check.sh / CI | 测试机 `remote-check.sh` 整组 | Python 整组照旧全绿 + Go 一段全绿 |

## 验收标准

```sh
cd server
gofmt -l .            # 空
go vet ./...          # 干净
staticcheck ./...     # 干净
govulncheck ./...     # 无漏洞
go test ./...         # 全绿（含两进程并发写）
```

测试机：`bash scripts/remote-check.sh` 整组（Python 照旧 + 新的 Go 段）全绿；两容器压测脚本输出进 `RESULTS.txt`。本机不新增 Python 侧改动，Python 测试数量不应变化。
