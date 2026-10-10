# 262 实现报告

## 结论

完成。F1 底座的第一批（A1、A2、A3、A6，A4 的大半）做完；顺带修了 261 提交 CI 红的那条日历测试。页面本身没改。

## 逐条结果

| 编号 | 结果 |
|---|---|
| T1 注册表 `nonNil` | `server/internal/platform/api/nonnil.go`；`registry.go` 编码前调它。测试 `TestNilListsAreEncodedAsEmpty`：nil 切片 → `[]`、嵌套的 nil 切片 → `[]`、nil 映射 → `{}`、nil 指针 → `null`、`omitempty` 的 nil RawMessage 照旧省略 |
| T2 apigen | `apigen.go` 重写 TS 输出：`import type { CallExtras, Requester } from "../client.ts"`；函数签名 `(r: Requester, 路径参数: string \| number, body?, query = {}, extras = {})`，函数体 `return r<Out>(方法, 路径, { ...extras, params, body, query })`；只有带请求体时才生成 `XxxIn`，有查询参数时生成 `XxxQuery`（全可选）；匿名嵌入摊平；`[]*T` → `(T \| null)[]`；`json.RawMessage` → `unknown`、`[]byte` → `string`；递归遇到自己 → `unknown`（不再是 `any`）；答复不是结构时生成 `export type`。三条新测试 + 原有三条改写。生成物在测试机上重新生成后拷回提交（`index.ts` 2257 → 2033 行，`fetch(` 0 处）|
| T3 `createClient` | 基地址、`buildURL`（路径参数编码、查询串跳过 undefined/null/空串）、超时（`AbortSignal.timeout`，只有 SSR 设）、`fetch` 抛错 → `ApiError(0, "network" \| "timeout")`、`unauthorized: "throw"`；`Requester`、`CallExtras` 导出。三条新测试，原六条照过 |
| T4 激活 | `main.ts` 两边 `createSSRApp`；`browser-check.mjs` 新加：`Page.addScriptToEvaluateOnNewDocument` 挂 MutationObserver，首页 `js-ready` 后装着 `#main` 的节点被移除过就失败 |
| T5 登录门、分流、会话、上下文 | `router.ts`：`LoadCtx` 加 `api`、`query`（`fetch`、`apiBase` 留给 260 的页面）、`RouteMeta` 声明 `load`/`auth`/`admin`、`statusOf`、`flat`；`routes.ts`：23 条前台地址（`/me/*`、`/letters/*`、建队、申请、管理、赛事报名、报名单、重新认证、邮箱、改密码、设密码）和全部后台地址 `auth: "member"`；`entry-server.ts`：`createClient`（转交 Cookie/IP/请求编号、Go 基地址、5 秒超时）、加载器错误 401 → 登录、403/404/429 → 错误页、其余 → 503，会话整份；`entry-client.ts`：`useApi` 提供、写成功后重读会话、要登录的页换页前先送去登录、加载器 401 已跳登录、`ApiError(0)` 弹「网络连不上」留在原页、其余整页加载拿服务器画的错误页、页面数据整份替换、分块丢了同一地址一分钟内重载一次；`api.ts` 的 `useApi()`；`viewer.ts` 的类型来自生成的 `GetApiSessionOut`。四条新 SSR 测试 |
| T6 后台页面改签名 | 25 个后台页面文件的 `getApiX(` → `getApiX(api, `，加 `useApi()`；别的不动 |
| 顺带：日历测试 | `agenda.Service` 加 `clock`（默认 `clock.System{}`）和 `WithClock`，`Serve` 用它；测试环境 `WithClock(clock.Fixed(t0))` |

## 验收输出

### 整组

`bash scripts/remote-check.sh`，日志 `sjtu-ow-test:/srv/sjtu-ow-check/runs/20261010-144417-e29bbba.log`，退出码 0：

