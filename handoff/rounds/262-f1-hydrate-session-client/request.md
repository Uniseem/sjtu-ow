# 262 F1 底座（一）：激活、整份会话、接口客户端、加载器的错误分流

## 背景

用户 2026-10-10：「之后开始写前端吧」。按 `docs/frontend-migration.md` 第 11 节，先做 F1 底座。这一轮做底座里最底下的四件，后面每一页都要站在它们上面：

- C1：客户端用 `createApp` 清空重画，不是激活（A1）
- S14：SSR 只留了会话的 `nickname`、`admin`，后台导航因此只剩「首页」（A6）
- C5、C6：生成的接口函数绕过 `createClient`、没有查询参数、类型和 JSON 对不上（A3、A4、B4 的前半）
- C12、S5、S6：加载器把错误吞掉；要登录的页访客能打开；客户端换页出错原地不动（A2）

第 10 节的拍板（回滚、后台形态、新依赖）还没回复。这一轮不依赖它们：不加依赖（所以 `vue-tsc` 不在这一轮），不碰正式站，不重写页面。

## 本轮范围

做：

1. Go：注册表编码答复前把没赋值的切片、映射换成空的（`[]`、`{}`），指针照旧 `null`
2. Go：apigen 重写 TS 输出——每个函数第一个参数是 `Requester`，经过 `createClient`；查询参数生成 `XxxQuery`；匿名嵌入摊平；`[]*T` 写成 `(T | null)[]`；只在有请求体时生成 `XxxIn`；生成物里没有 `fetch`
3. `@sjtu-ow/api` 的 `createClient`：基地址、查询串（空值不发）、超时、连不上和超时变成 `ApiError(0)`、`unauthorized: "throw"`
4. 站点：`main.ts` 两边都用 `createSSRApp`；`useApi()`；加载器的上下文有 `api`、`query`；路由元信息 `auth: "member"`，SSR 先把访客送去登录；加载器抛的 `ApiError` 按状态码分流（401 登录、403/404/429 错误页、其余 503）；客户端换页：401 已由客户端跳登录、连不上弹提示留在原页、其余整页去拿服务器画的错误页、分块丢了整页重载一次（一分钟内同一地址只一次）；换页时页面数据整份替换不合并
5. SSR 把 `/api/session` 整份放进页面状态（`superuser`、`caps` 都在）
6. 253 的后台页面改成新签名（`getApiX(api, …)`），不改别的——它们整体在 F8、F9 重写

不做：

- 不重写任何页面（260 的页面继续用旧的 `ctx.fetch`、`ctx.apiBase`，留到各自那一组重写）
- 不加 `vue-tsc`、源码守卫（守卫要先有「待重写」的白名单，下一轮和图片、错误页一起做）
- 错误页的正文照旧站（A12）不在这一轮
- 不部署

## 任务

| 编号 | 任务 | 验证 |
|---|---|---|
| T1 | 注册表 `nonNil` | `go test`：一条接口返回 nil 切片、映射、嵌套 nil 切片、nil 指针，答复是 `[]`、`{}`、`null`；拆掉 `nonNil` 必须红 |
| T2 | apigen | `go test`：签名带 `Requester`、调用经 `r(...)`、无 `fetch(`；嵌入摊平；`(T \| null)[]`；查询参数类型和签名。生成物重新生成后提交，`check.sh` 的 `git diff --exit-code` 过 |
| T3 | `createClient` | Vitest：基地址和查询串、空值不发、路径参数编码、连不上 → `ApiError(0, "network")`、`unauthorized: "throw"` 不跳转；原有六条照过 |
| T4 | 激活 | `browser-check.mjs` 加一项：首页启动过程中，装着 `#main` 的节点不许被移除（`createApp` 会清空容器、激活不一致会换节点）。变异：`main.ts` 换回 `createApp`，browser-check 必须红 |
| T5 | 登录门、错误分流、整份会话、加载器上下文 | Vitest（SSR）：访客打 `/me/teams/?x=1` → 302 带 `next`，成员 200，公开页照旧；加载器抛 404/403/429 → 同状态码的错误页，抛 `ApiError(0)` → 503；页面状态里的 `viewer.user` 和接口给的一模一样；加载器拿到的 `params`、`query`、`api`（经基地址发出去）。变异：去掉 `auth` 判断、去掉 429 分流，各自对应的测试必须红 |
| T6 | 后台页面改签名 | 构建通过；`journey.mjs pages` 不在这一轮（后台页面整体要重写） |

## 验收标准

- 测试机整组 `bash scripts/remote-check.sh` 退出码 0
- `browser-check.mjs` 输出 `BROWSER-CHECK-OK`
- 变异（T1、T4、T5 列的）全部变红后恢复
