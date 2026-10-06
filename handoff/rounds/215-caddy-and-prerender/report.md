# 215 实现报告：Caddy 和预渲染（C4、C5、C6、C9、F1）

## 结论

完成。210 复核建议顺序第 4 步的五条全部修好（设计 v7.18 先行）：字体原文件 404、下线内容由当前进程当场删、Caddy 自己发的文件带 HSTS、`/healthz` 对外只给状态、状态片段请求失败或 8 秒没回来时去掉骨架。新测试 11 条，14 处变异全部被抓到；测试机整组检查 1967 条全绿。两个真环境脚本在测试机上跑过，各带一次「用改之前的版本应该红」的对照。正式站升级见文末。

## 逐条结果

1. **C4（字体原文件谁都能下载）**：`deploy/Caddyfile` 在带哈希的字体样式表和分片之后、`handle /media/*` 之前加 `handle /media/fonts/*` → `respond 404`。后台下载原文件走 Django（`core/fonts/admin_views.py` 的 `FileResponse`），不受影响。正式站 10-07 核对：`/app/media/fonts/` 下只有 `css/`，没有上传过字体，没有已经泄露的文件。测试 `test_uploaded_font_originals_are_not_served` 读 Caddyfile：这块只回 404、位置在两者之间，并拿分片的正则实际匹配几条地址（`original/` 下的 `.woff2`、`.otf` 不算公开）。
2. **C5（下线内容不是立即删）**：`core.prerender.request_removal` 改为提交后由当前进程直接 `drop`（以前是排 `remove_prerendered` 任务给 worker）。删除出错时 `logger.exception`、记录标成「生成失败」写 `REMOVAL_FAILED`（超管在后台待办「N 个静态页面生成失败」里看到，设计 13.13.5「通知超级管理员」就靠它）、再排一个 `remove_prerendered` 任务重删，删成功后记录随 `drop` 消失。测试：撤回发布的文章在提交后文件和记录都不在、**任务表里没有留给 worker 的任务**；`remove_page` 抛错时记录是失败、日志有那一行、排了 1 个任务。原来的 `test_unpublishing_deletes_the_static_file` 是手动调 `drop`，从没走过信号到删除这条路，所以 C5 一直没被测到。
3. **C6（预渲染页和静态文件没有 HSTS）**：新 snippet `(transport_security)` 只放一行 `Strict-Transport-Security`，`(page_security)`（预渲染页）、`@hashed_static`、`/static/*`、`@hashed_fonts`、`/media/images/*`、`/media/*` 都 import；交给 Django 的路由不加（Django 自己发）。测试 `test_what_caddy_serves_itself_carries_django_s_hsts` 从 `settings/prod.py` 读三个 `SECURE_HSTS_*`，经 Django 自己的 `SecurityMiddleware` 生成期望值，和 Caddyfile 一字不差；六个地方都 import；`(django)` 不 import；整份只出现一次。
4. **C9（`/healthz` 返回全部细节）**：`core/views.py` 的 `healthz` 对非超管只给 `{"status", "checks": {名字: {"ok": 布尔}}}`；超管看完整细节。判断超管时读数据库出错就当不是（数据库坏了时探针照样 503，不能变成 500）。状态码规则不变。原来四条读 `detail` 的测试改成用超管登录；新增三条：匿名请求在心跳过期时 503、`checks` 恰好是四个 `{"ok": …}`、正文里没有「心跳过期」和磁盘数字；**能进后台但不是超管的人**（`is_staff`）看不到细节；超管看得到。
5. **F1（状态片段失败时整页灰块）**：`static/js/state.js` 把去骨架写成 `done()`，`htmx.ajax(...).then(done, done)`（网络错误时 reject 也去）；`start()` 先挂 `setTimeout(done, 8000)`（HTMX 没加载上、请求一直不回）；加 `asked` 防止 `htmx:load` 和 300 毫秒的兜底各发一次请求。请求晚到照样 OOB 换进去（按代码判断，浏览器里未验证）。字符串守卫 `test_the_skeleton_goes_even_when_the_state_request_fails`；行为由浏览器探针验证（下面）。
6. **设计 v7.18**：13.4 路由表 `/healthz` 一行、13.13.3 加「片段请求没成功时也一样」、13.13.5 加「谁来删」、15.2 传输和字体文件两行、16.6 加「对外只给状态」，附录 D 记一行；文档头版本从 v7.14 改到 v7.18（212–214 改了附录没改文档头）。
7. **文档**：README「健康检查」写明对外和超管的区别、服务器上怎么看细节；AGENTS.md 加两条：`htmx.ajax()` 的 Promise 只在网络错误时 reject 的坑；用户 10-07 要求的「所有测试和检查都放到后台跑，别让对话卡住」。

