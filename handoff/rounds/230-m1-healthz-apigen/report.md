# 230 实现报告

## 结论

完成。`/healthz`、apigen、`sjtuow serve` 和 `sjtuow worker` 都接上了。4 处变异全部变红后恢复。

## 逐条结果

### 1. /healthz

写一行到 `health_probe` 再回滚。数据卷剩余等于或低于 20% 就不健康。worker 心跳超过 120 秒、或者没有心跳，不健康。积压只数 `ready` 且到期时间早于 10 分钟前的任务。对外的 JSON 只有总状态和各项真假；详情只在调用方标明是超管时带上。状态码两边一样。

用户表还没有。真会话只能解出用户编号，解不出超管。测试用注入的超管看详情。

### 2. apigen

`sjtuow apigen` 把注册表写成 `web/packages/api/src/gen/index.ts` 和 `nav.ts`：类型、调用函数、后台导航。现在还没有领域接口，生成物是调用壳和空导航。CI 和测试机整组生成后再 `git diff --exit-code`。守门矩阵、乱填、限流和查询预算继续用 Go 测试直接读注册表。

### 3. serve 和 worker

`serve` 先迁移，挂上注册表（限流、幂等、会话 Cookie）和 `GET /healthz`，默认听 `:8080`。`worker` 占锁，注册 `mail.letter`，每秒一轮。SMTP 从环境变量读，没配就按「尚未配置」走邮件车道的重试。

## 验收输出

全部在测试机上跑。变异和整组是同一趟。日志 `20261008-184217-2177b0d`，退出码 0。apigen 的 `git diff` 在 Go 那一步里面，没有单独的标题；脚本能印出「全部通过」，说明生成物和仓库一致。

```
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/health	(cached)
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/apigen	0.003s
四处变异全部变红后恢复
MUTATIONS-OK
== Go（新栈）
No vulnerabilities found.
Your code is affected by 0 vulnerabilities.
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/health	(cached)
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/apigen	(cached)
ok  	github.com/Uniseem/sjtu-ow/server/internal/serve	0.009s
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/api	0.067s
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/db	7.744s
== 全部通过
```

| 变异 | 改动 | 结果 |
|---|---|---|
| A 剩余 20% 也算健康 | `free*5 <= total` 改成 `<` | 刚好 20% 被当成健康 |
| B 积压不看到期时间 | 10 分钟改成 1 分钟 | 两分钟前到期的也算积压 |
| C 对外也给详情 | `if !detail` 前加 `false &&` | 对外的结果里带着 Detail |
| D 生成器不用 json 标签 | `Get("json")` 改成 `Get("xml")` | 请求体里没有 `message`，响应字段变成 `ID` |

## 设计偏差

超管详情要等用户表（M3）才能从会话里看出来。生成的守门矩阵、乱填、限流对照、查询预算没有另写一份文件：223 起的 Go 测试已经直接读注册表，加接口就会跑到。

## 未完成 / 顺带发现

- 领域接口还没注册，生成物是空壳。
- 34 种信、确认页、全站设置里的 SMTP 表都不是这轮的事。

## 改动文件

- `server/internal/platform/health/`
- `server/internal/platform/apigen/`
- `server/internal/serve/`
- `server/cmd/sjtuow/main.go`
- `server/internal/platform/api/registry.go`
- `server/internal/platform/jobs/worker.go`
- `server/db/migrations/00007_health_probe.sql`
- `web/packages/api/src/gen/`
- `.github/workflows/ci.yml`
- `scripts/check.sh`
- `handoff/rounds/230-m1-healthz-apigen/`
- `handoff/STATUS.md`
