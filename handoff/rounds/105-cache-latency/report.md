# 105 缓存与高延迟（报告）

## 先测了什么

在演示站上看每类资源的响应头，在内置浏览器里看第二次打开时资源是不是走了缓存：

```
== /static/css/app.4fcecfd50e6a.css
HTTP/1.1 206 Partial Content
Cache-Control: public, max-age=31536000, immutable
Content-Encoding: br
...
== /media/images/anime-1.4883b0d3.fill-88x88.png
HTTP/1.1 200 OK
Content-Length: 14635
Etag: "dluof3zpszmnbaj"
```

浏览器带 `Accept-Encoding` 时静态文件、预渲染页都是 206（`Content-Range: bytes 0-14212/14213`），不带时是 200。在服务器上用同一个 Caddy 镜像起临时容器对比三种配置：

```
8081 encode+precompressed=both:   HTTP/1.1 206 Partial Content
8082 encode+precompressed=precompressed-only:   HTTP/1.1 206 Partial Content
8083 encode+precompressed=encode-only:   HTTP/1.1 200 OK
```

条件请求照常 304。内置浏览器（Chromium 152）第二次打开时 `app.css`、脚本的 `transferSize` 都是 0，说明 Chromium 照样缓存了这些 206；图片没有缓存头，每次回访要逐张确认；预渲染页 `max-age=0, must-revalidate`，每次点击都要等一个来回。另外发现预渲染页没有任何安全响应头、演示站 canonical 是 `http://localhost:8000/`（104 报告里已记）。

## 做了什么

1. **设计 v6.3**：13.10 加「压缩」「提前准备下一页」两条、上传文件缓存写清楚；13.13.2 第 3 步和「安全响应头」；13.13.3 被提前准备的页面显示时才取状态；15.2 内容安全策略一行；12.x 技术选型表里预压缩的说明；附录 D
2. **`deploy/Caddyfile`**：
   - `encode zstd gzip`，三处 `file_server { precompressed br gzip }` 改成 `file_server`（预压缩文件照常生成，暂时不用）
   - `/media/images/*` 一年不可变，其余 `/media/*` 一天
   - 新片段 `(page_security)`：和 Django 一样的内容安全策略、`X-Frame-Options: DENY`、`X-Content-Type-Options: nosniff`、`Referrer-Policy: same-origin`、`Cross-Origin-Opener-Policy: same-origin`，预渲染页 `import page_security`
3. **内容安全策略**（`settings/base.py`）：`script-src` 加 `'inline-speculation-rules'`
4. **提前准备下一页**：新模板 `templates/components/speculation_rules.html`，`base.html` 的 `<head>` 引入。规则：站内地址、`moderate`（停 200ms 或按下）、排除 `/admin/`、`/accounts/`、`/me/`、`/_fragments/`、`/_styleguide/` 和带 `download`、`target`、`data-no-prerender` 的链接
5. **`static/js/state.js`**：`document.prerendering` 为真时等 `prerenderingchange` 再取状态
6. **测试**：新文件 `core/tests/test_latency.py`（6 条）；`test_chapter15_audit.py` 两条按新规则改：`script-src` 只能是 `'self'` 和 `'inline-speculation-rules'`，页面里除了 `type="speculationrules"` 不能有内联脚本
7. **文档**：README「生产 / 测试环境启动」加改 Caddyfile 要 `restart proxy`、「半静态渲染」加响应头和提前准备两条；`AGENTS.md`「第二台」加 `Caddyfile.vps` 怎么重新生成、「已知的坑」加 CRLF 一条
8. **演示站**：拉取 104、传上 105 的文件、重新生成 `Caddyfile.vps`、重建、`restart proxy`、`init_site`（canonical）、全量生成

## 命令输出

变异（`handoff/rounds/105-cache-latency/mutate.py`，13 处）：

```
baseline green, 7 tests
caught Caddy's policy drifts from Django's -> test_prerendered_pages_carry_the_same_policy_as_django
caught prerendered pages lose the security headers -> test_prerendered_pages_carry_the_same_policy_as_django
caught prerendered pages may be framed -> test_prerendered_pages_carry_the_same_policy_as_django
caught precompressed comes back -> test_caddy_does_not_serve_precompressed_files
caught thumbnails lose their year -> test_thumbnails_are_kept_a_year_and_other_uploads_a_day
caught other uploads lose their day -> test_thumbnails_are_kept_a_year_and_other_uploads_a_day
caught the policy forbids speculation rules -> test_the_front_end_csp_forbids_inline_script_and_eval
caught the policy forbids speculation rules -> test_prerendered_pages_carry_the_same_policy_as_django
caught pages carry no rules -> test_pages_ask_the_browser_to_prepare_public_links
caught pages carry no rules -> test_prerendered_files_carry_the_rules_too
caught the personal pages are prepared too -> test_pages_ask_the_browser_to_prepare_public_links
caught the sign-in pages are prepared too -> test_pages_ask_the_browser_to_prepare_public_links
caught downloads are prepared -> test_pages_ask_the_browser_to_prepare_public_links
caught everything is prepared at once -> test_pages_ask_the_browser_to_prepare_public_links
caught a prepared page asks before it is shown -> test_a_prepared_page_waits_to_be_shown_before_asking_who_is_signed_in
restored and green; missed: none
```

