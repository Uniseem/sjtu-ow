# 236 实现报告

## 结论

完成。前台内容安全策略和 12 号文档 6.9 逐字一致，首页壳的体积在每次 `pnpm test` 里量，超了就红。

## 逐条结果

1. **策略**。`server.ts` 的 `CSP` 补上 `frame-src 'self' https://player.bilibili.com`。整句和 6.9 一样，测试钉住这句话，并且不许出现 `unsafe-`。独立服务在 `STRICT_CSP=1` 时仍把这句写进响应头。
2. **体积**。`budget.mjs` 挂在站点的 `pnpm test` 末尾，构建之后跑。它渲染首页，再 gzip：HTML、入口脚本、入口静态带上的样式和预加载脚本。样张那一块是路由懒加载，不算进首页。脚本合计超过 120 KB，或 HTML + 样式 + 脚本超过 300 KB，进程退出码 1。

## 验收输出

测试机同一趟（日志 `20261008-202631-d5bdb21`，退出码 0）：整组、浏览器检查、变异。

govulncheck：

```
No vulnerabilities found.

Your code is affected by 0 vulnerabilities.
```

site 34 条（多了钉策略的那一条）：

```
 Test Files  5 passed (5)
      Tests  34 passed (34)
...
首页壳 gzip：HTML 2507 + CSS 17584 + JS 53151 = 73242 字节（脚本上限 122880，合计上限 307200）
BUDGET-OK
== 全部通过 (12:26:56)
```

73242 字节约 71.5 KB，在 300 KB 以内；脚本 53151 字节约 51.9 KB，在 120 KB 以内。

浏览器检查：

```
site ssr on :4422 (api http://127.0.0.1:4802, built assets)

BROWSER-CHECK-OK
```

变异：

```
抓到 A 策略少了 frame-src（退出码 1）
抓到 B 脚本上限改成 1 KB（退出码 1）
两处都抓到，已改回
MUTATIONS-OK
```

## 设计偏差

没有。`docs/design.md` 没动。

## 未完成 / 顺带发现

- 样张和旧站并排截图还做不了：`/static/img/` 仍没接到新站。
- 字体（D4）还没做。
- 新依赖：无。

## 改动文件

- `web/apps/site/server.ts`、`budget.mjs`、`package.json`、`src/handle.test.ts`
- `handoff/rounds/236-m2-csp-budget/`、`handoff/STATUS.md`
