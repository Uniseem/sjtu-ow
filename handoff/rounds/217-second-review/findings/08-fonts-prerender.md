# 217 复核 08：字体、预渲染、Caddy

复核人：08 号子代理（只记录，不修）。范围：`core/fonts/`（含 210 没读的 `processing.py`）、`core/prerender.py`、`core/prerender_admin.py`、`core/middleware.py` 的 `PrerenderMissMiddleware`、`deploy/Caddyfile`，以及 215 的「字体原文件 404」规则和代码实际写出的每一种字体文件名。

复现脚本都在本目录，测试机上跑过一次（`runs/20261007-033727-d00ad12`）：

- `08-repro_test.py`：pytest，每条断言「缺陷存在」，绿 = 已复现。**第一次运行时文件里只有 08-1～08-5、08-3 三个参数**（7 passed）；08-8、08-9 两条是后来加的，因为协调者要求收尾，**没有在测试机上跑过**
- `08-woff_bomb.py`：WOFF 压缩炸弹，量峰值内存。第二个参数（换成别的表，比如 `glyf`）是后来加的，没跑过
- `08-google_timing.py`：照 `download_google_slices` 的顺序下载 Google 分片并计时
- `08-caddy_probe.py`：起真 Caddy（`caddy:2.10-alpine`），用各种变形地址请求原文件，再看 `/media/documents/`

```
bash scripts/remote-check.sh run bash -c "uv run pytest -q -s -p no:cacheprovider F/08-repro_test.py; uv run python F/08-woff_bomb.py; uv run python F/08-google_timing.py; uv run python F/08-caddy_probe.py"
```

---

## 中

### 08-1 Google 字体：删掉一个没人用的字重，会连带删掉另一个正在用的字重的分片

- **严重度**：中
- **位置**：`core/fonts/services.py:320-326`（`delete_face`）→ `core/fonts/processing.py:149-158`（`delete_slice_files`）；共用文件来自 `core/fonts/download.py:199-203`
- **问题**：Google 对可变字体的多个字重给的是同一个文件，`download_google_slices` 按内容哈希命名、只存一份（`fonts/<id>/google-<哈希>.woff2`，设计 13.12.2 第 5 步就是这么定的），所以 400 和 700 两条记录的 `slices` 指向同一批文件。`delete_face` 不检查别的字重还用不用，直接删 `face.slices` 里的每个文件。设计 13.12.2 要求删分片前「再确认没有任何字重仍在引用」，`delete_unreferenced_slices` 做了这个检查，`delete_face` 没做。`add_google_faces:150-152` 里那个「stale」删除也是立即删、不查引用，但现在的界面每次都新建字体，走不到那条路
- **失败场景**：从 Google Fonts 加了「Noto Sans SC」的 400、700，排版设置里一级标题用 700。超管在字体详情页删掉没人用的 400（`is_face_in_use` 放行）→ 700 的分片文件一起没了；700 的记录还是「可用」，样式表照样引用这些地址，访客拿到 404，标题回落到系统字体，后台看不出任何异常
- **怎么验证**：`08-repro_test.py::test_08_1_…`
- **状态**：**已复现**。测试机输出：
  ```
  400 的分片： [{'path': 'fonts/1/google-1a10f0cd.woff2', ...}]
  700 的分片： [{'path': 'fonts/1/google-1a10f0cd.woff2', ...}]
  删掉 400 以后，700 的状态： ready ；分片文件还在吗： False
  当前样式表仍引用： True
  ```

### 08-2 撤回发布和正在进行的生成撞上：撤回的文章又被写回静态文件，最长公开一天

