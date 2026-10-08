# 233 M2 第三轮：前台布局

## 背景

M2 前两轮（231 样式、232 薄 SSR）打好了底：`input.css` 在 `packages/styles`，`server.ts` 能画页面、分流错误、转义状态。但拼出来的页面只有 `<main><h1>`：没有页头页脚，HTML 还指着源码入口 `/src/entry-client.ts`，也从没在浏览器里看过激活。本轮把 12 号文档 6.3–6.6 里的布局件做出来，并还掉 232 的两件遗留。

## 本轮范围

**做**（12 号文档 6.2 第 7 条、6.3–6.6）：

1. **HTML 指向构建产物**（232 遗留 1）：`documentHTML` 接收来自 Vite 客户端清单的 assets（入口脚本、样式表、modulepreload）；生产模式注入哈希过的地址，没有 assets（开发）仍指 `/src/entry-client.ts`。样式经 `entry-client.ts` 里的 `import "@sjtu-ow/styles/dist/site.css"` 进 Vite 清单。SSR 构建的入口从 `src/entry-server.ts` 换成 `server.ts`（构建产物本身就是一个能 `node` 起的完整服务）。
2. **页头页脚**：`SiteHeader`（品牌、主导航六项带 `aria-current`、搜索表单、手机抽屉、加载条元素）、`SiteFooter`（说明、社区/参与/账号/关于四栏、底行年份按上海时区）、跳到正文链接、`CIcon`（本轮需要的图标子集，路径照 `components/icon.html` 原样）、`SLink`（路由存在就走 SPA，不存在就是普通链接，SSR 和客户端画得一样）。
3. **主题**：`public/theme.js` 暴露 `window.owTheme`（`current()`/`set()`，保留 `ow-theme` 键、跨标签同步、切换交叉淡化、theme-color 粉刷，`localStorage` 键不变）；`ThemeMenu` 组件读它，激活前 `hidden`。
4. **加载条**：SPA 路由加载条（12 号 6.6：`CLoadbar`，150 毫秒内不出现、慢慢爬、到了冲满再淡出——节奏由已搬过来的 CSS 定，跨整页的接力不做）。纯逻辑拆成可测模块。
5. **右键菜单**：`CContextMenu` 全局组件，行为照 `static/js/contextmenu.js`（Shift 右键、输入框、触屏用原生；键盘导航；Esc/点外关闭；复制有回执）。条目分组拆成纯函数。
6. **提示**：`Toasts`（`c-toast` 样式、`aria-live`、自动消退）＋ `toast()`，本轮没有页面用它发信，机制和测试先行。
7. **viewer**：232 只从 `/api/session` 拿了 `loggedIn`；本轮把 `user`（`nickname`、`admin`）带进 SSR 渲染和 `ow-state`，页头账号区和页脚账号栏据此画（12 号 3.3：SSR 直接画登录态）。
8. **错误页不激活**：403/404/503 的正文不是 App 画出来的，不该让入口脚本去激活它。错误页改成无脚本裸页（有样式、无 `ow-state`、无入口脚本）。
9. **浏览器里验证**（232 遗留 2）：`web/apps/site/browser-check.mjs`，照 220 e1 的方法用 CDP 驱动无头 Chromium：激活（`js-ready`）、严格 CSP 零违规（standalone 服务在 `STRICT_CSP=1` 时按 12 号 6.9 加响应头）、SPA 换页、主题切换、右键菜单、无脚本 8 秒横幅、404。在测试机上跑（chromium 已装）。

**不做**：按现行站地址补路由、`/_styleguide/`、接口封装（401/待发信/幂等键）、CSP/体积进 CI 的常驻测试、字体（等 D4 成品包）、头像图片和默认头像池（viewer 还没有头像字段）、`/api/session` 的 Go 实现（M3；本轮 SSR 按约定的形状消费，测试里给桩）、搜索页本身。

## 任务

| # | 任务 | 验证 |
|---|---|---|
| 1 | assets 两态注入 + 样式进清单 | vitest：有清单时出 `<link rel="stylesheet">`、`modulepreload`、哈希入口；无清单时指 `/src/entry-client.ts`；`pnpm --filter @sjtu-ow/site test` 构建通过 |
| 2 | 页头页脚（导航、搜索、抽屉、账号区、页脚、图标、SLink） | vitest 经 `render()` 断言六项导航、`aria-current` 前缀规则、访客/成员/干部三态、页脚说明与年份 |
| 3 | 主题（theme.js 的 `window.owTheme` + 菜单） | browser-check：点「深色」后 `data-theme=dark`、`localStorage ow-theme=dark`、`aria-pressed` |
| 4 | 加载条 | vitest：假时钟下 start/arrive/stop 的类切换、进度矩阵解析 |
| 5 | 右键菜单 | vitest：条目分组纯函数；browser-check：链接上右键出菜单、Esc 关 |
| 6 | 提示 | vitest：入队与自动消退 |
| 7 | viewer 贯通 | vitest：三态渲染；browser-check：桩 API 的用户名出现在页头 |
| 8 | 错误页裸页 | vitest：404 正文无入口脚本、无 `ow-state` |
| 9 | 浏览器验证 | 测试机 `remote-check.sh run`：`browser-check.mjs` 退出码 0，全程零 CSP 违规、零控制台错误 |

## 验收标准

1. `pnpm test`（web 根）全绿，测试机 `bash scripts/remote-check.sh` 整组全绿（Go + pnpm）。
2. `mutate.py` 的每处变异先红后恢复（硬规则 7）。
3. `browser-check.mjs` 在测试机上通过：激活、换页、主题、右键菜单、无脚本横幅、404，零 CSP 违规。
4. `server.ts` 仍 ≤ 300 行（12 号 6.2 的目标）。

## 明确不做（防扩大）

- 不加新依赖：不装 `jsdom`/`@vue/test-utils`，组件行为在真浏览器里验（browser-check），SSR 输出在 vitest 里验。
- 不动 `server/`（Go）、不动现行站 Django 代码、不动正式站。
