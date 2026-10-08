# 224 实现报告

## 结论

完成。限流按时间片原子计数，超限回 429 和 Retry-After；幂等键认领先行，24 小时内重放原样回回执。4 处变异全部变红后恢复。

## 逐条结果

### 1. 迁移

`rate_counters(key, bucket, count)` 主键 `(key, bucket)`；`idempotency_keys(user_id, key, …)` 主键 `(user_id, key)`，`status=0` 表示认领了还在处理。过期清理留给定时器轮。

### 2. 限流

- `INSERT … ON CONFLICT DO UPDATE SET count = count + 1 RETURNING count`，超了 `N` 就 429，`Retry-After` 是到下一个时间片的秒数。
- 时间片（UTC，固定窗口）：≤1 分钟按分钟，不满 24 小时按小时，≥24 小时按天。请求里写的「≤1 小时按分钟」会把「每小时 5 次」算成每分钟 5 次，改了，并写进 12 号文档 5.9。
- 访客 IP 只信 `TRUSTED_PROXIES` 带来的 `X-Real-IP`，直连用 `RemoteAddr`；IPv6 折叠成 /64。没登录的人走 `per_user` 时按 IP 计。
- `limits.go` 钉了附录 C / 规则 214、217–220、222 里这轮先用的数字：入队 20/天、建队 3/天、评论 3/分 + 100/天、点赞 60/分、搜索 30/分/IP、导出 5/小时。规则 6（allauth）、215（状态片段）、216（日历 30/分/IP）、221（头像 5/天）、223（注销试密码 5/小时）写在表头注释里，等对应接口的轮次再引用。一个接口可以挂多条，先撞上的那条决定 429。

### 3. 幂等键

`Idempotency-Key`：同一个人同一个键先插入 `status=0`，做完再写回执。24 小时内重放原样回状态码和正文；处理中再来 409；键用在别的地址上 400；过期可以重新用；处理出错释放认领。只对登录用户的写请求生效。

### 4. 注册表接线

`api.Limit` 收 `ratelimit.Decl`（可以多条）。`Handler` 用 `WithLimiter` / `WithIdempotency` / `WithTrustedProxies` 注入。没接执行器时不计数（纯单元测试）。

## 验收输出

全部在测试机上跑。日志 `20261008-173746-bfe5ce2`。第一次（`20261008-173625-98f3976`）卡在 gofmt（`limits.go` 注释缩进），格式化后重跑。

Go 测试（变异前的基线，未命中缓存）：

```
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/api	0.027s
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/ratelimit	0.002s
```

gofmt、`go vet`、staticcheck 无输出（通过）。变异（`mutate.py`，基线先绿）：

```
四处变异全部变红后恢复
MUTATIONS-OK
```

| 变异 | 改动 | 结果 |
|---|---|---|
| A 不执行限流 | `cfg.limiter != nil` 加 `&& false` | `TestRateLimit429WithRetryAfter`：第 3 次 200，应 429 |
| B 不重放 | `Replay` 改成永远匹配不上的 outcome | 重放跑了第二次，`{"call":2}` |
| C IPv6 不折叠 | `copy(masked, v6[:8])` 改成拷全地址 | 同 /64 的第二个地址 200，应 429 |
| D 不查可信代理 | `inAny` 前加 `true \|\|` | 换一个来源仍被伪造的 `X-Real-IP` 算成 429 |

同一趟接着跑的检查（`run` 里调 `check.sh`，没设 `CHECK_SHARDS` / `CHECK_DOCKER`，所以 pytest 没分片、镜像没构建）：

```
2163 passed in 263.45s (0:04:23)
== 迁移
No changes detected
== Go（新栈）
No vulnerabilities found.
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/api	(cached)
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/ratelimit	(cached)
== 生产配置
System check identified no issues (0 silenced).
== 全部通过
```

镜像没构建：本轮没改 Dockerfile 和现行站代码。223 那次整组的镜像是绿的。

## 设计偏差

5.9 原来只说「整分钟（或整小时、整天）一个桶」，没写窗口和片怎么对应。请求里写的「≤1 小时按分钟」和「每小时 5 次」矛盾，按后者改了，12 号文档 5.9 和修订记录补了一句。

## 未完成 / 顺带发现

- 过期桶和过期幂等键的清理等定时器轮。
- allauth、日历、头像、注销试密码的数字还没进 `limits.go` 的变量，只写在注释里。
- 本轮没把 `serve` 真正挂上。

## 改动文件

- `server/db/migrations/00002_rate_counters.sql`、`00003_idempotency_keys.sql`
- `server/internal/platform/ratelimit/`、`idempotency/`
- `server/internal/platform/api/registry.go`、`middleware_test.go`、`registry_test.go`
- `docs/rewrite-research/12-architecture.md`（5.9 时间片）
- `handoff/rounds/224-m1-ratelimit-idempotency/`