- **严重度**：中（会公开已经撤回的内容；时间窗只有一次渲染那么长）
- **位置**：`core/prerender.py:223-261`（`generate`）、`core/prerender.py:391-396`（`_remove_now`）
- **问题**：215 把下线删除改到了 `web` 里、事务提交后立刻删（C5），但 worker 的 `generate` 是「先渲染、后写文件」，中间不再确认页面还公开。worker 在文章还在线时开始渲染，渲染期间 `web` 撤回发布并删除文件和记录，worker 随后照样 `write_page`，`record.save()` 又把记录插回成 READY。之后没有任何事件会再删它：中间件只在 Django 收到请求时才动，可 Caddy 直接把文件发出去了；要等第二天凌晨全量生成时，这个路径不在 targets 里才删
- **失败场景**：编辑刚改完一篇文章（排了一次 30 秒后的重新生成），或者正好赶上全量生成走到它，同时另一位编辑因为内容有问题撤回这篇文章 → 撤回成功、后台显示已撤回，但 Caddy 继续把旧页面发给所有人，最长到次日凌晨
- **怎么验证**：`08-repro_test.py::test_08_4_…`：在 `render_html` 返回前调 `unpublish()` 再调 `_remove_now()`，模拟 `web` 在渲染期间提交
- **状态**：**已复现**（用替换 `render_html` 的方法模拟时序；真实并发未在两个进程里复现）。输出：
  ```
  文章 live=False；静态文件存在=True；记录=ready
  全量目标里还有它吗： False
  ```
- **同一处的另一个问题（推测，未复现）**：`request_page` 用 `requested_at` 合并请求，`generate` 最后又把开头读到的 `record` 整行 `save()`（`requested_at=None`）。渲染进行中来的一次 `request_page` 看到 `requested_at` 不到 30 秒，判成「已经排上了」不再入队，随后被 `generate` 清掉 → 这次改动的内容没有进静态页，要等下一次事件或凌晨全量（`core/prerender.py:355-364`、`:259-260`）

---

## 低

### 08-3 坏字体让「上传字体」页面 500，而不是表单报错

- **严重度**：低（只有超管能进字体库）
- **位置**：`core/fonts/processing.py:72-86`（`inspect_font` 只在 `TTFont()` 和 `getBestCmap()` 外面接了异常）、`core/fonts/forms.py:51-56`（只接 `FontError`）
- **问题**：`TTFont(..., lazy=True)` 不在打开时解析表，`font.get("OS/2")`、`font.get("head")` 才解析；表被截短时抛 `struct.error`，不是 `FontError`，表单的 `clean_file` 接不住，整个请求 500。同类：`download.fetch_bytes:91-92` 的 `int(Content-Length)` 遇到不是数字的头抛 `ValueError`，`_create_from_url` 只接 `DownloadError/FontError`，也是 500，而且 `create_family` 已经提交的空字体留在库里
- **失败场景**：超管上传一个下载不完整或损坏的 TTF → 500 页面（错误监控里一条异常），而不是「无法解析字体文件」
- **怎么验证**：`08-repro_test.py::test_08_3_…`（把表目录里的长度改成 6）
- **状态**：**已复现**（OS/2、head 两种；name 表截短时 fontTools 自己容错，不出错）：
  ```
  b'OS/2': inspect_font 抛出 error: unpack requires a buffer of 78 bytes
      表单 is_valid() 也抛： error
  b'head': inspect_font 抛出 error: unpack requires a buffer of 54 bytes
      表单 is_valid() 也抛： error
  ```

### 08-4 一个 1MB 的 WOFF 让上传请求吃掉 2GB 内存（压缩炸弹）

