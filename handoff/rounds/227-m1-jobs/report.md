# 227 实现报告

## 结论

完成。任务表、三条车道、只有一个 worker、邮件三次重试、上海时区的定时项都在。4 处变异全部变红后恢复。

## 逐条结果

### 1. 队列

`jobs` 表按 5.10 的列。`Enqueue` 插在调用方的写事务里。`EnqueueOnce` 只看还在 `ready` 的同 `dedupe_key`：到期时间相同不再排；`earlierCounts` 时，已有一条不晚于这次的也不再排。认领按优先级、到期时间、编号，标成 `running` 并把 `attempts` 加一。邮件失败按 1 分钟、5 分钟、30 分钟再排，第四次记失败；别的车道失败一次就记失败。启动时 `running` 放回 `ready`。

### 2. 一把锁

`worker_lock` 只有一行。心跳 120 秒内第二个 `TryLock` 得到 `ErrBusy`；心跳断了可以接手。心跳同时写 `worker_status`。

### 3. 定时器

`Asia/Shanghai`，固定东八区。每 30 秒两项（定时上线、巡查）、每天 03:00 备份、04:00 清理、04:40 旧前端文件、每周日 04:30 `PRAGMA optimize` 和 `wal_checkpoint(TRUNCATE)`。错过了只补最近一次。04:00 删掉做完超过 30 天的任务、过期会话、超过 24 小时的幂等回执、48 小时前的限流桶。备份、上线、巡查、删旧文件这四项还没有处理函数，到点只记下跑过。

## 验收输出

全部在测试机上跑。

整组。日志 `20261008-180215-77fd808`，退出码 0。这一趟前面先跑了 226 的变异（`MUTATIONS-OK`），任务队列的测试在同一趟的 `go test` 里。

```
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/jobs	0.034s
GO-OK
2163 条测试分成 4 片
分片 1：541 passed in 73.38s (0:01:13)
分片 2：541 passed in 72.10s (0:01:12)
分片 3：541 passed in 67.24s (0:01:07)
分片 4：540 passed in 65.65s (0:01:05)
== 迁移
No changes detected
== Go（新栈）
No vulnerabilities found.
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/jobs	(cached)
== 生产配置
System check identified no issues (0 silenced).
== Docker 镜像
构建成功：a2a0c4273791
== 全部通过
```

变异（`mutate.py`，基线先绿）。日志 `20261008-180433-0cca2af`。

```
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/jobs	(cached)
四处变异全部变红后恢复
```

| 变异 | 改动 | 结果 |
|---|---|---|
| A 启动不复位 running | `ready` 改回 `running` | 启动应把 running 放回 ready，得到 running |
| B 邮件失败不重试 | 车道判断改成永远碰不上的 `never` | 第一次失败直接 `failed`，没有 1 分钟后的重试 |
| C 更早的一条不算数 | 去掉 `earlierCounts` | 已有更早的一条仍 `inserted=true` |
| D 第二个 worker 也能占锁 | `n == 0` 前加 `false &&` | 第二个应起不来：`<nil>` |

## 设计偏差

没有。`sjtuow worker` 这轮按请求没挂上命令，只有 `Lock` 和 `Tick`。

## 未完成 / 顺带发现

- 备份、定时上线、巡查、删旧前端文件的处理函数等对应的表和目录。
- 入队申请、空草稿的清理等那些表。
- `serve` / `worker` 命令还是「还没实现」。

## 改动文件

- `server/internal/platform/jobs/`
- `server/db/migrations/00005_jobs.sql`
- `handoff/rounds/227-m1-jobs/`
- `handoff/STATUS.md`
