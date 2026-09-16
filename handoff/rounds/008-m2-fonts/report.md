# 008 实现报告

> 本轮由**用户指定 Claude 实现**（"这一块你来做"），不是 Grok。因此复核由 Grok 做：请读本报告和 `request.md` 末尾的「复核清单」，自己跑命令验证，不要采信这里的结论，结果写进 `review.md`。

## 结论

T0–T5 已完成：字体库（上传 / Google Fonts / 网址三条路径、授权与 `fsType` 检查、预览、下载、重新处理、删除保护），worker 切片成带 `unicode-range` 的 WOFF2 分片，9 个排版区域 + 实时预览 + 生成 `fonts.<哈希>.css`，性能约束与后台菜单。新增依赖 `fonttools`、`brotli`（设计 2.2 节已列，属于计划内）。

实测：思源黑体 CN（8.4MB、30926 字）切成 66 片、5.9MB，单个字重耗时约 40 秒；一篇短文章页下载 21 个分片、808,352 字节。

## 逐条结果

### T0 顺带提交

`docs/design.md` 的 v1.5.4 改动随本轮一起提交，并在本轮继续改到 **v1.5.5**（见文末「设计偏差」和附录 D）。

### T1 字体库

- `FontFamily` / `FontFace` 按 12.4.3、12.4.4 建表；`FontFamily` 多了一个 `license_confirmed` 字段，把「确认允许嵌入」的勾选留档（设计已补）。
- 三条添加路径都做了，表单在 `/admin/settings/fonts/add/` 一页三块：
  - **上传**：TTF / OTF / WOFF / WOFF2，>30MB 直接拒；字重和样式可以选「自动识别」，从 `OS/2.usWeightClass` 和 `fsSelection` / `head.macStyle` 读。
  - **Google Fonts**：请求 `css2?family=<名字>:wght@...`（带桌面浏览器 UA 才会返回 woff2 + `unicode-range`），解析全部 `@font-face`，把分片下载到本站，`status` 直接是 `ready`。
  - **网址下载**：只允许 https；解析域名后逐个检查 IP，私有 / 回环 / 链路本地 / 保留 / 组播一律拒；跟随跳转时**每一跳都重新检查**；限制 30MB（先看 `Content-Length`，再按字节数兜底）。
- 授权：类型必选 + 必须勾选确认；Google 来源自动记开源；`fsType` 第 1 位（禁止嵌入）或第 9 位（仅点阵）直接拒绝，错误在表单上显示。
- 操作：列表页和详情页用示例文字预览（附录 C 那句），下载（上传/网址来源给原始文件，Google 来源打包分片 zip），状态含进度、分片数、总大小、字符数、失败原因，重新处理，删除（被引用时拒绝）。

### T2 字体处理

- `core/fonts/processing.py`：fontTools 解析 → 校验 → `getBestCmap()` 取字符集 → 逐片 `Subsetter` → WOFF2。
- 切片（`core/fonts/slicing.py`）：拉丁 / 数字 / 标点 / 全角一组（每 600 字一片）；常用汉字每 200 字一片；其余汉字和其他字符每 600 字一片。
- **「常用」怎么判定**：仓库里没有汉字使用频率表，我也不会凭记忆编一份。用 Python 自带的 `gb2312` 编解码器判断是不是 GB 2312 一级汉字（3755 字，首字节 0xB0–0xD7），这是真实可计算的数据；片内按码位排序。**代价见下面「设计偏差 3」**。
- 分片名 `<字重>[i]-<序号>.<内容哈希>.woff2`，放 `media/fonts/<字体 ID>/`；重新处理时内容没变就复用同名文件，变了才写新文件并删旧的。
- Google 来源不重新切片；分片按内容哈希命名，Google 对 400 / 700 返回同一个可变字体文件时只存一份（实测 202 个请求 → 101 个文件、5.9MB，去重前是 202 个文件、11.7MB）。
- 队列同一时间只处理一个字重：任务开始前检查有没有别的 `processing`，有就 30 秒后重新入队（最多约 1 小时）；超过 30 分钟没更新进度的视为中断，不再阻塞。
- 进度写在 `FontFace.progress`，后台每次刷新能看到；失败原因写 `error` 并显示。