- **严重度**：低（要超管上传或填一个外部地址；后果是 `web` 或整台机器内存耗尽）
- **位置**：`core/fonts/processing.py:61-70`（只限制压缩后的 30MB）；fontTools `sfnt.py` `WOFFDirectoryEntry.decodeData` 直接 `zlib.decompress`，`woff2.py:79` 直接 `brotli.decompress` 整个流，都是解完才比长度
- **问题**：30MB 上限只看文件本身。WOFF 的每张表、WOFF2 的整个数据流都可以压得极小、解开极大。`inspect_font` 在 `web` 的请求里同步跑（上传表单、从网址下载），解压不设上限
- **失败场景**：超管「从网址下载」一个第三方发布的字体（比如 GitHub 上的「免费中文字体」），文件是炸弹 → gunicorn 进程申请几个 GB 内存，可能触发 OOM、拖垮同机的其他服务（正式站上还跑着 WordPress 等）。另外，`inspect_font` 只读 OS/2、head、cmap、name，**炸弹放在 `glyf` 里能通过上传检查**，到 worker 切片时才解开；worker 被 OOM 杀掉后，214 的 `reset_orphaned_running_tasks` 会在重启时把这条任务放回队列 → 推测会反复崩，期间验证码邮件全停（这一段**推测**，`08-woff_bomb.py <字节数> glyf` 可验，没跑）
- **怎么验证**：`uv run python 08-woff_bomb.py`
- **状态**：**已复现**（cmap 炸弹）：
  ```
  WOFF 文件 1.00 MB（上限 30 MB），cmap 解压后 1024 MB
  inspect_font 抛出 FontError: 字体没有可用的字符映射表：'NoneType' object is not iterable
  耗时 3.4 秒；进程峰值内存 125 MB → 2173 MB（+2048 MB）
  ```
  30MB 的文件按同样比例能解出约 30GB

### 08-5 Wagtail 的「页面隐私：要登录」设了以后，静态文件照旧对所有人公开

- **严重度**：低（只有超管能进 `/wagtail/` 设隐私）
- **位置**：`content/signals.py`（只接 `page_published/unpublished/slug_changed/move/delete`，没接 `PageViewRestriction` 的保存）、`core/prerender.py:167-170`（只有 404/410 算 `PageGone`，302 只记「生成失败」、文件不动）
- **问题**：设计 13.13.5「不再公开的内容必须立即删除静态文件」。给一篇已发布文章（或一个栏目，连同下面所有文章）设「要登录」后，没有任何信号触发删除；手动重新生成时 Django 对匿名访客返回 302，`generate` 只记失败，旧文件留着。`content_targets` 用了 `.public()`，凌晨全量时才删
- **失败场景**：超管把一篇内部通知设成「仅登录可见」→ 未登录访客照样从 Caddy 拿到全文，最长到次日凌晨；后台「静态页面」里它显示「生成失败：页面返回 302」，看起来像是生成出了问题而不是内容泄露
- **怎么验证**：`08-repro_test.py::test_08_5_…`
- **状态**：**已复现**：
  ```
  设了「要登录」后匿名访问 Django：302 /_util/login/?next=/news/soon-private/
  重新生成：failed 页面返回 302，不生成静态文件
  静态文件还在： True ；还在全量目标里： False
  ```

### 08-6 旧字体样式表按「文件创建时间」清理：用了很久的那份，一换就被删

- **严重度**：低（自定义字体在预渲染页上暂时失效几分钟，样式表变量回落到 `input.css` 的默认值）
- **位置**：`core/fonts/css.py:210-226`（`_clean_old_stylesheets` 用 `get_modified_time`）
- **问题**：设计 13.12.4「旧的样式表文件保留一天再删除，避免刚生成时还在传输的页面拿不到文件」，意思是「被换下来以后再留一天」。代码比较的是文件写出的时间：一份样式表如果 10 天前生成、一直在用，换成新的那一刻就被删。可这时所有预渲染页还引用旧地址，要等 `request_all_soon` 30 秒后开始、全量生成跑完（几分钟）才换掉；浏览器里开着的页面、bfcache 里的页面也一样
- **失败场景**：超管在排版设置里改一下行高 → 这几分钟里访客打开的预渲染页，字体样式表 404，正文和标题回落到系统字体
- **怎么验证**：`08-repro_test.py::test_08_2_…`（把旧样式表的修改时间改到 10 天前）
- **状态**：**已复现**：
  ```
  旧样式表 /media/fonts/css/fonts.f42c1154633c.css → 新样式表 /media/fonts/css/fonts.8a97bcd3612e.css
  旧样式表还在吗： False
  ```

