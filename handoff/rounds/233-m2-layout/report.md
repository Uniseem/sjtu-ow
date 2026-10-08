# 233 实现报告

## 结论

完成。前台有了页头页脚、主题菜单、路由加载条、右键菜单和提示机制；HTML 在生产模式指向 Vite 清单里的构建产物（232 遗留 1），浏览器里激活、严格 CSP 零违规也真验过了（232 遗留 2）。

## 逐条结果

1. **构建产物进页面**。`entry-client.ts` 里 `import "@sjtu-ow/styles/dist/site.css"` 把样式带进 Vite 清单（带哈希）；`server.ts` 的 `assetsFromManifest()` 从 `dist/client/.vite/manifest.json` 取入口脚本、样式表和 modulepreload，`documentHTML` 注入。没有清单（开发）仍指 `/src/entry-client.ts`。SSR 构建的入口从 `src/entry-server.ts` 换成 `server.ts`——构建产物 `dist/server/server.js` 自己就是一个能 `node` 起的完整服务（isMain 块加了 `/assets/*`、`/theme.js` 的静态服务，生产由 Caddy 做，这里给独立运行和浏览器检查用）。
2. **页头页脚**。`SiteHeader`（品牌、主导航六项、搜索表单、主题菜单、账号区、手机抽屉、加载条元素）、`SiteFooter`（说明、社区/参与/账号/关于四栏、底行）、跳到正文链接。导航当前项按路径前缀（`sections.ts`，含 `/registrations/` 算赛事、`/me/teams/` 不算战队，照旧站 main_nav.html）；`SLink` 在路由表里有这一页时走 SPA，没有就是普通链接全页加载——路由还没补全，两种都能用。页脚年份按上海时区（`time.ts` 的 `shanghaiYear`）。`CIcon` 的路径从 `components/icon.html` 原样抄，class 传进来换掉默认尺寸（照 icon.html 的 class 参数）。
3. **主题**。`public/theme.js` 暴露 `window.owTheme`（`current()`/`set()`），保留 `ow-theme` 键、跨标签 storage 同步、`startViewTransition` 交叉淡化、theme-color 粉刷；`localStorage` 键不变，割接后各人的选择不丢。`ThemeMenu` 组件两种形态（页头菜单、抽屉行），SSR 画 `hidden`、激活后移除——没有脚本时按钮本来就没用，系统说了算。
4. **加载条**。SPA 路由版：`router.beforeEach` 起条（CSS 自带 150 毫秒不出）、`afterEach` 冲满淡出（`--loadbar-from` 接着爬到的位置）、`onError` 立刻收，15 秒兜底。跨整页的接力（旧 loading.js + arrival.js 的 sessionStorage）按 12 号文档不再要。
5. **右键菜单**。`CContextMenu` 全局组件，行为照 `static/js/contextmenu.js`：Shift 右键/输入框/触屏走原生，键盘上下翻、Esc/点外关，复制有「已复制」回执。条目分组拆成纯函数 `contextmenu-entries.ts`。
6. **提示**。`toasts.ts` + `Toasts.vue`：`c-toast` 样式、`aria-live`、4.5 秒自己走。本轮没有页面调它，机制和测试先行。
7. **viewer**。`/api/session` 的 `user`（`nickname`、`admin`）进 SSR 渲染和 `ow-state`（`useViewer()` 注入）：访客见登录/注册，成员见头像（首字母，规则照 `ow.initial` 过滤器）+ 昵称 + 菜单，干部多一条管理后台。页脚账号栏同样跟着换（照 slots/footer_account.html）。Go 侧的 `/api/session` 还没有（M3），SSR 按这个形状消费，测试给桩。
8. **错误页不激活**。403/404/503 的正文不是 App 画的，现在是无脚本裸页：有样式和 theme.js，没有 `ow-state`、没有入口脚本、没有无脚本横幅。
9. **浏览器里验证**。`web/apps/site/browser-check.mjs`（照 220 e1 的 CDP 方法，Node 自带 WebSocket，零新依赖）：起桩 API + 生产 SSR 服务（`STRICT_CSP=1` 时按 12 号 6.9 加响应头），无头 Chromium 走激活→严格 CSP（内联脚本和 style 属性被拦、CSSOM 不拦）→SPA 换页和后退→主题选深色再回跟随系统→右键菜单出和 Esc 关→无脚本 8 秒横幅→404。任何一步浏览器报错、控制台错误、CSP 违规都算失败。

## 验收输出

整组 `sh scripts/check.sh`（测试机日志 `20261008-195507-50f0bde`，退出码 0）：Go 全绿，govulncheck「No vulnerabilities found. Your code is affected by 0 vulnerabilities.」；样式 4 条、site 24 条 vitest 全过：

