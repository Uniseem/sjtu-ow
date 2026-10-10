# 261 自查

连做轮次，自查不能替代独立复核。

## 换角度核对

1. **类名的误报**：第一遍拿 `input.css` 的类名和页面比，报出 16 个「不存在的类」。回头拿旧模板再比一遍，其中 `c-crumbs__sep`、`c-row__main`、`c-stats__list`、`c-brand__name`、`c-hero__emblem-body`、`c-media-grid--3`、`c-stage--team` 是旧模板里就有、本来就不带样式的挂钩类，不算问题；`c-hue` 是 `c-hue-${…}` 被截断的误匹配。文档最后只列 7 个两边都没有的类，外加后台 25 个文件写错的 `c-notice--warning`
2. **色板类的误报**：第一遍把 `text-white`、`stroke-white` 也算成被关掉的颜色。`input.css` 第 31、32 行保留了 `--color-white`、`--color-black`，这两个能用；改正后是 17 个前台页面用了被关掉的色板（`BrandMark.vue` 是 M2 的，没问题）
3. **「客户端不是激活」**：不靠印象，读了本机 `node_modules` 里 Vue 3.5.43 的 `runtime-dom.cjs.js`：`createApp().mount()` 先 `container.textContent = ""` 再 `mount(container, false)`，确实是清空重画
4. **登录的 `verify_required`**：读 Go 的 `LoginOut`，确认是 200 + `result: "verify_required"`，所以页面的 `res.ok` 分支会把人送回首页
5. **数量**：`routes.ts` 里 `page(` 34 条、`dynamicPage(` 15 条，加上 `/`、`/teams/`、`/_styleguide/` 共 52 条前台路由；`admin(` 40 条；`pages/admin/` 27 个文件，其中 17 个本该能改东西、写请求数为 0
6. **`<title>`**：第一稿写「有的是 SJTU-OW」，回头逐页 `curl` 了一遍，改成实测的四种写法

## 没核实的（文档里标了「读码」）

- S2 图片坏图、S9 待发信发不出去、S10 宣言改掉公开段位、S14 后台导航只剩首页：都是读代码得出的，没有登录正式站去点（不在正式站上做写操作）
- 回滚窗口的到期时间按快照文件名推算，服务器上旧镜像和数据卷还在不在没有登录去看

## 结论

自查通过。文档的现状一节是 2026-10-10 的快照，之后进度只在 STATUS 的「前台页面进度」表里更新。