## 验收输出

### 整组检查（测试机，`bash scripts/remote-check.sh`）

```
== ruff (18:10:54)
All checks passed!
== Tailwind (18:10:54)
== pytest (18:10:56)
分片 1：492 passed in 63.46s (0:01:03)
分片 2：492 passed in 72.23s (0:01:12)
分片 3：492 passed in 67.29s (0:01:07)
分片 4：491 passed in 65.95s (0:01:05)
== 迁移 (18:12:14)
No changes detected
== 生产配置 (18:12:15)
System check identified no issues (0 silenced).
== 错误页和模板一致 (18:12:17)
== Docker 镜像 (18:12:18)
构建成功：66e990927ec0
== 全部通过 (18:12:18)
```

### 变异（测试机，`remote-check.sh run uv run python handoff/rounds/215-caddy-and-prerender/mutate.py`，退出码 0）

```
基线全绿，开始变异。
ok C4: 字体原文件又交给 file_server：改坏后红了（1 条）
ok C4: 分片的正则放宽，original/ 下的 woff2 也算公开：改坏后红了（1 条）
ok C6: HSTS 值和 Django 不一样（少了 preload）：改坏后红了（1 条）
ok C6: 预渲染页不带 HSTS：改坏后红了（1 条）
ok C6: 不带哈希的静态文件不带 HSTS：改坏后红了（1 条）
ok C6: Django 那条路也加 HSTS（叠两份）：改坏后红了（1 条）
ok C5: 下线又排给 worker：改坏后红了（1 条）
ok C5: 删除失败不标记：改坏后红了（1 条）
ok C5: 删除失败不交给 worker：改坏后红了（1 条）
ok C9: 对外照旧给细节：改坏后红了（2 条）
ok C9: 能进后台的都看细节：改坏后红了（1 条）
ok C9: 超管也看不到细节：改坏后红了（1 条）
ok F1: 网络错误时不去骨架：改坏后红了（1 条）
ok F1: 没有 8 秒兜底：改坏后红了（1 条）
改回后基线全绿。
```

### 真 Caddy（`caddy_probe.py`，测试机）

测试读的是 Caddyfile 的文字；Caddy 实际怎么排 `handle` 的先后、snippet 里再 import snippet 行不行，只有 Caddy 说了算。脚本起 `caddy:2.10-alpine`，挂载和 `deploy/docker-compose.yml` 一样，后面接一个假的 Django（另一个 Caddy，回自己的 HSTS 值）。这一轮的 Caddyfile：

```
ok   C4 原文件 /media/fonts/3/original/Secret-Bold.otf 是 404  [404]
ok      且没有给出文件内容  [0]
ok   C4 原文件 /media/fonts/3/original/Secret-Bold.woff2 是 404  [404]
ok      且没有给出文件内容  [0]
ok   / 是 200  [200]
ok      缓存头照旧（public, max-age=0, must-revalidate）  [public, max-age=0, must-revalidate]
ok      C6 带 HSTS，值和 Django 一样  [['max-age=31536000; includeSubDomains; preload']]
ok   /static/css/app.0123456789ab.css 是 200  [200]
ok      缓存头照旧（public, max-age=31536000, immutable）  [public, max-age=31536000, immutable]
ok      C6 带 HSTS，值和 Django 一样  [['max-age=31536000; includeSubDomains; preload']]
ok   /static/js/plain.js 是 200  [200]
ok      缓存头照旧（public, max-age=300, must-revalidate）  [public, max-age=300, must-revalidate]
ok      C6 带 HSTS，值和 Django 一样  [['max-age=31536000; includeSubDomains; preload']]
ok   /media/fonts/css/fonts.0123456789ab.css 是 200  [200]
ok      缓存头照旧（immutable）  [public, max-age=31536000, immutable]
ok      C6 带 HSTS，值和 Django 一样  [['max-age=31536000; includeSubDomains; preload']]
ok   /media/fonts/3/latin.0123456789ab.woff2 是 200  [200]
ok      缓存头照旧（immutable）  [public, max-age=31536000, immutable]
ok      C6 带 HSTS，值和 Django 一样  [['max-age=31536000; includeSubDomains; preload']]
ok   /media/images/face.fill-96x96.jpg 是 200  [200]
ok      缓存头照旧（immutable）  [public, max-age=31536000, immutable]
ok      C6 带 HSTS，值和 Django 一样  [['max-age=31536000; includeSubDomains; preload']]
ok   /media/original_images/face.jpg 是 200  [200]
ok      缓存头照旧（public, max-age=86400）  [public, max-age=86400]
ok      C6 带 HSTS，值和 Django 一样  [['max-age=31536000; includeSubDomains; preload']]
ok   预渲染首页仍带 CSP  [200]
ok   /accounts/login/ 交给 Django  [django answered]
ok      HSTS 只有 Django 自己那一个，没叠一份  [['from-the-stand-in-django']]
ok   /?q=1 交给 Django  [django answered]
ok      HSTS 只有 Django 自己那一个，没叠一份  [['from-the-stand-in-django']]
ok   /healthz 交给 Django  [django answered]
ok      HSTS 只有 Django 自己那一个，没叠一份  [['from-the-stand-in-django']]

32 项通过，0 项失败
```

