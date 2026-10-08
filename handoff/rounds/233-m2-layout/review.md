# 233 复核结果（自查）

## 结论

通过。九条任务全部完成；验收三样（整组、browser-check、七处变异）都在测试机上真跑过、退出码 0。

## 验证记录

1. **重跑**：整组在测试机上来回跑了八次才全绿——前三次的失败（CIcon 的 `./icons` 路径、断言写错、Vue 片段注释）都是测试真在拦，不是摆设。最终日志 `20261008-195507-50f0bde` 退出码 0，site 24 条 vitest 全过。
2. **改坏看红**：`mutate.py` 七处（样式表不进页面、导航前缀匹配改精确、访客也画成员菜单、加载条不清 is-loading、右键菜单没有图片组、有昵称也当访客、提示不会自己走）每处单独改坏都在测试机变红（日志 `20261008-195629-38db7a6`），改回后基线仍绿。
3. **浏览器**：`browser-check.mjs` 在测试机的无头 Chromium 下 `BROWSER-CHECK-OK`（日志 `20261008-195534-c28257d`）。它抓到过两个 vitest 抓不到的问题：丢了 `page-data` 的 provide（首屏水合不重画、一换页正文就空）、清单入口键是 `index.html` 不是 `src/entry-client.ts`。这正是 232 留下「没在浏览器里看过」要还的债。
4. **对照设计原文**：页头（base.html 39–102 行）、账号区（account_area.html）、页脚（base.html 110–144）、主导航（main_nav.html 的路径前缀规则）、主题菜单、右键菜单（contextmenu.js 的条目、键盘导航、原生豁免）、无脚本横幅（6.10 的 8 秒纯 CSS）逐块比对过，类名、文字、aria 属性照抄。图标路径与 `components/icon.html` 逐条一致（`icons.test` 守着每个路径以 M 开头且非空）。
5. **12 号 6.2 的纪律**：`server.ts` 169 行（≤ 300）；模板无 `<meta charset>`、无 `style="`（vitest 守卫）；组件 setup 不碰 window/document（ThemeMenu、WeChatHint、CContextMenu 都在 onMounted 里）；时间走 `time.ts` 的上海时区；没有 `:style`。

## 发现的问题

建议修（都不挡本轮）：

- 客户端导航里 `load()` 抛 401/403 时浏览器端没有分流（服务端有）——接口封装轮（6.4）的活，到时在 `beforeResolve` 里接。
- 主题的跨标签 storage 同步、`theme-color` 粉刷、加载条的实际节奏（CSS 动画的观感）没进 browser-check——CSS 是原样搬的，节奏风险低；跨标签行为下一轮顺手加一条。
- 页头/抽屉的搜索表单提交后全页到 404（`/search/` 没有路由），路由补全轮一起接。

## 判断里最没把握的

- 无头 Chromium 里 `pointer: fine` 不匹配，browser-check 用 `addScriptToEvaluateOnNewDocument` 垫了 matchMedia——右键菜单的行为是在「假装是桌面」下验的。真机上精确指针本来就用同一条规则（与现行站 contextmenu.js 逐字一致），风险很小，但没有在真桌面浏览器里点过。
- 观感（页头页脚长得像不像现行站）没有并排截图比对——M2 的完成标准本来就要等 `/_styleguide/` 和样张页，本轮只保证了结构和类名照抄。

## 文档更新

- `handoff/STATUS.md`：`round`/`next`、M2 表加 233 行、「现在该谁动手」加 233 段
- `AGENTS.md`：新栈一节加 browser-check 的用法；「已知的坑」加 Vue SSR 片段注释和 Vite manifest 两个坑
- `docs/design.md` 没动（本轮没有设计变化）；`README.md` 没动（没有命令或运维变化）
