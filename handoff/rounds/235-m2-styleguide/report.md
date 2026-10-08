# 235 实现报告

## 结论

完成。`/_styleguide/` 按现行站样张排了组件，访客和普通成员打开是 404。邮件样张仍是标题页，同样被挡住。

## 逐条结果

1. **样张页**。`Styleguide.vue` 用现行站同一套类名排了颜色、字体、标志、按钮、标签、图标、列表、表格、名片、表单、提示、正文、赛场横幅、首页块和评论。日期在 `loadStyleguide` 里按上海时区算好放进 `ow-state`，格式和 `ow_date` 一样（`2026.10.11`、`19:30`、`周日`）。样张组件单独成块，不进首页的入口脚本。
2. **只有干部看得到**。`styleguideHidden`：路径以 `/_styleguide/` 开头、会话里 `admin` 不是 true，服务端回 404，正文是「找不到这个页面」，没有样张。客户端换页也停在原地。邮件样张地址同样挡住。
3. **图标**。样张那 44 个名字的路径从 `icon.html` 补进 `icons.ts`（原来页头用到的还在）。

## 验收输出

测试机同一趟（日志 `20261008-202112-b1d2979`，退出码 0）：整组、浏览器检查、变异。

govulncheck：

```
No vulnerabilities found.

Your code is affected by 0 vulnerabilities.
```

根目录 Vitest 10 条，site 33 条：

```
 Test Files  5 passed (5)
      Tests  33 passed (33)
...
== 全部通过 (12:21:39)
```

构建产物：入口 `index-io0dZIYg.js` 137.23 kB（gzip 53.15 kB），样张块 `Styleguide-B4XoZor5.js` 26.29 kB（gzip 8.78 kB），样式 `index-DBJErt-L.css` 97.49 kB（gzip 17.58 kB）。

浏览器检查：

```
site ssr on :4515 (api http://127.0.0.1:4860, built assets)

BROWSER-CHECK-OK
```

变异：

```
抓到 A 样张对访客开放（退出码 1）
抓到 B 拿掉为战队报名（退出码 1）
抓到 C 名额格不再涂色（退出码 1）
三处都抓到，已改回
MUTATIONS-OK
```

干部打开样张时，去掉片段注释后有 `>设计体系样张</h1>`、`为战队报名`、`#9B3A33`，页面里没有 `style="`。名额格 `is-taken` 一共 36 处（8/10 三处、12/12 一处）。

## 设计偏差

没有。`docs/design.md` 没动。样张仍是设计 13.2.7 那一页，门槛仍是能进后台的人。

## 未完成 / 顺带发现

- **占位图还没接到新站**。地址写的是 `/static/img/placeholders/cover-07.svg` 这种现行站的路径，新的 SSR 服务不提供 `/static/`。并排截图要等资产接上再做，M2 的完成标准这一条还没达到。
- 邮件样张（34 封信的 HTML）是 M7 的事，这轮只把地址挡住。
- 体积还没写进 CI。入口 gzip 53.15 kB、样式 gzip 17.58 kB，离 300 KB 还远，但没有常驻断言。
- 新依赖：无。

## 改动文件

- `web/apps/site/src/pages/Styleguide.vue`、`components/SectionHead.vue`、`specimen.ts`、`specimen.test.ts`
- `web/apps/site/src/icons.ts`、`time.ts`、`router.ts`、`routes.ts`、`entry-server.ts`、`entry-client.ts`、`handle.test.ts`
- `handoff/rounds/235-m2-styleguide/`、`handoff/STATUS.md`