### T3 排版设置

- `TypographyRule` 九条由 `init_site` 建，后台只能改。正文不能选「跟随正文」（模型 `clean()` + 表单）。
- 字体下拉只列「有处理完成字重」的字体；选「字体库中的字体」时字重必须是该字体已处理完成的（模型校验）。
- 后备字体：正文类接 `var(--font-fallback)`（苹方 / 微软雅黑 / 思源黑体 / sans-serif），代码区接 `var(--font-mono-fallback)`。
- 实时预览：预览块里有导航、一级 / 二级 / 三级 / 四级标题、正文段落、分队结果（等宽）、数字、按钮。`static/js/typography-preview.js` 监听表单，把 `--font-*` 写到预览块的行内样式上；同时把字重下拉里该字体没有的字重隐藏。`/admin/settings/fonts/faces.css` 提供全部已处理字体的 `@font-face`，所以预览用的是真字体。
- 保存后生成 `media/fonts/css/fonts.<12 位哈希>.css`，`SiteSettings.font_css_path` / `font_css_generated_at` 记录；`templates/base.html` 在 `{% tailwind_css %}` 之后引用它（`core.context_processors.fonts`）。旧样式表保留一天再清。
- **没有改模板里的字体类名**：`.font-nav` / `.font-button` / `.font-numeric` / `.font-code` 都还在，`assets/css/input.css` 只增加了默认变量、行高 / 字间距、手机端标题 85% 和 `.font-numeric` 的等宽数字。

### T4 性能约束

- 「字体 × 字重」超过 6 组时保存后给警告（只统计**真的会被下载**的组合：区域要的字重没有对应文件时浏览器不会下载，不计入）。
- 每个区域下面显示它用的字重有多少分片、合计多大（「跟随正文」的区域按正文字体算）。
- CSP 没动：`font-src` 仍是 `'self'`，前台没有任何第三方字体域名。

### T5 后台

「设置」菜单下新增「字体库」和「排版设置」，`SuperuserMenuItem` 只对超级管理员显示；视图里另外再判断一次 `is_superuser`，非超级管理员直接 `PermissionDenied`（Wagtail 会转成跳回 `/admin/`）。

## 验收输出

### 1. ruff / pytest / makemigrations / check --deploy

```
$ uv run ruff check . && uv run ruff format --check .
All checks passed!
145 files already formatted
```

```
$ uv run python -m pytest -q
148 passed in 9.61s
```

```
$ uv run python manage.py makemigrations --check --dry-run
No changes detected
```

```
$ DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod DJANGO_SECRET_KEY=... FIELD_ENCRYPTION_KEY=... \
  DJANGO_ALLOWED_HOSTS=example.com DJANGO_CSRF_TRUSTED_ORIGINS=https://example.com \
  SITE_URL=https://example.com DJANGO_SECURE_SSL_REDIRECT=true uv run python manage.py check --deploy
System check identified no issues (0 silenced).
```

本轮新增测试 26 个（`core/tests/test_fonts.py`，含用 fontTools 现场造的真字体 `core/tests/fonts_factory.py`）：切片分组和 `unicode-range` 合并、`fsType` 拒绝、上传表单拒绝、真实切片落盘（文件头是 `wOF2`）、失败状态、同一时间只处理一个、重新处理、默认样式表、自定义区域的变量和 `@font-face`、「跟随正文」按正文字体取字重、缺字重只警告、正文不能「跟随正文」、字重必须存在、6 组警告、删除保护、删除清文件、内网地址被拒、Google CSS 解析与域名校验、后台超级管理员限制、上传流程、排版表单保存并生成样式表、前台引用样式表。

### 2. 添加中文字体（用的是哪条路径）

**上传路径**。字体：Source Han Sans CN Regular / Bold（思源黑体，SIL OFL 1.1），从 Adobe 的 GitHub 发布地址 `curl` 到本地后通过后台「上传字体文件」提交。

> 「从网址下载」在本机走不通：本机 DNS 把所有外网域名解析到 `198.18.0.0/15`（VPN 的 fake-ip 段），SSRF 检查按设计判定为内网地址并拒绝，后台提示「下载地址指向内网地址，已拒绝。」。这是**开发环境的网络形态**，不是代码问题；海外服务器上是真实公网 IP，不会触发。为了仍然验证下载逻辑本身，另外跑了一次只跳过地址检查的一次性脚本（见第 2b 条）。

