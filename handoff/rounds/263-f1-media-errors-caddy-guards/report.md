# 263 实现报告

## 结论

完成。F1 底座的第二批（B1、B2、B6、A7、A12、源码守卫）做完；另修了 Caddy 转发访客 IP 的安全问题。页面本身没改。发现「旧图只导了行、没导文件」，留给 264。

## 逐条结果

| 编号 | 结果 |
|---|---|
| T1 出图 | `media/api.go`：`api.Raw(GET /media/r/{id}/{file})` → `ServeThumbnailHTTP`：编号（`ParseID`）、`.webp` 后缀、规格白名单、原图任一不对 404；生成失败 500 并记日志；`image/webp`、缓存一年、文件留在卷里。去掉 `GET /api/media/r/{id}/{spec}`（回 JSON 和服务器文件路径） |
| T2 站点地图 | `content/sitemap.go` 重写：文章 `/news/<slug>/`、普通页 `/<slug>/`、没解散的战队、`published`/`finished` 的赛事、`published` 或 30 天内 `finished` 的内战；`lastmod` 按上海时区；robots 八行同旧站，`WithTestEnvironment` 时整站 `Disallow: /`（`main.go` 的 serve 按 `TEST_ENVIRONMENT` 设）。`/sitemap.xml`、`/robots.txt` 用 `api.Raw` 挂上 |
| T3 规格 | `media.SpecsTS()`；`sjtuow apigen` 一起写 `web/packages/api/src/gen/specs.ts`；`@sjtu-ow/api` 导出 `IMAGE_SPECS`、`ImageSpec`；站点 `src/media.ts` 的 `imageUrl(id, spec)`；260 的 8 处 `/api/images/{id}` 改成它 |
| T4 错误页 | `src/error-page.ts`：403/404/429/500/503 逐字照 `templates/errors`（503 是维护页的话），独立文档、`/static/css/error.css`、无脚本；`entry-server.ts` 出 `{kind: "error"}`，`errorStatusOf`：403/404/429 原样、0 和 502–504 → 503、其余 → 500；`server.ts` 渲染抛错兜底成 500 页（带转义的 `X-Request-ID`），SSR 自己也发 `error.css`；服务端应用 `throwUnhandledErrorInProduction` |
| T5 Caddy | `deploy/Caddyfile.new` 重写（见 request 第 5 条）；Compose：`caddy:2.10-alpine`、挂 `./error_pages`、web 拷 `error.css`、去掉 `STRICT_CSP`；`Dockerfile.web` 带上 `error.css` |
| T6 smoke | `e2e/caddy/smoke.sh`：`caddy validate` + 43 条 |
| T7 守卫 | `src/guards.test.ts`：6 条规则 + 自测 + 路由占位不增加 + 待重写列表只缩不涨 + 文件数 |

## 验收输出

### 整组

`bash scripts/remote-check.sh`，日志 `sjtu-ow-test:/srv/sjtu-ow-check/runs/20261010-150644-db367fa.log`，退出码 0：

```
      Tests  15 passed (15)
...
      Tests  55 passed (55)
...
首页壳 gzip：HTML 2770 + CSS 19504 + JS 70240 = 92514 字节（脚本上限 122880，合计上限 307200）
BUDGET-OK

== 全部通过 (07:07:15)
```

（`go test`、`apigen` 生成物无差异都在整组里。站点地图、出图的 Go 测试另用 `-count=1` 单跑过：日志 `20261010-145659-4faa03d`，`ok internal/platform/media`、`ok internal/content`。）

### 浏览器

`browser-check.mjs`，日志 `20261010-150716-fef4e07`：`BROWSER-CHECK-OK`（新加的 404 页一项在里面）。

### Caddy

`bash scripts/remote-check.sh run bash e2e/caddy/smoke.sh`，日志 `20261010-145809-46c0b96`，退出码 0：