对照：`--caddyfile handoff/rounds/215-caddy-and-prerender/Caddyfile.before-215`（改之前那份，`git show HEAD:deploy/Caddyfile`）。失败的行：

```
FAIL C4 原文件 /media/fonts/3/original/Secret-Bold.otf 是 404  [200]
FAIL    且没有给出文件内容  [17]
FAIL C4 原文件 /media/fonts/3/original/Secret-Bold.woff2 是 404  [200]
FAIL    且没有给出文件内容  [17]
FAIL    C6 带 HSTS，值和 Django 一样  [[]]
（同上一行，共 7 处）

21 项通过，11 项失败
```

### 浏览器（`f1_probe.py`，测试机无头 Chromium）

真的预渲染首页（`render_html('/')`，带 `data-state-filled="0"`），设 `ow_logged_in=1`，脚本里的小服务器代替 Caddy，每种情况弄坏一样。骨架出现和消失的时刻由页面自己用 MutationObserver 记（第一次从外面轮询，失败的三种在 0.1 秒内就结束，轮询看到的是「没看到骨架」，改了探针重跑）。这一轮的 `state.js`：

```
ok   ok       骨架0.1 秒后去掉（要求 0–3 秒），占位区内容 visible
ok   429      骨架0.1 秒后去掉（要求 0–3 秒），占位区内容 visible
ok   500      骨架0.1 秒后去掉（要求 0–3 秒），占位区内容 visible
ok   drop     骨架0.1 秒后去掉（要求 0–3 秒），占位区内容 visible
ok   hang     骨架8.1 秒后去掉（要求 7–10 秒），占位区内容 visible
ok   no-htmx  骨架8.1 秒后去掉（要求 7–10 秒），占位区内容 visible

6 种情况通过，0 种失败
```

对照：`--old-script`（`state.before-215.js`）：

```
ok   ok       骨架0.2 秒后去掉（要求 0–3 秒），占位区内容 visible
ok   429      骨架0.1 秒后去掉（要求 0–3 秒），占位区内容 visible
ok   500      骨架0.1 秒后去掉（要求 0–3 秒），占位区内容 visible
FAIL drop     骨架一直没去掉（要求 0–3 秒），占位区内容 hidden
FAIL hang     骨架一直没去掉（要求 7–10 秒），占位区内容 hidden
FAIL no-htmx  骨架一直没去掉（要求 7–10 秒），占位区内容 hidden

3 种情况通过，3 种失败
对照：符合预期
```

旧脚本在 429、500 时也能去掉骨架：htmx 对错误状态码照样 resolve（只是不换内容）。210 复核里「429/5xx 时 resolve 但不换片段」说的就是这个，真正卡住的是断网、请求不回、HTMX 没加载这三种。对照的期望（恰好这三种失败）是跑之前写进脚本的。

### 浏览器旅程

改了 `state.js`（每个预渲染页都加载），跑了新人旅程和全站地址：

```
=== journey（remote-check.sh run uv run python scripts/journey.py）
ok  首页「我的安排」里有这场内战
ok  浏览器没有报错
全部走通
exit=0
=== pages（remote-check.sh run uv run python scripts/journey.py pages）
看了 174 个地址，0 处有问题
全部走通
exit=0
```

顺带：测试机上有一批没人管的进程（父进程已退出），一组是一天前的开发服务器、worker 和 Chromium，另外几个是 214 演练留下的 worker 和 `/tmp/drill214.sh`。它们是以前的脚本没收干净留下的，这次逐个 `kill -TERM` 清掉了，正在跑的 `pages` 那组没碰。