```
family 2 思源黑体 CN sjtu-font-1 upload open_source True 字体验收
  face 1 400 normal processing 30926 file: fonts/2/original/SourceHanSansCN-Regular.otf

   0.0s  processing 36%
  ...
  40.0s  ready 100%  slices=66 bytes=7306612
```

| 字重 | 分片 | 总大小 | 字符数 | 耗时 |
|---|---|---|---|---|
| 400 | 66 | 5.86 MB（丢 hinting 后；之前 7.13 MB） | 30926 | 约 40 秒 |
| 700 | 66 | 5.87 MB | 30926 | 约 40 秒（排在 400 后面跑） |

Bold 是在详情页「添加字重」上传的，字重选「自动识别」，系统从文件里读出 700。

分片示例：

```
fonts/2/400-000.4bccd32e.woff2  43664 字节  600 字  U+0020-007E, U+00A0-0103, ...
fonts/2/400-002.54b2de66.woff2  28816 字节  200 字  U+4E00-4E01, U+4E03, U+4E07-4E0B, ...
fonts/2/400-065.89b7b53c.woff2   2952 字节          U+1F242-1F248, U+1F250-1F251
```

**2b. Google Fonts 路径**：在跳过地址检查的一次性脚本里真实跑通了（网络确实通）：

```
CSS bytes: 225452
faces parsed: 202 weights: [400, 700]
face 400 ready 101 slices, 5886 KB
face 700 ready 101 slices, 5886 KB
files on disk: 101 size: 5886 KB      # 两个字重共用同一批文件
```

后台表单那一步（填字体名 → 勾字重 → 提交）在本机**没跑通**，原因同上（表单里的请求也过 SSRF 检查）。

### 3. 生成的样式表片段

正文设为思源黑体 CN 400、一级标题「跟随正文」700 时（`/media/fonts/css/fonts.faad43d71790.css` 节选）：

```css
/* 由「设置 → 排版设置」生成，请勿手工编辑。 */

@font-face {
  font-family: "sjtu-font-1";
  font-weight: 400;
  font-style: normal;
  font-display: swap;
  src: url("/media/fonts/2/400-002.54b2de66.woff2") format("woff2");
  unicode-range: U+4E00-4E01, U+4E03, U+4E07-4E0B, U+4E0D-4E0E, U+4E11, ...;
}

:root {
  --font-body: "sjtu-font-1", var(--font-fallback);
  --font-body-weight: 400;
  --font-h1: var(--font-body);
  --font-h1-weight: 700;
  --font-h2: var(--font-body);
  --font-h2-weight: 600;
  ...
  --font-code: var(--font-mono-fallback);
}

body {
  line-height: 1.75;
}
```

### 4. 浏览器：字体生效、0 条报错、下载量

文章页 `/news/m2-first-guide/`（桌面 1024px）：

```js
{fontRequests: 21, fontBytes: 808352, inlineStyles: 0, fontsLoaded: 66}
getComputedStyle(document.body).fontFamily
  → "sjtu-font-1, \"PingFang SC\", \"Microsoft YaHei\", \"Noto Sans CJK SC\", sans-serif"
h1 → sjtu-font-1 / 700
```

新标签页打开同一页，`read_console_messages` 返回 **No console logs**（0 条）。页面 `[style]` 数量 0。

375px：`innerWidth=375`，`h1` 字号 27.2px = 32px × 0.85（设计 13.12.3 的手机端缩放），字体仍是 sjtu-font-1，0 条内联样式。

**注意**：808,352 字节 = 789 KiB。设计 13.12.5 的预算是 800KB —— 按 1KB=1024 算在预算内，按 1KB=1000 算超了 1%。只启用一个中文字重时约 590KB。已把实测数据写进设计 13.12.5。

### 5. 改回系统字体

正文改回「系统字体」保存后：

```
排版设置已保存，字体样式表已更新：/media/fonts/css/fonts.efc51d290193.css
```

前台同一篇文章：