### 08-7 「从 Google Fonts 下载」在 web 请求里同步下载，同一个文件按字重重复下载

- **严重度**：低
- **位置**：`core/fonts/admin_views.py:169-203` → `services.add_google_faces` → `download.download_google_slices:194-203`（先 `fetch_bytes` 再看文件在不在）；gunicorn 没配 `--timeout`（`deploy/entrypoint-web.sh`，默认 30 秒）
- **问题**：设计 13.12.1 写的是「由服务器在后台下载」，实现是在超管点按钮的那个请求里逐个下载。可变字体每个字重都给同一批地址，代码按 @font-face 逐个下载，不去重：Noto Sans SC 选 400、700 是 202 次请求、其中 101 次是重复的。每次都新建 TLS 连接
- **失败场景**：在测试机上 400+700 用了 18.2 秒；多选几个字重（或正式站到 gstatic 的网络慢一些）就会超过 gunicorn 的 30 秒，worker 被杀、Caddy 给维护页；`create_family` 已提交，留下一个没有字重的空字体，已下载的分片成了没人引用的孤儿文件（`delete_family` 只删字重记录里列出的文件）
- **怎么验证**：`uv run python 08-google_timing.py "Noto Sans SC" 400,700`；超时那一步是**推测**（没在正式站网络上测）
- **状态**：下载次数和耗时**已复现**：
  ```
  Noto Sans SC ['400', '700']：样式表 0.1 秒，202 个 @font-face，101 个不同的地址
  已下载 202/202，8.6 MB，累计 18.2 秒
  合计 18.2 秒（gunicorn 默认 30 秒超时）
  ```

### 08-8 重新处理字体时，先处理完的字重把还在排队的字重踢出线上样式表

- **严重度**：低（几分钟的显示退化；排队的字重处理失败时则一直缺）
- **位置**：`core/fonts/services.py:171-180`（`queue_face` 把 READY 改成 PENDING）、`:262-263`（处理完就 `regenerate_font_css`）、`core/fonts/css.py:85-98`（`used_faces` 只收 READY）
- **问题**：「重新处理」（`reprocess_family`）把这个字体的每个字重都改成 PENDING，旧分片其实还在、还能用。worker 一个一个处理：先做完 400，因为在用就重写样式表，而 700 此时是 PENDING，被排除 → 新样式表没有 700，随后全站预渲染重新生成。到 700 处理完才补回来。替换一个在用的字重（`add_face_from_bytes` 同样先改 PENDING）、处理期间任何一次排版自动保存，也一样
- **失败场景**：正文 400、标题 700 都用同一个中文字体，超管点「重新处理」→ 中文字重一个要几分钟，这段时间全站标题用系统字体或假粗体；如果 700 重新处理失败（比如原文件丢了），标题就一直没有自定义字体，而排版设置里仍显示选着它
- **怎么验证**：`08-repro_test.py::test_08_8_…`
- **状态**：**已核对代码**（测试已写好，未在测试机上跑）

### 08-9 删除字体先删文件、后删记录；记录因 PROTECT 删不掉时，文件已经没了

- **严重度**：低
- **位置**：`core/fonts/services.py:353-366`（`delete_family`）、`core/models.py` `TypographyRule.family`（`on_delete=PROTECT`）、`core/autosave.py:117-133`
- **问题**：`delete_family` 只查 `mode=custom` 的区域，然后先删全部分片和原文件，最后 `family.delete()`。只要还有一条区域 `mode` 不是 custom 但 `family_id` 没清空，`PROTECT` 就让最后一步抛 `ProtectedError` → 500，此时文件已删、记录还说「可用」。这种区域可以由自动保存造出来：同一行里「字体来源」改成系统字体的同时，另一个框（字间距打到一半的「-」）不合法，`save_valid_fields` 只存合法的已改字段 `mode`，`family` 没改动所以不存，而 `TypographyRuleForm.clean` 里把 family 清空只有整张表单都合法时才生效
- **失败场景**：如上存出一条「系统字体 + 挂着字体 F」的区域，之后删除 F → 500；F 留在字体库里显示可用，但文件都没了，再选它就是 404
- **怎么验证**：`08-repro_test.py::test_08_9_…`
- **状态**：**已核对代码**（测试已写好，未在测试机上跑；自动保存那一步的触发要靠时机，属**推测**）

