# 224 M1 第三轮：限流的执行 + 幂等键

## 背景

223 立了注册表，限流只有**声明**（`api.Limit` / `api.NoLimit`，写接口必须声明其一）。本轮做执行（12 号文档 5.9）和幂等键（5.5 的 Idempotency-Key 协议），写请求的两道通用防线就齐了。

## 本轮范围

### 做

1. **迁移**：`rate_counters(key, bucket, count)`（5.9 的三列表）和 `idempotency_keys(user_id, key, method, path, status, response, created_at)`（13 号 D 节：幂等回执放表里、worker 定期清——清理由 worker 轮做，本轮只建表）。
2. **`internal/platform/ratelimit`**：
   - 原子计数：`INSERT … ON CONFLICT DO UPDATE SET count = count + 1 RETURNING count`，整分钟 / 整小时 / 整天一个时间片桶（窗口 ≤1 小时按分钟、<24 小时按小时、≥24 小时按天，UTC）；
   - 访客 IP：只认**可信代理**（`config.TrustedProxies`）带来的 `X-Real-IP`，直连或不可信的一律用 `RemoteAddr`；IPv6 折叠成 /64（5.9）；
   - `limits.go` 一张表：把设计附录 C 里新栈还适用的数字先钉进去（申请入队 20/天/人、创建战队 3/天/人、评论 3/分+100/天/人、点赞 60/分/人、搜索 30/分/IP、导出 5/小时/人），每条注明出处；allauth 那组和日历的数字等对应接口的轮次再进表；
   - 一个接口可以同时挂多个限流（评论就是 3/分和 100/天两个）。
3. **`internal/platform/idempotency`**：`Idempotency-Key` 头——同一个人同一个键 24 小时内重放直接返回当时的回执；**认领先行**（先插一行 status=0，完成再写回执）防双击：处理中再来的同键请求 409；键用在不同地址上 400；超 24 小时的键可以重新用；处理出错的请求释放认领、让重试可行。只对登录用户生效（访客的写请求不带会话，重放没意义）。
4. **注册表接线**：`api.Limit` 改收 `ratelimit.Decl`（数字只能来自 limits.go 的表，不许内联——结构性保证 5.9 的「集中一张表」）；`Handler` 加选项注入限流器、幂等存储、可信代理网段；超限返回 **429 + Retry-After**（到下一个时间片）；幂等重放原样回状态码和回执体。
5. **测试**：计数与阻断、跨时间片重置、可信/不可信代理、IPv6 同 /64 同键、429 的头和形状、幂等重放（处理函数只跑一次）、双击 409、错用地址 400、过期键复用、出错释放；端到端走真 SQLite。
6. **变异**：不执行限流 / 不重放 / IPv6 不折叠 / 不查可信代理——各自变红。

### 不做

- worker 的过期桶和过期幂等键清理（定时器轮）；allauth 那组限流的数字（M3 认证轮）；`Token` 门和 djsign；`serve` 真正挂载。
- 日历订阅的限流数字（设计没写明，等接口落地问一次）。

## 验收标准

`cd server && gofmt -l .（空）&& go vet ./... && staticcheck ./... && govulncheck ./... && go test ./...` 全绿；测试机整组全绿；4 处变异变红后恢复。
