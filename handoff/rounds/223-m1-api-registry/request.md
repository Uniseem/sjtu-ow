# 223 M1 第二轮：接口注册表、门和错误形状

## 背景

M1 第一轮（222）立起了 `server/`：配置、数据库、迁移。本轮做 12 号文档 5.3/5.4 的**接口注册表**——新栈所有 HTTP 接口都从它走：声明门和限流、按标签绑定路径参数和 JSON、统一错误形状。它的价值在「由注册表生成守卫测试」：守门矩阵、乱填、跨站写，这些是 210/217 复核里暴露过整类问题的地方（03-1 越权读、166/167 乱填 500、16-2 没测 CSP）。

## 本轮范围

### 做

1. **`internal/app`**：`Viewer`（这次请求是谁的最小口径：编号、停用、邮箱已验证、超管、后台能力集、单人功能限制）和 `Ctx`（服务函数第一个参数，12 号文档 5.2：用户、时钟、请求编号；待发信批次后续轮次加）。`can_use` 的完整判定顺序（角色级限制，5.8）M3 随账号域做，本轮 Viewer 上的判定是它的子集。
2. **`internal/platform/api` 注册表**：
   - `api.Get/Post/Patch/Delete` 泛型注册，处理函数签名 `func(*app.Ctx, In) (Out, error)`（In/Out 类型将来自动生成 TS 的元数据，TS 生成是下一步）；
   - 门的种类：`Public`、`Member`（登录且启用）、`Verified`、`Feature(f)`、`Cap(c...)`、`Superuser`。**`Token`（签名地址）这轮不做**——它需要 djsign（后续轮次），做了也是个空壳；没声明门的接口注册时直接 panic；
   - 路径参数 `{id}` 一律按 `[0-9]{1,18}` 解析（`api.ID` 类型），不合格 404；
   - 绑定：`path:"id"` 标签取路径参数、`json:"..."` 标签取请求体；**JSON 严格解析**（未知字段 400）、请求体 1 MB 上限、带 JSON 字段的写请求必须 `Content-Type: application/json`；注册时校验：path 标签的参数必须在 pattern 里、GET 的 In 不许有 json 字段；
   - 路由用标准库 `http.ServeMux`（方法 + 路径参数），整个 handler 外面包 `http.CrossOriginProtection`（跨站写 403；无 Origin 无 Sec-Fetch-Site 的非浏览器请求放行——微信内置浏览器的情形，13 号风险表）。
3. **错误形状**（5.4）：`{"error": {"code", "message"}, "fields": {...}}`；状态码 400（请求坏了）/ 401（没登录，含停用）/ 403（没权限，文案固定不说原因）/ 404（不存在）/ 422（业务校验，带 fields）/ 429（限流，本轮只有声明没有执行）。
4. **声明类选项**：`api.Budget(n)`（查询预算，接 222 的 Counter）、`api.Limit(kind, n, window)` / `api.NoLimit("理由")`（写接口必须声明其一，注册时不声明 panic——数字集中在限流轮的 limits 表）、`api.Nav(大类, 标签)`（后台位置）。
5. **守卫测试**（注册表的验收核心）：
   - **守门矩阵**：每种门 × 访客 / 停用 / 未验证成员 / 已验证成员 / 被限功能 / 有能力 / 超管，断言 401/403/放行和声明一致；
   - **乱填**：路径参数灌 `abc`、20 位数字、`-1`、`²` → 一律 404 不是 500；JSON 字段灌错类型、未知字段、空体、超 1 MB、错的 Content-Type → 400；
   - **跨站写**：`Sec-Fetch-Site: cross-site` 的 POST → 403；`same-origin` → 放行；
   - **注册时 panic**：没门、写接口没限流、path 标签不在 pattern、GET 带 json 字段。

### 不做

- `Token` 门（等 djsign 轮）、限流的**执行**（`rate_counters` 表、计数、429——下一轮）、幂等键、TS 生成（apigen 第二步）、`serve` 子命令和真实路由挂载、`{id}` 之外的查询参数绑定（`?page=` 这类，第一个需要它的页面接口出现时加）；
- Caddy、镜像、部署——M9。

## 任务（每条带验证）

| # | 任务 | 验证 | 期望 |
|---|---|---|---|
| 1 | Viewer/Ctx | `go test ./internal/app/` | CanUse/HasCap 判定对，停用一票否决 |
| 2 | 注册表 + 门 | `go test ./internal/platform/api/` | 守门矩阵全过；panic 规则全过 |
| 3 | 绑定 + 严格解析 | 同上 | 乱填全 404/400，无一 500 |
| 4 | 跨站写防护 | 同上 | cross-site 403、same-origin 放行 |
| 5 | 错误形状 | 同上 | JSON 形状和状态码逐条对 |
| 6 | 变异 | 拆掉门检查 / 严格解析 / ID 校验 / 跨站防护 | 各自变红 |

## 验收标准

```sh
cd server && gofmt -l .（空）&& go vet ./... && staticcheck ./... && govulncheck ./... && go test ./...
```

全绿；`bash scripts/remote-check.sh` 整组（Python 照旧 + Go 段）全绿；4 处变异全部变红后恢复。
