# 222 实现报告

## 结论

完成。M1 第一轮立起来了：测试机工具链、`server/` 骨架、配置、数据库两池 / WriteTx / 看门狗、迁移机制、两进程并发写测试、两容器 flock 实测；三处变异全部被抓到。

## 逐条结果

### 1. 测试机工具链（13 号文档 C 节）

装进 `/srv/sjtu-ow-check/`（安装脚本 `install-toolchain.sh`，可重复跑）：

- **Go 1.26.5**（`go/`）：官方 tarball，sha256 核对（`5c2c3b1…3f053`）
- **Node 24.13 + pnpm 11.20.0**（`node24/`）：官方 tarball，sha256 核对；系统自带的 Node 20.19.2 没动（`/usr/bin/node` 照旧）
- **staticcheck 2026.2.1（v0.8.1）、govulncheck v1.8.0**（`gobin/`）：`go install` 钉版本装的，模块完整性由 Go 的校验和数据库核对
- 缓存（`gopath/ gocache/ gomodcache/`）也在检查目录这块盘上，和 uv 一样

第一次跑砸在 pnpm：`./node24/bin/npm` 的 shebang 是 `#!/usr/bin/env node`，解析到系统 Node 20，pnpm 11 要 ≥22.13。修法是把 `node24/bin` 放进 PATH 最前再调 npm/pnpm。这个坑写进了 AGENTS.md。

### 2. `server/` 骨架

```
server/
├── go.mod                    github.com/Uniseem/sjtu-ow/server，go 1.26.5
├── cmd/sjtuow/               migrate 真实现；serve/worker 先过配置再报「后续轮次实现」
├── db/embed.go + migrations/ goose SQL 嵌进二进制；00001 是空基线
├── internal/platform/
│   ├── config/               环境变量，缺必填拒绝启动
│   ├── clock/                可注入时钟
│   └── db/                   两池、WriteTx、看门狗、查询计数、时间格式、迁移
└── tools/txhammer/           用真实 WriteTx 压并发的工具（容器实测用）
```

二进制嵌了 `time/tzdata`（12 号文档 5.6）。

### 3. 配置（5.16）

`SITE_URL`、`SIGNING_KEY`、`FIELD_ENCRYPTION_KEY` 缺了拒绝启动，报出全部缺项；`SITE_URL` 得是完整 http(s) 地址；生产模式（`SJTUOW_ENV=prod`，这个变量名是本轮新增的，12 号文档没定名）下密钥至少 32 字符；`DATA_DIR/MEDIA_DIR/ASSETS_DIR` 默认 `data/media/assets`；`TRUSTED_PROXIES` 解析成网段、坏值拒绝。

### 4. 数据库（5.6）

- **两池**：写池 `MaxOpenConns(1)`、`_txlock=immediate`、`busy_timeout(5000)`、`journal_mode(WAL)`、`synchronous(NORMAL)`、`foreign_keys(ON)`；读池 `mode=ro`、最多 4 连接
- **WriteTx**：进程内互斥量（flock 按打开的文件描述符记账，同进程共享 fd 的 goroutine 互相挡不住，包注释里写明了）→ 对 `<库>.wlock` 拿 `flock(LOCK_EX)` → `BEGIN IMMEDIATE` → fn → **先判超时再提交**（不理会 ctx 取消、慢慢做完的事务也不会落库——写的过程中发现并修掉的一个真问题）→ 提交或回滚 → 放锁
- **看门狗**：开发和测试超过 1 秒回滚并报 `ErrSlowTx`（到点先取消 ctx，让正在跑的查询尽快停）；生产超过 200 毫秒记 slog 警告、不拦；两个阈值都可注入（13 号 C 节：最终数值等真实数据）
- **查询计数**：`Counter.Counted(DBTX)` 包装（sqlc 认的接口），查询预算测试的基础
- **时间**：库里一律 UTC 文本 `YYYY-MM-DDTHH:MM:SS.ffffffZ`，`FormatUTC/ParseUTC`；ParseUTC 也认带偏移、没有微秒的旧写法（导入旧库会遇到）

### 5. 迁移

goose v3.28 的 Provider API（12 号文档写 `WithEmbedFS` 时查的旧接口，v3.28 里已经没有了——第一次编译就暴露，改成 Provider，少一层全局状态）。`sjtuow migrate` 建库并应用；重复跑是无操作。

### 6. 测试（`go test ./...`）

- config：缺必填报出缺哪个、一次报全、默认值、坏 URL/网段拒绝、生产短密钥拒绝、空白裁剪（8 个测试）
- db：读写池互通、业务错误回滚、进程内 8 goroutine 并发零失败零丢失、**两进程并发写**（测试 re-exec 自己当第二个进程，加本进程共三方，counter=log=1400）、**flock 排队**（对方握锁 7 秒 > busy_timeout 5 秒，本进程排队成功而不是 SQLITE_BUSY）、看门狗失败路径（慢事务不落库）、看门狗警告路径（记警告但提交）、迁移幂等、查询计数
- timefmt：格式、往返、字典序=时间序、旧写法兼容
- clock：固定时钟、真时钟

### 7. 两容器 flock 实测（13 号 C 节）

`RESULTS.txt`。两容器同时压共享卷上的同一个库：各 2000 步全部成功、`counter=4000 log_rows=4000`、零 SQLITE_BUSY、合计约 880 事务/秒、worst_step 190ms（排队而非忙等）。**跨容器 flock 有效，不需要退路。**

