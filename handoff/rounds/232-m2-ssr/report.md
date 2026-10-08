# 232 实现报告

## 结论

完成。前台有一个 73 行的 `server.ts`：只接 GET/HEAD，能补斜杠、画页面、把 `<` 转义进状态脚本。路由先只有 `/` 和 `/teams/`。

## 逐条结果

1. `web/apps/site` 用 Vue 3.5、Vue Router 4、`@unhead/vue` 2、Vite 7。`createHead` 在 unhead 2 里不从包根导出，服务端用 `@unhead/vue/server`，浏览器里用 `@unhead/vue/client`。
2. POST 是 405。`/teams?x=1` 301 到 `/teams/?x=1`。不存在的地址 404，正文是「找不到这个页面」。
3. `load()` 和 `/api/session` 并行。Cookie、`X-Real-IP`、`X-Request-ID` 转交，超时 5 秒。`load()` 401 就 302 到 `/accounts/login/?next=`。接口连不上是 503「站点暂时连不上」。
4. `theme.js` 在 head 最前。charset 和 viewport 只出现在 unhead 写出的标签里，模板里没有。状态在 `id="ow-state"`，`<` 换成 `\u003c`。没有 `style="`。
5. 访客 `Cache-Control: no-cache`，登录用户 `private, no-store`，都有 `Vary: Cookie`。出错的页面是 `no-store`。
6. 横幅「页面脚本没有加载成功……」在页面里。样式在 `input.css` 末尾：没有 `js-ready` 时 8 秒后显示。
7. `/` 的标题是 SJTU-OW。`/teams/` 的标题是「战队」。

## 验收输出

变异在测试机上先红再改回。日志 `20261008-190857` 那次命令的结尾（退出码 0）：

```
抓到 A 放行 POST（退出码 1）
抓到 B 不转义小于号（退出码 1）
抓到 C 登录用户也能被缓存（退出码 1）
三处都抓到，已改回
MUTATIONS-OK
```

B 拆掉转义之后，状态脚本里是 `"marker":"<"`，测试要的 `\u003c` 不在了。

整组 `sh scripts/check.sh`，日志 `20261008-191001-3f83467`，退出码 0。govulncheck：

```
No vulnerabilities found.
Your code is affected by 0 vulnerabilities.
```

前端段 `pnpm install --frozen-lockfile` 是 Already up to date。样式 4 条、SSR 8 条通过。客户端构建 gzip 41.28 kB（`index-EzTL-aiA.js`），服务端 `entry-server.js` 6.07 kB。

```
== 全部通过 (11:10:25)
```

新依赖：`vue`、`vue-router`、`@unhead/vue`、`vite`、`@vitejs/plugin-vue`。发布许可证都是 MIT。12 号文档已经定了用 Vue。

## 设计偏差

没有改设计。6.2 里「Vite 清单给出要预加载的分块」这轮没接上：测试走的 `documentHTML` 仍引用 `/src/entry-client.ts`。构建产物在 `dist/client`，页面还没指向它。

## 未完成 / 顺带发现 / 需要确认

- 没有在浏览器里打开页面。激活、换页、CSP 是否零违规，这轮没看。
- 找不到地址时 Vue Router 会在 stderr 打一行 No match found。状态码仍是 404。
- 客户端脚本 gzip 41 kB 只是运行时，还没算上样式和布局。体积预算等首页壳接上再量。
- 页头、页脚、主题菜单、加载条、样张页还没做。

## 改动文件

- `web/apps/site/`（`server.ts`、入口、两页、测试）
- `web/package.json`、`web/pnpm-workspace.yaml`、`web/pnpm-lock.yaml`
- `web/packages/styles/input.css`（末尾加了无脚本横幅）
- `.gitignore`
- `handoff/rounds/232-m2-ssr/`、`handoff/STATUS.md`
