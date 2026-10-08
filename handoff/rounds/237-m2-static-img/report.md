# 237 实现报告

## 结论

完成。样式里的装饰图改成 `/static/img/…`，独立 SSR 服务从仓库的 `static/img/` 发出这些文件，缓存一天，路径越不出这个目录。

## 逐条结果

1. **样式地址**。`input.css` 里 19 处 `url("../img/…")` 改成 `url("/static/img/…")`。现行站的样式在 `/static/css/`，相对地址解析出来也是这一处；新站的样式在 `/assets/`，相对地址对不上。
2. **发文件**。`/static/img/` 从仓库的 `static/img/` 读（svg、png、ico）。`Cache-Control: public, max-age=86400`。`..`、百分号编码的跳出都拒绝。源码在 `web/apps/site`（往上三级），构建产物在 `dist/server`（往上五级），启动目录是站点目录，三处都找。
3. **浏览器**。检查请求 `/static/img/placeholders/cover-07.svg`，要 200、`image/svg+xml`、缓存一天。

第一次跑（日志 `20261008-203410-ef06033`）浏览器拿到 404：构建产物只按源码的三级往上找。改了查找之后重跑，下面是这一趟。

## 验收输出

测试机同一趟（日志 `20261008-203738-93d25ad`，退出码 0）：整组、浏览器检查、变异。

govulncheck：

```
No vulnerabilities found.

Your code is affected by 0 vulnerabilities.
```

样式 5 条（多了钉 `/static/img/` 的那一条），site 35 条（多了目录限制和缓存）：

```
 ✓ styles.test.mjs (5 tests) 4ms
...
 Test Files  5 passed (5)
      Tests  35 passed (35)
...
首页壳 gzip：HTML 2506 + CSS 17592 + JS 53151 = 73249 字节（脚本上限 122880，合计上限 307200）
BUDGET-OK
== 全部通过 (12:38:06)
```

浏览器检查：

```
site ssr on :4469 (api http://127.0.0.1:4717, built assets)

BROWSER-CHECK-OK
```

变异：

```
抓到 A 目录限制拿掉（退出码 1）
抓到 B 山脊图改回相对地址（退出码 1）
抓到 C 缓存改成 max-age=0（退出码 1）
抓到 D 构建产物找不到图（退出码 1）
四处都抓到，已改回
MUTATIONS-OK
```

## 设计偏差

没有。`docs/design.md` 没动。地址和 12 号文档 3.4 的固定路径一致。

## 未完成 / 顺带发现

- 样张和旧站并排截图还没做。图已经能取到。
- 构建时 Vite 提示这些绝对地址「留到运行时再解析」。这是要的结果：图不打进带哈希的包，地址保持 `/static/img/…`。
- 字体库（D4）按 12 号文档在 M8。公开页样式用的是系统字体栈；现行站只有后台生成过字体样式表时才多挂一张。
- 新依赖：无。

## 改动文件

- `web/packages/styles/input.css`、`web/styles.test.mjs`
- `web/apps/site/server.ts`、`budget.mjs`、`browser-check.mjs`、`src/handle.test.ts`
- `handoff/rounds/237-m2-static-img/`、`handoff/STATUS.md`
