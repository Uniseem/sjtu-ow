# 230 M1 第八轮：healthz、apigen、serve 和 worker

## 背景

229 之后 M1 还差 12 号文档 5.15 的 `/healthz`、5.3 的 apigen，以及把 `sjtuow serve` / `sjtuow worker` 从「还没实现」接上。

## 本轮范围

### 做

1. **`/healthz`**：写一行再回滚、数据卷剩余要大于 20%、worker 心跳 120 秒内、积压是 `ready` 且到期时间早于 10 分钟前的任务。对外只有总状态和各项真假，详情只给超管。没接上用户表之前，真会话解不出超管，测试用注入的超管看详情。
2. **apigen**：从注册表生成 `web/packages/api/src/gen/` 的类型、调用函数和 `nav.ts`。CI 和测试机整组重新生成后 `git diff --exit-code`。守门矩阵、乱填、限流和查询预算继续用已经在跑的 Go 测试直接读注册表，不另生成一份。
3. **`serve`**：迁移、挂上注册表（限流、幂等、会话 Cookie）、`/healthz`，默认听 `:8080`。
4. **`worker`**：占锁，注册 `mail.letter`，每秒一轮。SMTP 从环境变量读，没配就按「尚未配置」走邮件重试。

### 不做

- 领域接口（注册表还是空的，生成物也是空的调用壳）。
- 用户表和「这个会话是不是超管」（M3）。
- 确认页、34 种信。
- 正式站。

## 验收标准

测试机上 gofmt、vet、staticcheck、govulncheck、go test、apigen 无差异。变异变红后恢复。不加依赖。
