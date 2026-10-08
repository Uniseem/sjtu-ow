# 223 实现报告

## 结论

完成。接口注册表落地：门、严格绑定、统一错误形状、跨站防护，守卫测试（矩阵、乱填、跨站写、panic 规则）全绿；4 处变异全部被抓到。

## 逐条结果

### 1. `internal/app`（Viewer / Ctx）

- `Viewer`：编号、停用、邮箱已验证、超管、能力集、单人功能限制；`CanUse` 按规则 11 的子集（未登录/停用拒 → 单人规则拒 → 默认允许，超管绕过）；`HasCap` 超管全有。停用一票否决（连超管身份也救不了，有测试）。
- `Ctx`：Context、Viewer、Clock（222 的可注入时钟）、RequestID（本轮随机生成；serve 起来后改由可信代理链传递）。待发信批次、任务入队后续里程碑挂上来。
- 完整的角色 → 能力对照、派生角色是 M3 的事（5.8），本轮只有判定骨架。

### 2. `internal/platform/api`（注册表）

- `Get/Post/Patch/Delete` 泛型注册，处理函数签名 `func(*app.Ctx, In) (Out, error)`；
- 门五种：`Public`、`Member`、`Verified`、`Feature(f)`、`Cap(c...)`、`Superuser`（`Token` 等 djsign 轮，本轮不做）。**没声明门注册时 panic**；
- 401/403 的口径：没登录（含停用）一律 401；已登录但不够格一律 403 固定文案；规则 148 的「没权限看也 404」由服务层自己返回 `NotFound`；
- 声明选项：`Budget(n)`、`Limit(kind, n, window)`、`NoLimit("理由")`（写接口必须声明其一，否则 panic——数字的集中对照表在限流执行轮做）、`Nav(大类, 标签)`；
- 路由：标准库 `http.ServeMux`（方法 + 通配段），整个 mux 外套 `http.NewCrossOriginProtection().Handler(...)`——跨站写 403，无 Origin 无 Sec-Fetch-Site 的非浏览器请求放行（微信内置浏览器的情形）。守卫测试里 `cross-site` 403 / `same-origin` 200 实测过。

### 3. 绑定（`bind.go`）

- `path:"id"` 标签 → 路径参数，一律过 `ParseID`（`[0-9]{1,18}`，不合格 404；20 位数字、`-1`、`²`、`abc` 全部 404 不是 500，166/167 那类问题在新栈从结构上不存在）；
- `json:"..."` 标签 → 请求体，**严格解析**：Content-Type 必须是 application/json、未知字段 400、`http.MaxBytesReader` 限 1 MB；
- 路径参数**最后**写、覆盖 JSON 里的同名字段（有人在请求体里塞 `"id": 999` 改不了路径指向的对象，有测试）；
- 注册时校验 In 类型（panic）：path 字段必须是 `api.ID` 且参数名在 pattern 里、GET 的 In 不许有 json 字段。

### 4. 错误形状（`errors.go`）

`{"error": {"code", "message"}, "fields": {...}}`；400 invalid / 401 unauthorized / 403 forbidden（固定文案）/ 404 not_found / 422 invalid_fields（带 fields，`__all__` 放整表单的）/ 429 留给限流轮。服务层冒出的普通 error 一律 500、记 slog、返回固定文案——测试确认 `postgres://secret` 这种内部串不会漏给客户端。

## 验收输出

全部在测试机上跑。Go 全套（日志 20261008-141735-88acb7b）：

```
ok  github.com/Uniseem/sjtu-ow/server/internal/app                          0.006s
ok  github.com/Uniseem/sjtu-ow/server/internal/platform/api                 0.007s
ok  github.com/Uniseem/sjtu-ow/server/internal/platform/clock               (cached)
ok  github.com/Uniseem/sjtu-ow/server/internal/platform/config              (cached)
ok  github.com/Uniseem/sjtu-ow/server/internal/platform/db                  (cached)
GO-ALL-GREEN
```

变异验证（单点改动、测试机上跑、改完恢复）：

| 变异 | 改动 | 结果 |
|---|---|---|
| A 不查门 | `gate.check` 的结果忽略 | 守门矩阵 19 处红（访客 200、被限功能 200……） |
| B 不严格解析 | 去掉 `DisallowUnknownFields` | 乱填测试红：未知字段 200 应 400 |
| C ID 校验放水 | `!ok` 前加 `false &&` | 乱填测试红：`abc`/20 位/`-1`/`²` 全 200 应 404 |
| D 不套跨站防护 | `Handler` 直接返回 mux | 跨站测试红：`Sec-Fetch-Site: cross-site` 200 应 403 |

最终整组：见下方「最终整组」。

## 最终整组

第一次整组（20261008-142117-ce7dcdb）卡在 govulncheck：**标准库 `encoding/asn1` 的 GO-2026-5972**（1.26.6 修复），我们在 1.26.5 上。处置：测试机 Go 升到 **1.26.8**（官方 tarball、sha256 核对，安装脚本里也改了版本）、本机 brew 升到 1.27.1、`go.mod` 的 go 指令跟到 1.26.8（记录验证过的最低工具链）。升级后重跑整组（20261008-142612-d894413）：

```
== pytest
2163 条测试分成 4 片
分片 1：541 passed in 75.45s
分片 2：541 passed in 75.95s
分片 3：541 passed in 68.11s
分片 4：540 passed in 64.97s
== 迁移
No changes detected
== Go（新栈）
No vulnerabilities found.
ok  github.com/Uniseem/sjtu-ow/server/internal/app            0.003s
ok  github.com/Uniseem/sjtu-ow/server/internal/platform/api   0.013s
ok  github.com/Uniseem/sjtu-ow/server/internal/platform/clock 0.004s
ok  github.com/Uniseem/sjtu-ow/server/internal/platform/config 0.003s
ok  github.com/Uniseem/sjtu-ow/server/internal/platform/db    7.729s
== 生产配置
System check identified no issues (0 silenced).
== Docker 镜像
构建成功：9364e2f89970
== 全部通过
```

## 设计偏差

- 12 号文档 5.3 写 `api.Budget(12)` 等选项的形式——照做；`Token` 门推迟到 djsign 轮（本轮 request 里写明）；
- 5.4 的「401 前端跳登录」在接口层只负责返回状态码，跳转是前端的事；
- 其余按文档。GET 的 In 带 json 字段直接 panic 比文档「只说不做」更严，是注册时的结构性拦截。

## 未完成 / 顺带发现 / 需要确认

- 限流只有声明、没有执行（`rate_counters` 表、原子计数、429 + Retry-After）——**下一轮**；
- 幂等键、TS 生成（apigen）、`serve` 子命令、会话中间件（`ViewerResolver` 的真实现）都在 M1 后续轮次；
- 顺带发现：`httptest.NewRequest` 不带 Sec-Fetch 头时 CrossOriginProtection 默认放行（非浏览器口径），和 13 号文档对微信内置浏览器的判断一致。

## 改动文件

- 新增：`server/internal/app/`（ctx + 测试）、`server/internal/platform/api/`（registry、gates、bind、errors、id + 测试）
- `handoff/rounds/223-m1-api-registry/`（request、本报告、review）
- `handoff/STATUS.md`
