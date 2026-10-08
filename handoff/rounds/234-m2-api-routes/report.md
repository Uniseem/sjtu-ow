# 234 实现报告

## 结论

完成。接口调用有了 401、待发信和幂等键的封装；前台会打开成一页的地址都登记了，先只显示标题。导航点进去不再是整页 404。

## 逐条结果

1. **调用封装**。`web/packages/api/src/client.ts` 的 `createClient`（生成物 `gen/` 不动，apigen 还会覆盖它）。错误变成带 `status`、`code`、`fields`、`current` 的 `ApiError`。401 跳 `/accounts/login/?next=`，`next` 是当前路径加查询串。响应里有 `letters.batch` 就跳 `/letters/<batch>/?back=<当前地址>`；当前地址以 `/admin/` 开头则去 `/admin/letters/<batch>/`。POST、PUT、PATCH、DELETE 带 `Idempotency-Key`，调用方传入的 `key` 原样沿用，不传就 `crypto.randomUUID()`。写成功后调用 `onWrite`，给外面刷新会话留口。路径里的 `{name}` 用 `params` 替换。
2. **前台路由**。`routes.ts` 登记 02 号文档第 2、3 节里会打开成完整页的地址，外加导航已经链到的 `/news/`、`/about/`、`/terms/`、`/privacy/`。编号是 `:id(\\d{1,18})`。首页和 `/teams/` 仍是原来的 `Home.vue`、`Teams.vue`，排在这张表前面。其余走 `Page.vue`，只画标题。不登记的：只接受 POST 的动作、`/healthz`、图标、sitemap、robots、日历文件、HTMX 片段、导出下载。
3. **少斜杠**。`/news` 这种加得上斜杠的地址仍走 232 的 301，现在多出来的页也适用。

## 验收输出

测试机同一趟（日志 `20261008-200733-f0c7146`，退出码 0）：整组、浏览器检查、变异。

整组 `sh scripts/check.sh`。govulncheck：

```
No vulnerabilities found.

Your code is affected by 0 vulnerabilities.
```

根目录 Vitest 10 条（样式 4、接口封装 6），site 28 条：

```
 Test Files  2 passed (2)
      Tests  10 passed (10)
...
 Test Files  4 passed (4)
      Tests  28 passed (28)
...
== 全部通过 (12:07:58)
```

构建产物：入口 `index-BFndzdpo.js` 128.07 kB（gzip 48.90 kB），样式 `index-HAlK5m1Q.css` 95.00 kB（gzip 17.11 kB）。SSR 端 `dist/server/server.js` 43.17 kB。

浏览器检查（同一日志，无头 Chromium）：

```
site ssr on :4669 (api http://127.0.0.1:4757, built assets)

BROWSER-CHECK-OK
```

变异（同一日志，基线先绿）：

```
抓到 A 401 不再跳登录（退出码 1）
抓到 B 写请求不带幂等键（退出码 1）
抓到 C 待发信跳错地址（退出码 1）
抓到 D 资讯页被拿掉（退出码 1）
四处都抓到，已改回
MUTATIONS-OK
```

`/news/` 的服务端渲染断言在 site 的 28 条里：状态 200，去掉片段注释后正文有 `>资讯</h1>`；`/news` 301 到 `/news/`；`/teams/abc/` 是 404。

## 设计偏差

没有。封装按 12 号文档 6.4，路由按 6.3 和 02 号文档第 2、3 节。页面内容不是这一轮的。`docs/design.md` 没动。

## 未完成 / 顺带发现

- 页面还没有数据。`createClient` 还没有调用方：写成功后的 `onWrite` 要等真的写请求接上，再去刷新 `useViewer()`。
- 客户端换页时 `load()` 抛 401/403，浏览器端还没有和服务端一样的分流（233 复核提过）。这些占位页的 `load` 不请求接口，暂时抛不出 401。
- `/_styleguide/` 只是标题页，组件样张、CSP/体积进 CI、字体仍是 M2 欠的。
- 首页壳体积：入口 JS gzip 48.90 kB、CSS gzip 17.11 kB，还没和 300 KB 的预算放在一起量。
- 待发信的批次参数现在是普通路径段，没有收成 UUID。确认页还不会按批次取信。
- 新依赖：无。

## 改动文件

- `web/packages/api/src/client.ts`、`src/index.ts`、`client.test.ts`
- `web/vitest.config.js`（收进封装测试）
- `web/apps/site/src/routes.ts`、`pages/Page.vue`、`router.ts`、`routes.test.ts`、`handle.test.ts`
- `handoff/rounds/234-m2-api-routes/`、`handoff/STATUS.md`