```js
{fonts: 0, body: "\"PingFang SC\", \"Microsoft YaHei\", \"Noto Sans CJK SC\", sans-serif",
 cssLink: "http://127.0.0.1:8000/media/fonts/css/fonts.efc51d290193.css"}
```

新样式表里没有任何 `@font-face`，前台一个字体文件都不下载。

### 6. 删除正在使用的字体

后台 `/admin/settings/fonts/2/delete/`：

```
「思源黑体 CN」正在被排版区域使用（正文），不能删除。 请先在排版设置里把这些区域换成其他字体。
[前往排版设置]
```

直接 POST 删除接口也拦得住（绕过界面也不行）：

```
POST delete status: 200   still exists: True
POST delete weight: 200   face exists: True
```

### 7. 回归

```
/                    200
/news/               200
/about/              200
/sitemap.xml         200
/robots.txt          200
/healthz             200
/accounts/login/     200
/submit/             200
/me/                 302   （未登录跳登录页，符合预期）
```

```
{"status": "ok", "checks": {"database": {"ok": true, "detail": "ok"}, "disk": {"ok": true, ...},
 "worker_heartbeat": {"ok": true, "detail": "ok (0s ago)", ...}, "task_backlog": {"ok": true, ...}}}
```

`init_site` 连续跑两次输出一致，第二次没有新建任何东西：

```
已确保 9 个排版区域（默认系统字体），字体样式表：/media/fonts/css/fonts.f42c1154633c.css
...
rules: 9   css files: ['fonts.f42c1154633c.css']
```

### 8. docker / caddy

```
Successfully built 6065973633f7
Successfully tagged sjtu-ow:ci

$ docker run --rm sjtu-ow:ci python -c "import fontTools, brotli; print('fontTools', fontTools.version)"
fontTools 4.65.0
```

```
$ docker run --rm -e CADDY_SITE_ADDRESS=http://localhost \
    -v $PWD/deploy/Caddyfile:/etc/caddy/Caddyfile:ro \
    caddy:2.10-alpine caddy validate --config /etc/caddy/Caddyfile
Valid configuration
```

### 9. git

提交信息以 `008:` 开头，包含 T0 说的 `docs/design.md` 改动。

### 验收数据清理

验收用的两个字体（思源黑体 CN、Noto Serif SC）、临时超级管理员 `font008@example.com` 和多余的历史样式表都已删除；排版设置改回默认（正文和代码区系统字体，其余跟随正文）。`media/` 现在 104KB，只剩一个默认样式表。

## 设计偏差

已经改进 `docs/design.md`（v1.5.5），列出来供复核：

1. **`FontFamily.license_confirmed`**：12.4.3 的表里原来没有这个字段，但 13.12.1 要求必须勾选确认。加了字段把勾选留档。
2. **「跟随正文」区域的字重**：设计只说「字重只能选这个字体已有的字重」。`custom` 按硬校验做（选不了没处理完的字重）；`inherit` 如果正文字体缺这个字重，**只警告不拦截**——否则管理员刚传完 Regular 就会被四个标题区域卡住，没法保存。警告文案写明「浏览器会用假粗体」。生成样式表时，「跟随正文」的区域也会把正文字体 + 自己的字重算进 `@font-face`（否则标题会永远是假粗体）。
3. **常用汉字的排序**：设计写「按使用频率排序」，仓库里没有频率数据，我不编。实现用 GB 2312 一级汉字判定常用、片内按码位排序。**代价是真实的**：同一页面的汉字散落在多个分片里，短文章页要下 21 片。实测比较（思源黑体 CN，一页 87 个不同字）：每片 200 字 → 21 片 790KB；100 字 → 32 片 689KB；50 字 → 47 片 584KB；但长文章（850 个不同字）反过来：200 字 → 1111KB，50 字 → 1179KB。保持设计的 200 字默认，把这个取舍写进设计 13.12.2。想更省：用 Google Fonts 那条路径（Google 按共现聚类切好的片）。
4. **切片丢掉 hinting**：设计没写。实测中文分片小 12%（7.13MB → 5.86MB），Google 自己的网页字体也丢 hinting。已写进设计。
5. **工具类区域的字重**：`.font-nav` / `.font-button` / `.font-numeric` / `.font-code` 这四个区域，只有在选「字体库中的字体」时才把 `font-weight` 写进生成的样式表；系统字体 / 跟随正文时不写。否则一句 `.font-nav{font-weight:400}` 会盖掉模板里 logo 的 `font-semibold`，属于回归。已写进设计 13.12.4。
6. **Google 分片去重**：Google 对多个字重返回同一个可变字体文件，按内容哈希命名后只存一份（11.7MB → 5.9MB）。
7. **缓存头**：`deploy/Caddyfile` 给 `/media/fonts/<id>/*.woff2` 和 `/media/fonts/css/fonts.<hash>.css` 加了一年不可变缓存（设计 13.12.2 第 4 点要求「长期缓存」，但 Caddyfile 里 `/media/` 原来没有任何缓存头）。
8. **后台实现方式**：设计 14 节写「`ModelViewSet` + 自定义视图」，实际字体库全部用自定义后台页面（一个字体可能有多个字重、三条添加路径、还要预览和打包下载，`ModelViewSet` 的通用表单套不进去）。排版设置的实时预览用一个静态 JS 文件（`static/js/typography-preview.js`），不是 Alpine.js —— 后台没有引 Alpine，为一个预览再引一份不值。