新 Caddyfile 用服务器上的 Caddy 镜像验证：

```
Valid configuration
```

**提前准备是否生效**。内置浏览器（嵌在桌面应用里）连 `eagerness: immediate` 都不触发，`activationStart` 一直是 0，它把预加载关掉了，测不了。改用本机 Edge 无头模式，通过调试端口打开 `Preload` 事件，鼠标停在第一篇文章的链接上 1.5 秒再点击（节选，`spec_probe.py` 在临时目录）：

```
link {'x': 112, 'y': 401.796875, 'href': 'http://localhost:8000/news/october-schedule/', 'rules': True}
  Preload.preloadEnabledStateUpdated {"disabledByPreference": false, "disabledByDataSaver": false, "disabledByBatterySaver": false, ...}
  Preload.ruleSetUpdated {"ruleSet": {"sourceText": "\n{\"prerender\": [{\"where\": ...
after hover:
  Preload.prerenderStatusUpdated {... "url": "http://localhost:8000/news/october-schedule/"}, ... "status": "Failure", "prerenderStatus": "PrerenderingDisabledByDevTools"}
  Preload.prefetchStatusUpdated {... "status": "Ready", "prefetchStatus": "PrefetchSuccessfulButNotUsed", ...
after click {'url': '/news/october-schedule/', 'activationStart': 0, 'responseStart': 21, 'type': 'navigate'}
  Preload.prefetchStatusUpdated {... "status": "Success", "prefetchStatus": "PrefetchResponseUsed", ...
```

规则集没有解析错误，页面上的站内链接都成了候选；停留后浏览器对这一个链接发起了准备。完整的预渲染被拒是因为页面正被调试工具控制（`PrerenderingDisabledByDevTools`），一起发起的预取成功、点击时用上了（`PrefetchResponseUsed`）。

整组检查（开发服务器停着）：

```
All checks passed!
270 files already formatted
No changes detected
System check identified no issues (0 silenced).
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
1241 passed in 203.45s (0:03:23)
```

演示站部署。第一次 `build -q` 什么都没构建也没报错（之后 `docker images` 显示镜像还是 38 分钟前的），去掉 `-q` 重跑才构建。`Caddyfile.vps` 第一次也没生成对：从 Windows 打包的文件是 CRLF，`awk` 匹配 `admin off$` 失败，`trusted_proxies` 没插进去（`grep -c trusted_proxies` 是 0）；转成 LF 后重新生成：

```
2a3,7
> 	# A reverse proxy on this machine (or in a container) forwards here;
> 	# keep its X-Forwarded-Proto so Django knows the visitor used https.
> 	servers {
> 		trusted_proxies static private_ranges
> 	}
Valid configuration
```

```
 Container sjtu-ow-worker-1 Started 
proxy Up 2 minutes
web Up 20 seconds (healthy)
worker Up 20 seconds
1
全量生成完成：成功 46，失败 0，删除 0；目录占用 1582 KB
```

从外部看：

```
== /news/ (prerendered)
HTTP/1.1 200 OK
Cache-Control: public, max-age=0, must-revalidate
Content-Encoding: zstd
Content-Security-Policy: default-src 'self'; script-src 'self' 'inline-speculation-rules'; style-src 'self'; img-src 'self' data:; font-src 
Cross-Origin-Opener-Policy: same-origin
Referrer-Policy: same-origin
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
== css
HTTP/1.1 200 OK
Cache-Control: public, max-age=31536000, immutable
Content-Encoding: zstd
== /media/images/anime-1.4883b0d3.fill-176x176.png
HTTP/1.1 200 OK
Cache-Control: public, max-age=31536000, immutable
== canonical
<link rel="canonical" href="http://169.58.217.180:22887/news/">
== rules
1
```

```
etag "dlus5zwd4k1ukd7-zstd"
HTTP/1.1 304 Not Modified
HTTP/1.1 200 OK
Content-Encoding: gzip
```

（条件请求照常 304；只支持 gzip 的浏览器拿到 gzip。）

## 发现的问题（不在本轮修）

- 测试机 185.99.135.224 的 Caddy 也是 206 和缺安全头，等那台升级（STATUS 里原有的事项）
- 预渲染的 `.br`、`.gz` 现在没人用，每次生成白写两个文件；等确认要不要换 Caddy 版本再决定删不删

## 未验证

- 真实浏览器（不被调试工具控制）里完整的预渲染瞬开：无头 Edge 因为调试工具在控制页面拒绝了预渲染，只验证到预取被用上
- 用户自己的反向代理和线路优化服务会不会改写这些响应头、会不会缓存
