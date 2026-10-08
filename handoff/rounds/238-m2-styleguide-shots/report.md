# 238 实现报告

## 结论

完成。样张页和现行站在同一台机器、同一个无头 Chromium 里并排截 `#main`，正文一致，像素差 0.0268%，高度都是 13026px。首页壳 gzip 73530 字节，仍在 300 KB 以内。M2 的完成标准达到。

## 逐条结果

1. **样张包进 `<main id="main">`**。现行站的正文在这块里。新站原来样张写在 `main` 外面，截图对不齐。
2. **并排截图**。1280 宽、浅色、减少动态效果。两边都不挂后台生成的排版样式表（`init_site` 之后清掉 `font_css_path`），只用设计体系那份样式。页头账号区不比：旧站可能有头像图，新站只有首字，那是 M3。比较的是 `#main`。
3. **色块类名**。`bg-surface` 这些类写在 `specimen.ts`，用 `:class` 绑上。样式扫描只看 `.vue`，白底色块是透明的。补上对 `specimen.ts` 的扫描。
4. **懒加载的图**。视口以下的图在截图前还没请求，旧站大片是空盒子。比较脚本把它们改成马上加载，再滚过整页。

第一次像素比较（日志 `20261008-205719-0acfb6b`）正文已经一致，像素差 13.0336%。上面 3、4 修完之后重跑，才是下面这一趟。

## 验收输出

并排截图（日志 `20261008-210445-16d8905`，退出码 0）：

```
正文一致。像素差 0.0268%，高度 13026 / 13026（差 0px）
COMPARE-OK
```

整组、浏览器检查、变异同一趟（日志 `20261008-210654-cfa1fe7`，退出码 0）。

govulncheck：

```
No vulnerabilities found.

Your code is affected by 0 vulnerabilities.
```

样式 6 条（多了色块类名那一条），site 35 条：

```
 ✓ styles.test.mjs (6 tests) 3ms
...
 Test Files  5 passed (5)
      Tests  35 passed (35)
...
首页壳 gzip：HTML 2508 + CSS 17870 + JS 53152 = 73530 字节（脚本上限 122880，合计上限 307200）
BUDGET-OK
== 全部通过 (13:07:19)
```

浏览器检查：`BROWSER-CHECK-OK`。

变异：拿掉样张的 `id="main"`，`handle.test.ts` 报 `expected '…' to contain '<main id="main"'`（退出码 1）。拿掉 `@source "../../apps/site/src/specimen.ts"`，样式测试报 `/\.bg-bg\{/` 对不上（退出码 1）。两处都改回，基线仍绿。

```
抓到 A 样张去掉 id=main（退出码 1）
抓到 B 不再扫描 specimen.ts（退出码 1）
两处都抓到，已改回
```

截图比较不进每次 `pnpm test`（要起 Django）。