```
No vulnerabilities found.
...
ok  	github.com/Uniseem/sjtu-ow/server/internal/agenda	0.165s
...
      Tests  15 passed (15)
...
      Tests  40 passed (40)
...
首页壳 gzip：HTML 2772 + CSS 19504 + JS 70186 = 92462 字节（脚本上限 122880，合计上限 307200）
BUDGET-OK

== 全部通过 (06:45:05)
```

（`git diff --exit-code -- ../web/packages/api/src/gen` 在整组里，过了：提交的生成物和测试机上重新生成的一样。）

### 浏览器

`bash scripts/remote-check.sh run bash -c 'cd web/apps/site && node browser-check.mjs /usr/bin/chromium'`，日志 `20261010-144510-5cd9496`，退出码 0：

```
BROWSER-CHECK-OK
```

### 变异

`bash scripts/remote-check.sh run bash -c '… python3 handoff/rounds/262-f1-hydrate-session-client/mutate.py'`，日志 `20261010-144137-8de0078`，退出码 0：

```
基线全绿
抓到 T1 注册表不再把 nil 切片换成空的（go 退出码 1）
抓到 T2 apigen 的 []*T 不加括号（go 退出码 1）
抓到 T2 apigen 不摊平匿名嵌入（go 退出码 1）
抓到 T3 查询串不跳过空值（api 退出码 1）
抓到 T3 连不上不变成 ApiError(0)（api 退出码 1）
抓到 T3 unauthorized: throw 照样跳转（api 退出码 1）
抓到 T4 客户端换回 createApp（清空重画）（browser 退出码 1）
抓到 T5 要登录的页不再先送访客去登录（site 退出码 1）
抓到 T5 429 不再画成 429（site 退出码 1）
抓到 T5 会话只留昵称和 admin（site 退出码 1）
抓到 T5 加载器拿不到查询参数（site 退出码 1）
11 处全抓到，已改回，基线仍全绿
```

（变异那次的快照还没有日历测试的修复；修复在之后的整组里验过。）

### 261 的 CI

```
c1fd52f CI completed failure
--- FAIL: TestCalendarICSGenerationAndFolding (0.05s)
    agenda_test.go:275: 缺少 VEVENT 标记
```

测试机整组里这条是 `(cached)`，所以 261 在测试机上是绿的。修复见上面「顺带：日历测试」。

## 设计偏差

无。

## 未完成 / 顺带发现 / 需要确认

- **需要确认**：`docs/frontend-migration.md` 第 10 节六件仍未回复；`vue-tsc` 等第 3 件
- **顺带发现**：`content/home.go`（首页数据）、`comments/store.go`、`notify/announce.go`、`activity/api.go` 等处直接调 `time.Now()`，不走请求上下文的时钟。和这次的日历测试是同一类定时炸弹；本轮不改
- **顺带发现**：测试机的 `go test` 结果会被缓存，测试数据依赖日期的测试在测试机上可能一直「绿」、在 CI 上才红。以后改了日期相关的东西，单条跑时加 `-count=1`
- **体积**：首页壳 JS 62261 → 70186 字节（激活渲染器进来了），在上限内

## 改动文件

- `server/internal/platform/api/nonnil.go`（新）、`registry.go`、`registry_test.go`
- `server/internal/platform/apigen/apigen.go`、`apigen_test.go`
- `server/internal/agenda/agenda.go`、`agenda_test.go`
- `web/packages/api/src/client.ts`、`src/index.ts`、`src/gen/index.ts`（生成）、`client.test.ts`
- `web/apps/site/src/main.ts`、`router.ts`、`routes.ts`、`entry-server.ts`、`entry-client.ts`、`api.ts`（新）、`viewer.ts`、`handle.test.ts`、`browser-check.mjs`
- `web/apps/site/src/pages/admin/` 下 25 个文件（只改调用签名）
- `handoff/STATUS.md`、`handoff/rounds/262-f1-hydrate-session-client/`