```
 Test Files  3 passed (3)
      Tests  24 passed (24)
...
== 全部通过 (11:55:33)
```

构建产物：客户端入口 `index-BsVqk-4w.js` 125.92 kB（gzip 48.22 kB）、样式 `index-HAlK5m1Q.css` 95.00 kB（gzip 17.11 kB）；SSR 端 `dist/server/server.js` 39.99 kB（`server.ts` 作构建入口，产物自己就是一个能 `node` 起的服务）。

浏览器检查（测试机日志 `20261008-195534-c28257d`，退出码 0）：无头 Chromium 走了激活（`js-ready`）、入口指 `/assets/index-BsVqk-4w.js`、样式表在、严格 CSP（自己注入的内联脚本和 style 属性被拦、CSSOM 不拦）、客户端换页到 `/teams/` 再后退（不整页刷新、h1/标题跟着换）、主题选深色（`data-theme=dark`、`localStorage ow-theme=dark`、`aria-pressed`、菜单收起）再回跟随系统、右键菜单（链接上出「在新标签页打开」「复制本页链接」，Esc 关）、无脚本时正文可读、横幅 8 秒后出现、404 带正文。全程零控制台错误、零 CSP 违规：

```
site ssr on :4232 (api http://127.0.0.1:4749, built assets)

BROWSER-CHECK-OK
```

变异（测试机日志 `20261008-195629-38db7a6`，退出码 0）：

```
抓到 A 样式表不进页面（退出码 1）
抓到 B 导航前缀匹配改精确（退出码 1）
抓到 C 访客也画成员菜单（退出码 1）
抓到 D 加载条到了不清 is-loading（退出码 1）
抓到 E 右键菜单没有图片组（退出码 1）
抓到 F 有昵称也当访客（退出码 1）
抓到 G 提示不会自己走（退出码 1）
7 处都抓到，已改回
```

## 设计偏差

- 头像只画「底图 + 首字」：viewer 还没有头像字段，真实头像和默认头像池等 M3 的接口。
- 新依赖：无。`@sjtu-ow/styles` 以 `workspace:*` 挂进 site 的 dependencies（工作区内部链接，不是新包）。
- SSR 构建入口从 `entry-server.ts` 换成 `server.ts`（12 号 6.2 说的是 server.ts 这个文件 300 行以内，现在构建产物就是服务本身，和文档一致）。

## 未完成 / 顺带发现

- **browser-check 头一晚就抓到一个真 bug**：重写 `entry-client.ts` 时把 `app.provide("page-data", page)` 弄丢了。首屏看不出来（水合不重画，h1 还是 SSR 画的那份），客户端一换页，新组件 `inject("page-data")` 拿到 undefined，`useHead` 走了兜底标题、正文 h1 变空。vitest 走 SSR 渲染测不到这一层（服务端 provide 是全的）——这正是要在真浏览器里验激活的原因。已补上。
- Vite 7 的 `--ssrManifest` 写的是 `ssr-manifest.json`（资源映射表），不是块依赖图；块依赖图是 `build.manifest: true` 写的 `.vite/manifest.json`，而且无动态导入时入口键是 `index.html` 不是 `src/entry-client.ts`（entry-client 并进同一个块）。`assetsFromManifest` 两个键都认。已写进 AGENTS.md 的坑。
- 页脚夜带的底图（`/img/placeholders/ridge.svg`）在新栈还没有，无头浏览器里是 404——资产管线（图片占位图的搬运）是后面的轮次，browser-check 里过滤了这个噪音。
- 抽屉里的搜索表单、页头的搜索表单提交后是全页加载，`/search/` 还没有路由，会看到 404 页——路由补全的轮次一起接。
- Vue Router 在服务端对不存在的地址会往 stderr 打一行 No match found（232 就有），状态码仍是 404。
- 体积预算还没量（首页壳 gzip ≤ 300 KB）：本轮实测入口 JS gzip 48.2 kB、CSS gzip 17.1 kB（`dist/client/assets/`），等 `/_styleguide/` 和更多页面进来一起量。
- 右键菜单在无头浏览器里要 `Emulation.setEmulatedMedia` 把 pointer 仿真成 fine 才弹——组件按设计只在精确指针下接管（触屏用系统长按菜单），行为照旧。

## 改动文件

- `web/apps/site/`：`server.ts`、`src/`（入口、App、pages、components/ 九个组件、viewer/sections/time/initial/icons/theme/loadbar/contextmenu-entries/toasts/dropdowns）、`public/theme.js`、`browser-check.mjs`、`package.json`、三个测试文件
- `web/pnpm-lock.yaml`（workspace 链接 3 行）
- `.gitignore`（截图条目）
- `handoff/rounds/233-m2-layout/`、`handoff/STATUS.md`