### 08-10 Wagtail 文档（`/media/documents/`）任何扩展名都收，Caddy 直接当网页发，没有 CSP、nosniff

- **严重度**：低（只有超管能在 `/wagtail/` 上传文档；但违反设计 15.2「上传文件只允许 JPG、PNG、WebP，不允许 SVG」）
- **位置**：`sjtu_ow/settings/base.py:39`（装了 `wagtail.documents`，没设 `WAGTAILDOCS_EXTENSIONS`）、`sjtu_ow/urls.py:14`、`deploy/Caddyfile:93-98`（`handle /media/*` 只加缓存头和 HSTS）
- **问题**：传一个 `.html` 或 `.svg` 文档，`/media/documents/<名字>` 由 Caddy 以 `text/html`、`image/svg+xml` 在本站源下发出，不带内容安全策略、`X-Content-Type-Options`、`Content-Disposition`。放在受限集合里的文档也能绕过 Wagtail 的权限直接下载
- **失败场景**：超管（或拿到超管会话的人）上传一个 HTML 文档，链接发出去就是本站源下的任意脚本；或者把内部文件放在「私密」集合里，以为别人看不到
- **怎么验证**：`08-caddy_probe.py` 的 documents 段
- **状态**：Caddy 行为**已复现**（真 Caddy）：
  ```
  200 /media/documents/note.html Content-Type=text/html; charset=utf-8 nosniff=None CSP=None Content-Disposition=None
  200 /media/documents/pic.svg Content-Type=image/svg+xml nosniff=None CSP=None Content-Disposition=None
  ```
  上传端（Wagtail 不限扩展名）**已核对代码**

### 08-11 字体切片占住唯一的 worker，期间邮件和预渲染都排队

- **严重度**：低
- **位置**：`core/tasks.py:84-92`、`core/fonts/services.py:183-195`、`core/fonts/services.py:342-350`
- **问题**：worker 只有一个、串行执行（设计 16.2）。设计 13.12.2「同一时间只处理一个字体」的 `another_face_is_processing` / requeue 在单 worker 下其实用不上；真正的效果是字体任务排在队列里时，后面来的验证码邮件、预渲染都要等全部字重切完。「重新处理」一次把这个字体所有字重都排进去，一个中文字重要几分钟（设计原话）
- **失败场景**：超管重新处理一个 4 个字重的中文字体，接下来十几分钟新注册的人收不到验证码
- **怎么验证**：排两个中文字重的处理任务，紧接着触发一封验证码信，看信的入队和发出时间
- **状态**：**已核对代码**（未复现）

### 08-12 静态文件清单读到一半时，全量预渲染整轮中止

- **严重度**：低（时间窗很窄，只在升级时 `collectstatic` 写清单的那一刻）
- **位置**：`core/prerender.py:119-148`、`:155`（`refresh_static_manifest` 在 `render_html` 的 try 外面）；Django `ManifestFilesMixin.save_manifest` 先删后写，不是原子的
- **问题**：worker 正好在 `web` 启动跑 `collectstatic` 时读到写了一半的 `staticfiles.json`，`load_manifest` 抛 `ValueError`，不是 `PrerenderError`，从 `generate` 直接抛出去；`generate_all` 没有逐页兜底，整轮中止，后面的页面不生成、下线页面的清理那一段也不跑。磁盘写满时 `write_page` 的 `OSError` 同理
- **状态**：**推测**（读代码得出，未复现）