### 8. 检查与 CI

- `scripts/check.sh` 加「Go（新栈）」一段（server/go.mod 在且找得到 go 才跑：gofmt、vet、staticcheck、govulncheck、test），`remote-check.sh` 的任务脚本把检查目录里的工具链导进 PATH（装没装都不影响 Python 检查）
- CI 加 `go` 任务：checkout 和 setup-go 都按 commit SHA 固定、`permissions: contents: read`（14-7）；staticcheck/govulncheck 钉版本 `go install`
- AGENTS.md：「重构进行中」的占位命令换成真的；**「所有编译和测试一律先在测试机上做」（用户 2026-10-08 写死）**写进了 AGENTS.md 两处

## 验收输出

全部在测试机上跑（用户 2026-10-08 的规矩），本机只做了 gofmt 格式化和依赖清单的生成（`go mod tidy` 在测试机上跑、go.mod/go.sum 取回来）。

Go 全套（日志 20261008-120035-52fa4c0）：

```
?  	github.com/Uniseem/sjtu-ow/server/cmd/sjtuow	[no test files]
?  	github.com/Uniseem/sjtu-ow/server/db	[no test files]
ok 	github.com/Uniseem/sjtu-ow/server/internal/platform/clock	(cached)
ok 	github.com/Uniseem/sjtu-ow/server/internal/platform/config	(cached)
ok 	github.com/Uniseem/sjtu-ow/server/internal/platform/db	7.728s
?  	github.com/Uniseem/sjtu-ow/server/tools/txhammer	[no test files]
GO-ALL-GREEN
```

（gofmt、`go vet`、staticcheck 同轮先过；govulncheck 同轮输出：`No vulnerabilities found. Your code is affected by 0 vulnerabilities.`）

变异验证（都是单点改动、在测试机上跑、期望红）：

| 变异 | 改动 | 结果 |
|---|---|---|
| A 去 flock | `LOCK_EX` → `LOCK_UN` | `TestWriteTxQueuesBehindOtherProcess` 红：`开写事务：database is locked (5) (SQLITE_BUSY)` |
| B 不拦慢事务 | 拦截条件前加 `false &&` | `TestWatchdogFailsSlowTxBeforeCommit` 红：`应报 ErrSlowTx，得到 context canceled` |
| C 缺必填不拦 | `len(missing) > 0` 前加 `false &&` | config 包两条红：缺 SIGNING_KEY 没拒绝、缺项没报全 |

整组（Python 2163 条 + Go + Docker）：见下方「最终整组」。

## 最终整组

`bash scripts/remote-check.sh`（日志 20261008-120636-60269a7，测试机 kvm17243）：

```
== ruff
All checks passed!
439 files already formatted
== pytest
2163 条测试分成 4 片
分片 1：541 passed in 74.22s
分片 2：541 passed in 72.76s
分片 3：541 passed in 67.23s
分片 4：540 passed in 64.92s
== 迁移
No changes detected
== Go（新栈）
No vulnerabilities found.
Your code is affected by 0 vulnerabilities.
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/clock	(cached)
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/config	(cached)
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/db	(cached)
== 生产配置
System check identified no issues (0 silenced).
== 错误页和模板一致
== Docker 镜像
构建成功：6470192e8888
== 全部通过
```

（db 包显示 cached：变异恢复后文件和跑绿的那一轮字节一致，Go 的测试缓存按内容哈希，
可信。）

## 设计偏差

- 12 号文档 4 节选型表写 goose 用 `WithEmbedFS`——v3.28 已无此 API，改用 Provider（`NewProvider` + `fs.Sub`），语义相同
- 新增环境变量名 `SJTUOW_ENV`（dev/prod，默认 dev）：5.16 没定看门狗模式的开关变量名，实现需要；等 `.env.example` 那一轮一起进文档
- 其余无偏差；迁移文件、连接参数、flock 方案、看门狗行为全部按 5.6

## 未完成 / 顺带发现 / 需要确认

- **顺带发现**：CI 原有 Python 任务的 `actions/checkout@v4`、`setup-uv@v5` 没按 SHA 固定（14-7 的要求），本轮没动它（不扩大范围），建议下轮把整个 workflow 的 Action 都钉 SHA
- 看门狗生产阈值 200ms、开发 1s 仍是拍脑袋数（13 号 C 节说了等真实数据再定），但已做成可注入
- `go.sum` 里 indirect 的 `2 vulnerabilities in packages you import / 6 in modules you require` 是 govulncheck 报的「没被调用到的漏洞」，其中含 goose 的传递依赖；我们的代码路径不受影响，记录在案

## 改动文件

- 新增：`server/`（go.mod、go.sum、cmd/sjtuow、db/、internal/platform/{config,clock,db}、tools/txhammer）
- `scripts/check.sh`（Go 段）、`scripts/remote-check.sh`（任务脚本导出工具链）
- `.github/workflows/ci.yml`（go 任务）
- `AGENTS.md`（新栈真命令 + 编译测试优先测试机的规矩）
- `handoff/rounds/222-m1-go-foundation/`（request、本报告、install-toolchain.sh、drill-two-containers.sh、RESULTS.txt）
- `handoff/STATUS.md`