## 未完成 / 不同意

1. **Google Fonts 后台表单在本机没验证**（原因见 2b）：服务器上线后需要再走一次。下载和解析逻辑本身已经用真实的 `fonts.googleapis.com` 响应跑通。
2. **「从网址下载」的后台表单在本机被 SSRF 检查拦下**，同样是 fake-ip DNS 导致，逻辑本身跑通了（下载 8.4MB 字体、跟随 GitHub 跳转）。
3. 斜体字重可以上传和切片，但排版设置没有「斜体」选项（设计 12.4.5 的 `TypographyRule` 也没有这个字段），所以斜体只能作为文件存在，暂时用不上。设计没要求，本轮不加。

## 顺带发现

1. `empty_state` 组件里的 `h2` 带 `text-xl`，一直被 `input.css` 的 `h2 {font-size: 1.5rem}` 盖着（这两条规则都不在 `@layer` 里，非分层样式优先级高于任何 utility）。本轮没动这个层叠关系，但以后要调排版层级时得先处理它。
2. Wagtail 把 `{% block extra_js %}` 渲染在 `<body>` **开头**（`skeleton.html`），脚本要自己等 `DOMContentLoaded`，否则拿不到表单。
3. `{{ dict|json_script:"id" }}` 才是给前端传 JSON 的正确姿势；直接 `{{ json_string }}` 会被 HTML 转义成 `&quot;`，`JSON.parse` 必失败。
4. 本机 `/usr/bin/git` 仍被 Xcode license 拦，提交继续用 GitHub Desktop 自带的 git。

## 需要确认

1. **字体体积预算**：中文字体两个字重就到 800KB 了。是把 13.12.5 的预算放宽到 1MB，还是在后台加一条硬提示「中文字体建议只启用一个字重」？（目前按实测数据写进设计，没改预算。）
2. **是否要在字体库里显示「这个字体一共占多少磁盘」**：一个中文字体两个字重就是 12MB 原始文件 + 12MB 分片，海外小服务器要留意。本轮没做。

## 改动文件

模型与迁移：`core/models.py`、`core/migrations/0005_fonts.py`。

字体：`core/fonts/__init__.py`、`slicing.py`、`processing.py`、`download.py`、`css.py`、`services.py`、`forms.py`、`admin_views.py`；`core/tasks.py`、`core/wagtail_hooks.py`、`core/context_processors.py`。

后台模板：`core/templates/core/fonts/{index,add,detail,delete,typography}.html`。

前台与样式：`templates/base.html`、`assets/css/input.css`、`static/css/typography-admin.css`、`static/js/typography-preview.js`。

初始化与配置：`core/management/commands/init_site.py`、`sjtu_ow/settings/base.py`、`deploy/Caddyfile`、`pyproject.toml`、`uv.lock`。

测试：`core/tests/test_fonts.py`、`core/tests/fonts_factory.py`。

文档：`docs/design.md`（v1.5.5）、`README.md`、`handoff/STATUS.md`、本报告。