---

## 查过没问题

- **215 的「字体原文件 404」和代码写出的每一种文件名对得上**：切片 `fonts/<id>/<字重>[i]-<序号>.<8位哈希>.woff2`（`processing._slice_name`）、Google 分片 `fonts/<id>/google-<8位哈希>.woff2`、样式表 `fonts/css/fonts.<12位哈希>.css` 都匹配 `@hashed_fonts`；原文件 `fonts/<id>/original/<名字>` 多一层目录，不匹配，落到 `respond 404`。存储重名时 Django 改名（`_随机7位`）的文件，代码记录的仍是原名，不会引用到改过名的
- **真 Caddy 对原文件的 24 种变形地址全部 404、没有一处给出内容**：双斜杠、`%2F`/`%2f`、`%66onts`、`./`、`../`、反斜杠和 `%5C`、大小写、末尾斜杠、`%00`、带查询参数、目录本身（`08-caddy_probe.py`，「泄露 0 处」）。正常分片和样式表仍 200、`immutable`
- 原文件的保存名：上传名经过 Django 的 `sanitize_file_name`（去路径、拒 `..`），网址下载的名字经 `filename_from_url` 只留 `[A-Za-z0-9._-]`，`upload_to` 之后还有 `validate_file_name`
- `css.py`：样式表里的字体名只用自动分配的 `sjtu-font-<n>`，不用超管填的显示名，没有 CSS 注入；分片地址来自代码自己生成的路径；Google 的 `unicode-range` 原样写入，来源只认 `fonts.gstatic.com`
- 切片可复现（`recalcTimestamp=False`、brotli 确定性），重新处理同一个文件不会产生新文件名；被替换的分片一天后才删，删前查所有字重的引用（`delete_unreferenced_slices`）
- 嵌入权限：`fsType` 的 0x0002、0x0200 都拒；表解析失败时不会被当成 0 放行（fontTools 默认 `ignoreDecompileErrors=False`，见 08-3，是 500 而不是放行）
- 下载：只允许 https、连接时连检查过的地址（216 的 C8）、跳转再检查、体积上限按 `Content-Length` 和实际读取双重检查
- `normalize_path` / `file_for`：拒 `..`、`//`、`?`、`#`，相对路径去掉开头斜杠后才拼到根目录下，没有越出预渲染目录的路径；中间件只对 `cached_targets` 里有的路径才碰文件系统；后台「重新生成」215 起检查路径
- 预渲染三道闸（匿名 Client、带 Cookie 拒写、`SECRET_MARKERS`）、404/410 当 `PageGone` 删除、`generate_all` 清掉不在目标里的记录；`clear_all` 只清目录内容（挂载点不删）
- `_remove_now` 删除失败时标「生成失败」并排 worker 重删（215 的 C5 做法）
- Caddy 顺序：哈希静态 → 静态 → 字体 → 图片 → 其余 media → 必走 Django → 非 GET/HEAD → 带查询 → 预渲染 → Django；预渲染页带 CSP 和 HSTS；`/news/a`（不带斜杠）也命中预渲染文件，`/news/a/index.html` 交给 Django，没有直接暴露 `.html.br`、`.tmp-*`
- `font_faces_css`、字体后台的每个视图都有 `superuser_required`；模板里没有 `|safe`

## 没来得及看

- 08-8、08-9 的测试和 `08-woff_bomb.py … glyf` 没在测试机上跑（协调者要求收尾）
- 正式站的 `Caddyfile.vps` 和服务器上的 HSTS 实际值、正式站到 `fonts.gstatic.com` 的下载耗时
- worker 被 OOM 杀掉后字体任务反复重跑的真实表现（08-4 后半）
- `core/fonts/admin_views.typography` 的整表单（非自动保存）路径与 `TypographyFormSet` 的交互细节、排版设置页的前端预览脚本
