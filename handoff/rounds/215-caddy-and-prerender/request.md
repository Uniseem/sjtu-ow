# 215 轮要求：Caddy 和预渲染（C4、C5、C6、C9、F1）

## 背景

210 全站复核建议顺序的第 4 步（`rounds/210-full-review/review.md` 末尾）。211–214 修完了前三步；这一轮是 Caddy 直接对外的那几条，加上预渲染页的两处：五条都是「设计写了、实现没做到」，不需要用户拍板。

### C4：上传的字体原文件谁都能下载

原文件存在 `MEDIA_ROOT/fonts/<字体编号>/original/<上传文件名>`，Caddy 的 `handle /media/*` 直接 `file_server`。设计 15.2「前台只使用重新生成的 WOFF2 分片，不直接提供上传的原始文件」。后台的「下载字体文件」走 Django（`core/fonts/admin_views.py`，`FileResponse`），不受影响。正式站现在没有上传过字体（`/app/media/fonts/` 下只有 `css/`），没有已经泄露的文件。

### C5：下线内容的静态文件不是立即删

`core.prerender.request_removal` 只在提交后 `enqueue` 一个 `remove_prerendered` 任务。worker 不在（停了、卡住、排队）时，撤回的文章、改回草稿的赛事还从静态文件公开。设计 13.13.5「不再公开的内容必须立即删除静态文件；删除失败时记录错误」，15.2、风险表也写「立即删除」。`web` 容器的 `prerendered` 卷是可写挂载（Caddy 那边才是只读）。

### C6：预渲染页和静态文件没有 HSTS

Caddy 的 `(page_security)` 只有 CSP、XFO、nosniff、Referrer、COOP。首次访问几乎都落在预渲染首页，HSTS 只有 Django 渲染的页面才带。10-07 在正式站核对过：`curl -sI https://sjtu.ow-shanghaiuniversity.com/` 没有 `Strict-Transport-Security`，`/accounts/login/` 有（`max-age=31536000; includeSubDomains; preload`）。设计 15.2「全站 HTTPS，开启 HSTS」。

### C9：`/healthz` 对公网返回全部细节

返回数据库异常原文、磁盘百分比、积压任务数。设计 9.x 的网址表写「公开，只返回状态」。外部监控只要状态码。

### F1：状态片段请求失败时占位区永远是灰块

`static/js/state.js` 只在 `htmx.ajax(...)` 成功时去掉 `ow-state-pending`。网络错误时 htmx 2 会 reject，没有处理；HTMX 没加载上（被拦、加载失败）时 `fill()` 直接返回，也不去掉。结果是页头账号区、提示条、报名入口、整个评论区都是灰块、内容隐藏。设计 13.13.3「脚本加载失败时，占位区域保持未登录访客的内容，里面的链接都指向对应的实时渲染页面，核心流程仍然可用」。

## 本轮范围

做：

1. **C4**：Caddy 对 `/media/fonts/` 下除了带哈希的字体样式表和 WOFF2 分片以外的地址一律 404（放在 `handle /media/*` 前面）。
2. **C5**：`request_removal` 在提交后由当前进程直接删静态文件和记录（`prerender.drop`）；删除出错时记错误日志，并排一个 `remove_prerendered` 任务让 worker 再删一次。
3. **C6**：Caddy 给预渲染页、`/static/`、`/media/` 的响应加上和 Django 一字不差的 `Strict-Transport-Security`；Django 自己的响应不重复加。
4. **C9**：`/healthz` 对外只给总状态和每一项的「正常 / 不正常」（不给原文、百分比、数量）；超级管理员登录后看完整细节（后台待办里「worker 没在运行」的链接指向它）。状态码规则不变。
5. **F1**：`state.js` 在片段请求成功、失败（网络错误、429、5xx）时都去掉骨架；HTMX 一直没加载上或请求一直不回时，8 秒后也去掉，显示未登录访客的内容。请求晚到的话照样填进去。
6. 设计先改：13.13.3（失败时怎么显示）、13.13.5（谁来删、失败怎么办）、15.2（HSTS 由 Caddy 补上预渲染页和静态文件；字体原文件 404）、16.6（对外只给状态）。附录 D 记 v7.18。

不做：

- 不给 `/healthz` 加 IP 白名单之类的访问控制（外部监控要能访问）。
- 不搬字体原文件的存储位置（Caddy 拦住就够了，搬文件要迁移已有数据）。
- 不改 Wagtail 原图（`/media/original_images/`）的公开方式：那是公开图片，本来就要给人看。
- 不给片段请求加自动重试（429 时要等 60 秒，重试没有意义；网络错误让用户刷新）。
- 210 复核里别的低严重度条目不在这一轮。

## 任务和验证

| 条目 | 改动 | 「拆掉就红」的测试 | 真环境验证 |
|---|---|---|---|
| C4 | `deploy/Caddyfile` 加 `handle /media/fonts/*` → 404 | 测试读 Caddyfile：这块在 `/media/*` 前面、只回 404；带哈希的两类仍是 `file_server` | 测试机上用真的 `caddy:2.10-alpine` 起这份 Caddyfile：原文件 404、分片和样式表 200 |
| C5 | `core/prerender.py` 的 `request_removal` | 提交后文件已经不在、记录已删，**不依赖 worker 跑任务**；删除抛错时记日志、排了任务 | — |
| C6 | `deploy/Caddyfile` 的 `(page_security)`、静态和上传文件 | 测试读 Caddyfile：值和 Django 的 `SECURE_HSTS_*` 拼出来的一样；预渲染、`/static/`、`/media/` 都带；Django 那条路不加 | 同上，用真 Caddy 看响应头 |
| C9 | `core/views.py` 的 `healthz` | 匿名请求的响应里没有 detail、没有数字；超管有；坏了照样 503 | 升级正式站后 `curl` 一次 |
| F1 | `static/js/state.js` | 字符串守卫（成功、失败两条路都去掉骨架；有 8 秒兜底） | 测试机上无头 Chromium 打开真的预渲染页：片段接口正常、429、500、断开连接、一直不回、HTMX 加载失败六种情况，骨架都在限定时间内去掉；用改之前的 `state.js` 跑同一个脚本，除「正常」外都应该红 |

## 验收标准

- `bash scripts/remote-check.sh` 整组全绿（ruff、tailwind、pytest、makemigrations、check --deploy、docker build）
- 本轮新加的每条守卫做变异：改坏会红，改回会绿（`mutate.py`，先跑基线）
- Caddy 和浏览器两个真环境脚本在测试机上跑通，输出原样写进报告
- 改了 `backoffice/` 以外的前端脚本：跑一次 `journey.py`、`journey.py pages`
- 正式站先备份再升级，升级后核对首页带 HSTS、字体原文件地址 404、`/healthz` 不带细节
