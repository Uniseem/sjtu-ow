# 263 F1 底座（二）：出图、站点地图、错误页、Caddy、源码守卫

## 背景

接 262。`docs/frontend-migration.md` 第 11 节 F1 剩下的、和页面无关的几块：

- S2、B1：所有图片是坏图——页面把 `<img>` 指向返回 JSON 的 `/api/images/{id}`，出图的处理函数没挂路由，Caddy 的回源写法也不成立
- S12、B2：`/sitemap.xml`、`/robots.txt`、`/favicon.ico` 404；Go 里写好的站点地图和旧站对不上（没有结尾斜杠、少了战队赛事内战、robots 规则不一样）
- C11、A12：错误页是一行字，不是旧站的样子
- S11、C14、B6：一键退订 405；安全头不在 Caddy；502–504 不出维护页；没有请求体上限
- C2–C5 的复发：没有源码守卫，260 那样的色板类、编出来的类、裸 `fetch("/api/…")` 还能再写进来

读 Caddy 时还发现一处安全问题：`Caddyfile.new` 转发给 Go 和 SSR 的 `X-Real-IP` 写的是 `{remote_host}`。正式站前面是用户的反代（经 WARP，`100.96.0.0/12`），所以每个访客都成了反代那一个 IP——登录限流、同账号失败锁、注册限流全站共用一个计数。旧站 Caddyfile 用的是 `{client_ip}`。

## 本轮范围

做：

1. Go：`GET /media/r/{id}/{spec}.webp` 出图本身（编号、后缀、规格、原图任一不对 404；生成失败 500 并记日志；做好的文件留在 media 卷）；去掉回 JSON 和服务器文件路径的 `GET /api/media/r/{id}/{spec}`
2. Go：`/sitemap.xml`、`/robots.txt` 挂上，内容照旧站 `content.views`（文章 `/news/<slug>/`、普通页 `/<slug>/`、没解散的战队、发布或结束的赛事、已发布或 30 天内结束的内战；日期按上海时区；robots 八行，测试站整站不让抓）
3. Go → TS：apigen 一起生成 `specs.ts`（缩略图规格白名单）；前端 `imageUrl(id, spec)`，规格不在白名单编译不过；260 的 8 处 `/api/images/{id}` 改成它（规格照用途先挑，页面重写时照旧模板核）
4. 错误页：`error-page.ts` 照 `templates/errors/*.html` 逐字写 403、404、429、500、503（503 用旧站维护页的话）；独立的文档、链 `/static/css/error.css`、没有脚本；SSR 的加载器错误按状态分：403/404/429 原样，连不上和 502–504 是 503，别的（Go 的 500、加载器里的 bug）是 500；渲染抛错也给 500 页，不再让请求挂着
5. Caddy（`deploy/Caddyfile.new`）：整张表放进一个 `route` 按写的顺序匹配；`X-Real-IP {client_ip}`；安全头在 Caddy 统一加（推迟设置，覆盖上游）；`/media` 根目录改对（卷挂在 `/var/media`）；缩略图在就给、不在回源 Go；旧缩略图原样；字体只给带哈希的；其余 media 404；`POST /unsubscribe/*` 去 Go；`/favicon.ico`、`/apple-touch-icon.png` 301；`/theme.js`、`/static/css/` 由 Caddy 给；非读的页面请求 405；502–504 出维护页（单独一条只放开内联样式的策略）；请求体上限（传图接口 16 MB、其余接口 1 MB）。Compose：Caddy 固定 2.10、挂 `deploy/error_pages`、web 把 `error.css` 拷进 assets 卷、去掉 `STRICT_CSP`（CSP 由 Caddy 发）
6. `e2e/caddy/smoke.sh`：真 Caddy 容器 + 两个桩服务，逐条验路由、访客 IP、文件、图片、安全头、请求体上限、维护页
7. 源码守卫 `guards.test.ts`：色板类、`input.css` 和旧模板里都没有的组件类、`.vue` 里的裸 `/api/`、`style` 绑定、`v-html`、`any`；260、253 的文件列在「待重写」里，列表只能缩短（列着的文件不再违反任何一条就必须划掉）；路由表的标题占位不许增加

不做：

- 页面本身（F2 起）
- 头像、队标的上传管线（个人中心那一组）
- 邮件预览页的 CSP（发信、样张那一组）
- 部署（第 10 节第 1 件还没回复）

## 任务与验证

| 编号 | 验证 |
|---|---|
| T1 出图 | `go test`：真注册表上 GET 出图、`image/webp`、缓存一年、文件留在卷里；坏规格、错后缀、非数字编号、不存在的图都 404；旧 JSON 探针 404 |
| T2 站点地图 | `go test`：固定数据下地址列表逐条一致（含草稿、解散、取消、30 天前结束的不在）；`lastmod` 按上海时区跨日；robots 逐字一致、测试站整站不让抓 |
| T3 规格 | `go test`：`specs.ts` 列全白名单；整组的生成物无差异检查 |
| T4 错误页 | Vitest：404 是独立文档、`error.css`、旧站文案、没有脚本、没有 `style` 属性；403、429、500（带转义的请求编号）、502 → 503 维护页；渲染抛错 → 500。browser-check：真浏览器打开 404，样式表是 `error.css` 且生效、零脚本、零报错 |
| T5、T6 Caddy | `smoke.sh` 全部 ✓（`caddy validate` + 四十多条） |
| T7 守卫 | Vitest：每条规则在待重写之外零违规；每条规则的自测（抓得到已知的坏例子）；待重写列表里没有已经干净的文件 |

变异：拿掉 `{client_ip}`、拿掉缩略图回源、拿掉 `POST /unsubscribe` 路由、拿掉 `request_body` 1 MB、错误页丢掉 `error.css`、加载器错误全当 503、站点地图去掉结尾斜杠、出图不查规格、守卫的色板正则失效——各自的测试必须红。

## 验收标准

- 测试机整组退出码 0；browser-check `BROWSER-CHECK-OK`；`smoke.sh` `CADDY-SMOKE-OK`；变异全红
