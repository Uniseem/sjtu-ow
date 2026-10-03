# 105 缓存与高延迟

## 背景

用户 2026-10-03：

> 然后站点似乎没有做好缓存，对延迟稍高的时候不友好。

在演示站上实测（`curl` 看响应头，内置浏览器看 `performance` 里每个资源的 `transferSize`）：

- **上传的图片没有缓存头**：`/media/images/…`（头像、封面的缩略图）没有 `Cache-Control`，设计 13.10 写的「缩略图一年不可变缓存」没有落到 Caddyfile 里，只有字体文件有。一页几十张头像，回访时浏览器要逐张确认
- **206**：Caddy 2.10.2 的 `file_server { precompressed }` 返回预压缩文件时，状态码是 `206 Partial Content`，带 `Content-Range: bytes 0-N/N`（浏览器并没有要范围）。在服务器上用同一个镜像起临时容器对比：只开 `precompressed` 是 206，只开 `encode` 是 200。Chromium 照样缓存了这些响应，但这是错误的响应，别的浏览器和用户前面的线路优化服务、反向代理不一定缓存
- **每次点开新页都要等一个来回**：预渲染页是 `max-age=0, must-revalidate`，保证改了马上看得到，代价是每次点击都要去服务器确认一次；延迟高时这一下最明显
- **预渲染页没有安全响应头**（104 发现）：Caddy 直接返回的预渲染页没有内容安全策略、`X-Frame-Options`、`nosniff`、`Referrer-Policy`，同一页走 Django 时都有
- **演示站 canonical 是 `localhost:8000`**（104 发现）：102 恢复后漏跑 `init_site`

## 本轮范围

**做**（先改设计 13.10、13.13、15.2，记 v6.3）：

1. Caddy：去掉 `precompressed`，用 `encode zstd gzip` 动态压缩（预压缩文件照常生成，换到修好的 Caddy 再用）；`/media/images/` 一年不可变缓存，其他上传文件缓存一天
2. **提前准备下一页**：页面里放一段 Speculation Rules，鼠标在站内链接上停一下、或手指按下时，浏览器在后台把目标页准备好，点下去基本是瞬开，内容仍然是最新的。只对公开页面，后台、登录注册、个人中心、片段地址除外。内容安全策略加 `'inline-speculation-rules'`（只允许这种 JSON，不允许脚本）。不支持的浏览器（Safari、Firefox）照常加载
3. 被提前准备的页面等真正显示时才去取登录状态和提示消息（`state.js`），免得状态过期、提示被没看到的页面吞掉
4. 预渲染页由 Caddy 加上和 Django 一样的安全响应头，测试保证 Caddyfile 里的内容安全策略和 Django 的一字不差
5. 演示站：拉代码、重建、更新本机专用的 `Caddyfile.vps`、跑 `init_site`、全量生成，实测响应头

**不做**：给预渲染页加 `max-age`（会让刚改的内容最多晚几十秒才看到；第 2 条在不牺牲新鲜度的前提下解决点击等待）；Service Worker。

## 验证

测试：Caddyfile 的规则（不用 `precompressed`、缩略图不可变、预渲染页带安全头且内容安全策略和 Django 一致）；页面里的 Speculation Rules 是合法 JSON、排除的地址都在、没有别的内联脚本；`state.js` 等页面显示。变异逐条改坏。服务器上实测响应头和缓存；浏览器里实测提前准备是否生效。

## 验收标准

`AGENTS.md`「常用命令」那组全绿；变异全部被抓到；推送 `main`，CI 绿；演示站响应头符合设计。