## 正式站升级（2026-10-07 02:25 北京时间，补记）

先核对服务器上要被覆盖的 9 个文件和 214 一致，`backup`（`sjtu-ow-20261007-022425.tar.gz`，210.8 MB），再 `deploy_ship.sh 215`：镜像重建、无迁移、`prerender` 全量成功 12 失败 0、healthz ok。`Caddyfile.vps` 按新的仓库 Caddyfile 重新生成：在 `admin off` 下面插回原来那 10 行 `servers` 块，`diff` 只有这一块，`caddy validate` 显示 `Valid configuration`，重启 `proxy`。改前的 `Caddyfile.vps` 留在服务器 `/root/sjtu-ow-backups/Caddyfile.vps.before-215`。

第一次升级只做到备份就停了：脚本是 `ssh 服务器 'bash -s' < 脚本` 传进去的，`docker compose exec -T` 把标准输入里剩下的脚本读掉了，后面一条都没执行，退出码还是 0。从外面核对时 `/healthz` 还带细节，才发现没升上去。改成先 `scp` 脚本、再 `bash 脚本 < /dev/null`，重跑（跳过重复备份）。这个坑写进了 AGENTS.md。

从本机经域名核对（`https://sjtu.ow-shanghaiuniversity.com`）：

```
== 首页（预渲染）
HTTP/2 200
content-security-policy: default-src 'self'; script-src 'self' 'inline-speculation-rules';
strict-transport-security: max-age=31536000; includeSubDomains; preload
== 静态文件
/static/js/state.90d336d43e97.js
HTTP/2 200
cache-control: public, max-age=31536000, immutable
strict-transport-security: max-age=31536000; includeSubDomains; preload
== 登录页（Django）
HSTS 头的条数：1
== 字体原文件地址
404
== 字体样式表
/media/fonts/css/fonts.f42c1154633c.css
200
== healthz
{"status": "ok", "checks": {"database": {"ok": true}, "disk": {"ok": true}, "worker_heartbeat": {"ok": true}, "task_backlog": {"ok": true}}}  HTTP 200
== 首页引用的 state.js 里有 8 秒兜底
2
```

用户的反向代理把 Caddy 加的 HSTS 原样带出来了，Django 那条路上也只有一份。字体原文件那一行在正式站上说明不了什么：正式站没上传过字体，这个地址改之前也是 404。真正证明拦得住的是测试机上的 Caddy 探针。

## 设计偏差

无。五条都是按已有设计补齐实现；设计里补写的是「怎么做到」（谁来删、失败时怎么显示、对外给什么），不改变已有规则。

## 未完成 / 顺带发现 / 需要确认

- 210 复核里还有 50 多条低严重度的，和 A2（内容编辑能看邮箱）、A12（停用账号的头像）、T7（取消后还能审核）、B11（群发不限次）四处设计空白，等用户拍板。
- 正式站前面是用户自己的反向代理（`anylocate.cc`）。它会不会自己再加一份 HSTS、会不会把 Caddy 的这一份去掉，在升级后从外面 `curl` 看结果（见下）。
- HSTS 带 `includeSubDomains; preload`，是 Django 原来就发的值，Caddy 只是照抄。`sjtu.ow-shanghaiuniversity.com` 是子域名，`includeSubDomains` 只管它下面的子域名，不影响 `ow-shanghaiuniversity.com` 本身和它的其他子域名。`preload` 对子域名无效（浏览器的预加载名单只收主域名），保留它只是为了和 Django 一致。

## 改动文件

- `deploy/Caddyfile`：`(transport_security)`、各文件路由 import、`/media/fonts/*` 404
- `core/prerender.py`：`request_removal` 当场删，`_remove_now`、`REMOVAL_FAILED`
- `core/views.py`：`healthz` 对外只给状态、`_sees_health_details`
- `static/js/state.js`：`done()`、`.then(done, done)`、8 秒兜底、只请求一次
- 测试：`core/tests/test_latency.py`（C4、C6）、`core/tests/test_prerender.py`（C5、F1）、`core/tests/test_pages.py`（C9）
- 文档：`docs/design.md`（v7.18）、`README.md`、`AGENTS.md`
- 本轮目录：`request.md`、`report.md`、`review.md`、`mutate.py`、`caddy_probe.py`、`f1_probe.py`、`Caddyfile.before-215`、`state.before-215.js`（两份对照用的旧文件）
