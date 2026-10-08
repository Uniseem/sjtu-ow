# 232 M2 第二轮：SSR 服务

## 背景

231 把样式和工作区立起来了。这一轮做 12 号文档 6.2 的前台 SSR：每个 GET/HEAD 新建 Vue 应用，画出 HTML。页面内容、页头页脚、样张页后面再做。

## 本轮范围

### 做

1. `web/apps/site`：Vue 3、Vue Router、`@unhead/vue`。`server.ts` 300 行以内。
2. 只接 GET/HEAD，其它 405。少了结尾斜杠、加上之后能匹配的，301。
3. 并行跑页面的 `load()` 和 `/api/session`（转交 Cookie、`X-Real-IP`、`X-Request-ID`，超时 5 秒）。`load()` 401 就 302 到登录页；403/404 画出错误页并用那个状态码；接口连不上是 503。
4. HTML：`theme.js` 在 head 最前；charset 和 viewport 只由 unhead 写；状态放进 `id="ow-state"` 的 JSON 脚本，`<`、U+2028、U+2029 转义；没有 `style` 属性，没有可执行的内联脚本。
5. 登录用户 `Cache-Control: private, no-store`，访客 `no-cache`，都带 `Vary: Cookie`。
6. 脚本没加载上的横幅（6.10）：默认藏着，纯 CSS 8 秒后出现，除非 `html` 有 `js-ready`。
7. 路由先只放 `/` 和 `/teams/`，用来把上面几条跑通。首页标题是 SJTU-OW。

### 不做

- 页头、页脚、主题菜单、加载条、右键菜单、样张页。
- 按现行站地址表把路由补全。
- 体积预算（等首页壳真的接上样式和布局）。
- 正式站。

## 验收标准

测试机上 `pnpm test` 通过（含这一轮的 SSR 测试）。变异：放行 POST、不转义 `<`、登录用户也 `no-cache`，三处都要先红再改回。依赖是 Vue、Vue Router、unhead、Vite，许可证 MIT。