```
caddy validate 通过
页面和接口的去向
  ✓ 首页去 SSR
  ✓ 访客 IP 是反代带来的那个（{client_ip}）
  ✓ 接口去 Go
  ✓ 接口的访客 IP
  ✓ 接口的写请求去 Go
  ✓ 页面地址的写请求 405
  ✓ 一键退订 POST 去 Go
  ✓ 退订页 GET 去 SSR
  ✓ sitemap 去 Go
  ✓ robots 去 Go
  ✓ 健康检查去 Go
  ✓ 日历去 Go
文件
  ✓ 构建产物 / 缓存一年 / theme.js / 每次问 / 固定图 / 缓存一天 / 错误页样式表
  ✓ favicon.ico 跳固定地址 / apple-touch-icon 跳固定地址
图片
  ✓ 已有的缩略图直接给 / 缓存一年 / 没有的缩略图交给 Go 现做 / 编号不是数字的缩略图 404
  ✓ 旧缩略图原样给 / 原图不公开 / 带哈希的字体样式表给 / 字体原件不给
安全头
  ✓ 页面的 CSP 是 Caddy 的（覆盖了上游带来的）/ 只有一条 CSP / 和 server.ts 的逐字一致
  ✓ 接口也带 nosniff / 文件也带 HSTS / Referrer-Policy / X-Frame-Options
请求体上限
  ✓ 普通接口超过 1 MB 是 413 / 传头像 2 MB 放行 / 传队标 2 MB 放行
维护页
  ✓ SSR 连不上：旧站的维护页 / 不缓存 / 策略只放开内联样式 / 状态码是 5xx
CADDY-SMOKE-OK
```

（上面把同一组的 ✓ 合成了一行，原样输出是每条一行，共 43 条。第一次跑的日志 `20261010-145721-cead5a6` 里图标两条是 ✗，见自查第 1 条。）

### 变异

`mutate.py`，日志 `20261010-150814-1a05bc5`，退出码 0：

```
基线全绿
抓到 转给 Go 的访客 IP 换回 {remote_host}（caddy 退出码 1）
抓到 转给 SSR 的访客 IP 换回 {remote_host}（caddy 退出码 1）
抓到 缺的缩略图不回源 Go（caddy 退出码 1）
抓到 一键退订的 POST 不去 Go（caddy 退出码 1）
抓到 接口没有 1 MB 上限（caddy 退出码 1）
抓到 CSP 不推迟设置（上游的 CSP 留着）（caddy 退出码 1）
抓到 错误页不链 error.css（site 退出码 1）
抓到 加载器的错误全当 503（site 退出码 1）
抓到 渲染抛错不再给 500 页（site 退出码 1）
抓到 服务端渲染在生产里吞掉组件的错误（site 退出码 1）
抓到 站点地图的文章地址没有结尾斜杠（go 退出码 1）
抓到 站点地图收了解散的战队（go 退出码 1）
抓到 出图不查规格白名单（go 退出码 1）
抓到 守卫的色板正则失效（site 退出码 1）
抓到 待重写列表多了一个干净的文件（site 退出码 1）
15 处全抓到，已改回，基线仍全绿
```

前一次（`20261010-150239-44cabe7`）「渲染抛错不再给 500 页」没抓到，原因和改法见自查第 5 条。

## 设计偏差

无。Caddy 的路由表和 12 号文档 3.4 一致；`/theme.js`、`/static/css/`、图标跳转、请求体上限是照 3.4 的原则补的细节。

## 未完成 / 顺带发现 / 需要确认

- **顺带发现（重要）**：`content.ImportLegacyContent` 只把 `wagtailimages_image` 的行导进 `images`，原图文件从没过新管线变成母版（`data/originals/<id>.webp`），导入的错误也被 `_ =` 吞掉。正式站的 479 张图因此在新栈里全部出不来（缩略图要从母版生成）。264 加一条把旧原图过新管线的导入
- **顺带发现**：`/api/images/{id}` 对任何人公开图片信息（上传者编号、原文件名）。留给图片那一组（后台内容）
- **顺带发现**：`docker-compose.new.yml` 里 `server` 的健康检查是每 30 秒跑一次 `sjtuow reconcile`（对账工具），不是 `/healthz`。不属于前台，记下
- **需要确认**：第 10 节六件仍未回复。Caddy 的修复（含访客 IP）要部署才生效

## 改动文件

- `server/internal/platform/media/api.go`、`media.go`、`media_test.go`
- `server/internal/content/sitemap.go`（重写）、`sitemap_test.go`（新）、`service.go`、`api.go`、`m4_full_test.go`
- `server/cmd/sjtuow/main.go`
- `web/packages/api/src/gen/index.ts`、`gen/specs.ts`（新，生成）、`src/index.ts`；`docs/api-reference.md`（生成）
- `web/apps/site/server.ts`、`browser-check.mjs`、`src/error-page.ts`（新）、`src/media.ts`（新）、`src/guards.test.ts`（新）、`src/entry-server.ts`、`src/main.ts`、`src/handle.test.ts`；8 个页面和部件的图片地址
- `deploy/Caddyfile.new`、`deploy/docker-compose.new.yml`、`deploy/Dockerfile.web`
- `e2e/caddy/smoke.sh`（新）
- `handoff/STATUS.md`、`AGENTS.md`、`handoff/rounds/263-f1-media-errors-caddy-guards/`
