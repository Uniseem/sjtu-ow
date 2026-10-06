# 217 复核 07：战队与成员（teams/、members/）

范围：`teams/` 全部（services、views、forms、images、slots、notifications、admin_views、模板）、`members/` 全部，以及公开战队页对停用 / 注销成员的显示、队内联系方式、预渲染刷新、216 起「邮箱只给超管看」在模板和 JSON 里还有没有漏。

**复现情况**：写了两份复现脚本。脚本里的测试函数编号（`test_07_1`…`test_07_7`）是写脚本时定的，**和下面的 finding 编号不一一对应**，每条 finding 写明了对应哪个测试函数。断言写的是现在有缺陷的行为，所以测试绿就说明缺陷复现了。
- `findings/07-test_teams_repro.py`：测试机跑完了，退出码 0（`remote-check.sh` 没把 pytest 的退出码传出来），结果是 `3 failed, 2 passed`。`test_07_3`（对应 07-4）和 `test_07_5`（对应 07-7）**通过，算复现**。`test_07_1`、`test_07_2`（对应 07-1、07-2）是脚本自己的问题：测试库里没有 Wagtail 的根集合，`create_logo` 在建 `Image` 时就报 `Collection.get_first_root_node()` 是 None，没走到要验的地方（修的那一轮要先在测试里建根集合）。`test_07_4`（对应 07-8）的结论被推翻了一半，见 07-8。日志被 `tail -80` 截掉了，各条 `print` 的输出没有留下
- `findings/07-test_teams_repro2.py`（`test_07_6`、`test_07_7`，对应 07-5、07-3）：收尾时还在排队，按协调要求没等

---

## 高

### 07-1 队标的 EXIF 坏掉时，显示这个队标的每个页面都 500；首页、战队列表的静态页从此不再更新
- **严重度**：高
- **位置**：`teams/forms.py:72-84`（`clean_logo_file` 只查大小、扩展名、类型）、`teams/images.py:6-23`（`create_logo` 原样存）、`teams/views.py:113-119,219-227,256-265`；显示队标的地方有 `templates/components/team_tile.html:10`（`fill-400x400`）、`teams/templates/teams/detail.html:14`（`fill-288x288`）、`teams/templates/teams/_logo.html:7`、`members/templates/members/detail.html:62`，还有 `content/seo.py:33`（`fill-1200x630|format-jpeg`，战队主页的 og:image）
- **问题**：216 的 A4 已经确认过：EXIF 坏掉的 JPEG，或者带坏「Raw profile type exif」块的 PNG，能正常解码，只在 `ImageOps.exif_transpose` 这一步抛 `ValueError`。头像这条路已经修了（`accounts/images.py:45-52`）。队标这条路没修：Django 的 `ImageField` 只做 `verify()`，不碰 EXIF，所以文件照收。之后 Wagtail 生成缩略图时 `Filter.run` 会调 `willow.auto_orient()`（`wagtail/images/models.py:1062`），也就是 `ImageOps.exif_transpose`（`willow/plugins/pillow.py:477-484`）。`{% image %}` 标签只接 `SourceImageIOError`，这个 `ValueError` 一路冒出来，页面就 500。缩略图生成失败不会记下来，所以每次请求都会重新失败。
- **失败场景**：任何能建战队的成员（验证过邮箱、有 `team_create` 权限）上传这样一张 PNG 当队标。之后：
  - 实时渲染的页面直接 500：`/teams/<pk>/`（这支队是新的，还没有静态文件，就走 Django）、`/teams/?recruiting=1` 和 `?role=…`（带参数的请求都实时渲染）、队长自己的管理页 `/teams/<pk>/manage/`（页上有 `_logo.html`）、队长的个人主页 `/members/<pk>/`。管理页一打开就 500，队长连「删除队标」都点不到，只能等超管去后台换队标
  - 预渲染：`on_team_changed` 排了 `/teams/`、`/`、`/members/`、`/teams/<pk>/` 的生成任务，其中 `/teams/` 和 `/` 渲染时 500，`core/prerender.py:243-249` 记成「生成失败」、**保留旧的静态文件**。以后别的事（新文章、新赛事、新战队）触发首页和战队列表重新生成也一样失败，这两页一直停在旧版本，直到这个队标被拿掉。超管后台的待办里会冒出「生成失败的静态页面」
  - 不需要恶意：有些手机、修图软件导出的图 EXIF 本来就不规范
- **怎么验证**：`bash scripts/remote-check.sh run uv run pytest -q -s -p no:cacheprovider handoff/rounds/217-second-review/findings/07-test_teams_repro.py -k 07_1`。脚本用 216 那份坏 EXIF 的 PNG POST `/teams/new/`，再 GET 上面这些地址，打印状态码，并对 `/teams/` 和 `/teams/<pk>/` 跑一次 `prerender.render_html`。现在期望 `/teams/<pk>/` 和 `/teams/` 都是 500
- **状态**：已核对代码（Wagtail 8.0 和 Willow 1.12 的源码路径都读过，216 的测试也确认了这类文件确实会让 `exif_transpose` 抛错）；复现脚本跑了，但测试库里没有 Wagtail 的根集合，在建 `Image` 时就失败了，没走到要验的地方（见上面「复现情况」）
- **修法提示**：照 `accounts/images.square_face` 的做法，在表单或 `create_logo` 里先打开图片、`exif_transpose`，读不出就报字段错误，最好顺手重新编码一遍（07-2、07-7 也靠这个一起解决）

---

## 中

### 07-2 队标没有像素上限：一张几百 KB 的 PNG 能让每次生成缩略图都解码 4 亿多字节
- **严重度**：中
- **位置**：`teams/forms.py:72-84`、`teams/images.py:6-23`；对照 `accounts/images.py:23,39-40`（头像最多 4000 万像素）、`sjtu_ow/settings/base.py:324-325`（只配了 Wagtail 的上传大小和扩展名，这两项对 `create_logo` 不起作用，因为它绕过了 Wagtail 自己的上传表单）
- **问题**：队标只限文件不超过 5MB。Pillow 打开时，超过约 8950 万像素只发一条警告，超过约 1.79 亿像素才报错（`ImageField` 只会把后一种当成校验失败）。所以一张 12000×12000（1.44 亿像素）的纯色 PNG，压缩后只有几百 KB，照样能收进来。之后每生成一种尺寸的缩略图（288、400、96，加上 og 用的 1200×630 JPEG），Willow 都要把整张图解码成 RGB，约 432MB，缩放时还要再多占一些。
- **失败场景**：一个成员连着在管理页换队标（选文件就自动上传，**管理页的自动保存不限次数**）。每换一次，`on_team_changed` 就让 worker 重新生成战队主页、战队列表、首页，每页都要解码一遍这张大图。worker 只有一个进程，内存和 CPU 都被吃住，验证码邮件、其他页面的生成跟着排队。访客打开带参数的战队列表时，gunicorn 进程也会各解码一次。正式站那台 VPS 上还跑着别的服务（AGENTS「第二台」）
- **怎么验证**：`07-test_teams_repro.py -k 07_2`。脚本一行一行拼出一张 12000×12000 的 PNG 上传，打印文件大小、存下的宽高，以及 GET 战队主页前后的用时和进程峰值内存（`ru_maxrss`）。现在期望 `width*height > 4000 万`
- **状态**：已核对代码；复现脚本跑了，但和 07-1 一样因为测试库没有根集合而失败，没拿到内存数字。确实看到了 Pillow 的警告 `DecompressionBombWarning: Image size (144000000 pixels) exceeds limit of 89478485 pixels`，说明只是警告，表单没有拒收
- **修法提示**：和头像一样限制像素数（比如 4000 万），最好在服务器上缩到 512 以内、重新编码成 WebP 再存

### 07-3 队标的原图原样公开，手机照片里的 GPS 位置、机型都在
- **严重度**：中（隐私；头像那条路专门处理过这件事，队标这条路没有）
- **位置**：`teams/images.py:15-22`（上传的文件原样存成 Wagtail 原图，`original_images/<上传时的文件名>`）；`deploy/Caddyfile:93-98`（`/media/*` 全部公开，原图也在内）；对照 `accounts/images.py:1-7`（头像会重新编码，「Nothing the camera wrote into the file (place, device, time) survives」）
- **问题**：Wagtail 缩略图的文件名是「原图文件名去掉扩展名 + 裁剪规格」（比如 `/media/images/IMG_20261007_0930.2e16d0ba.fill-288x288.jpg`）。也就是说，任何访客都能从战队主页上的缩略图地址推出原图地址 `/media/original_images/IMG_20261007_0930.jpg`，下载到的是带完整 EXIF（GPS 坐标、机型、拍摄时间）的原文件。拿掉或换掉队标时，原图也不会删（见 07-11），所以一直能下载。
- **失败场景**：队长随手拿一张手机拍的照片（比如宿舍里拍的队服、战队合照）当队标，任何人都能拿到这张照片的拍摄地点
- **怎么验证**：`07-test_teams_repro2.py -k 07_7`。脚本上传一张带 Make、Model、GPS 的 JPEG 当队标，打印页面上的缩略图地址、原图存放路径，以及原图里留着的 EXIF，断言 GPS 还在。Caddy 这边是配置层面的事，靠读 `Caddyfile` 确认
- **状态**：已核对代码（Caddy 配置和 Wagtail 缩略图的命名都读过）；`repro2` 里的 `test_07_7` 和 07-1 一样，因为测试库没有根集合失败了（`KeyError: 'collection'`）。封面图、投稿图片的原图同样公开，那块归 02（图片与头像）
- **修法提示**：和 07-1、07-2 一起，在 `create_logo` 里重新编码（裁成方形、缩小、去掉 EXIF、用随机文件名）

---

## 低

### 07-4 队标内容格式不认识、文件名却是 .png 时，建队或保存战队资料都是 500
- **位置**：`teams/forms.py:80-83`（`content_type and content_type not in LOGO_TYPES`：类型为空就放行）、`teams/images.py:12`（`WillowImage.open` 没包 try）
- **问题**：Django 的 `ImageField` 会把 `content_type` 改成 Pillow 认出来的真实格式对应的 MIME 类型。但 Pillow 有 23 种能打开的格式根本没登记 MIME 类型：QOI、DDS、IM、MSP、SPIDER、SUN、PCD 等（在本机 Pillow 12.3 上用 `set(Image.OPEN) - set(Image.MIME)` 列出来的）。这些格式的 `content_type` 是 None，扩展名写成 `.png` 就能过表单。接着 `create_logo` 里 Willow 认不出格式，抛 `UnrecognisedImageFormatError`，`team_create` 和管理页的自动保存都没接住。头像那条路按 `picture.format` 白名单判断，没有这个问题
- **失败场景**：上传一张 QOI 格式的图、文件名改成 logo.png，就是 500。自动保存时 `autosave.js` 会显示保存失败
- **怎么验证**：`07-test_teams_repro.py -k 07_3`，期望 500
- **状态**：已复现（测试机上 `test_07_3_unrecognised_format_named_png_is_a_500` 通过，也就是这个 POST 返回了 500）

### 07-5 状态片段的编号只用 `isdigit()` 判断，`team-join:²` 是 500（内战、赛事的片段也一样）
- **位置**：`teams/slots.py:12-14`；同样写法在 `scrims/slots.py:42-44`、`tournaments/slots.py:102-104`
- **问题**：`"²".isdigit()` 是 True，`int("²")` 却抛 `ValueError`（本机 python3 真实输出：`True` / `ValueError invalid literal for int() with base 10: '²'`）。`/_fragments/state/` 谁都能请求，`render_requested` 也没包 try。这违反 AGENTS「编号一律过一道关」（应该用 `core.converters.as_id`）。`test_garbage_input` 只试了 `team-join:abc`
- **失败场景**：`GET /_fragments/state/?slots=team-join:²` → 500；214 起正式站的 500 会写进日志，可以拿它刷日志
- **怎么验证**：`07-test_teams_repro2.py -k 07_6`（三种片段都试，只对 team-join 断言 500）
- **状态**：已复现，只限 team-join（交回报告后 `repro2` 才跑完，结果是 `1 failed, 3 passed`：`test_07_6[team-join:²]` 断言了 500 并且通过；scrim、tournament 两个参数没有断言状态码，那两处只是同样写法，已核对代码）

### 07-6 拒绝和撤回申请不在事务里，和「通过」同时发生时，申请会记成「已拒绝 / 已取消」、人却已经入队
- **位置**：`teams/services.py:332-345`（`reject_application`）、`348-356`（`cancel_application`）；对照 `272-322`（`approve_application` 在 IMMEDIATE 事务里重新读状态）
- **问题**：拒绝和撤回是先读内存里那份申请的 `status`，再整行 `save()`。如果「通过」在这两步中间提交了，后写的那次会把 `APPROVED` 覆盖成 `REJECTED` 或 `CANCELLED`，但成员记录已经建好了。拒绝这条还会再发一封「未通过」的信（通过的信已经发了）
- **失败场景**：队长和超管同时处理同一条申请；或者申请人撤回的同时队长点了通过。这时申请人「我的入队申请」里写着已取消，可他其实已经是队员，还收到两封互相矛盾的信
- **怎么验证**：参照 `test_concurrency.py` 用真线程，一边 `approve_application`，一边 `reject_application`，看最后的状态和成员
- **状态**：推测（代码路径已核对，实际碰上的时间窗很窄）

### 07-7 入队申请的「每天 20 次」照样按「尝试」计数（T6 只修了建队）
- **位置**：`teams/views.py:161-166`：`over_limit(...)` 在 `form.is_valid()` 之前就计了数
- **问题**：216 的 T6 把建队改成只算有效的表单；申请入队这里还是老写法，没勾位置、留言超长这类无效提交也算一次
- **失败场景**：一个人连着几次忘了勾位置，当天剩下的次数就少了。要攒满 20 次才会被挡，影响小
- **怎么验证**：`07-test_teams_repro.py -k 07_5`：20 次无效提交以后，第一次有效申请被「今天的入队申请太多了」挡下
- **状态**：已复现（测试机上 `test_07_5_apply_limit_counts_invalid_forms` 通过）

### 07-8 （大半被推翻）非 ASCII 字母的队名大小写
- **位置**：`teams/services.py:46-50`
- **原来的推测**：SQLite 的 `LOWER()` 只处理 ASCII，所以「ＯＷ精英」完全同名也查不出来
- **测试机结果**：`test_07_4` 最后一行断言 `name_taken("ＯＷ精英") is False` **失败了，实际是 True**，所以完全同名查得出来，这一半推翻。但这条测试是在最后一行才失败的，说明前面的 `services.create_team(user=other, name="ｏｗ精英")` 没有抛错：全角大写的「ＯＷ精英」和全角小写的「ｏｗ精英」两个队能同时存在，和设计 7.1「不区分大小写唯一」不一致。`print` 的输出被截掉了，这个结论是从测试执行到哪一行推出来的
- **严重度**：低（不会 500，只是规则对全角字母不成立）
- **状态**：推测（结果只是部分观察到；要在 `-s` 下重跑、看打印出来的值再定）

### 07-9 改「每队人数上限」不重新生成战队列表和战队主页
- **位置**：`core/signals.py:8,37-42`（只盯首页那三个字段和栏目横幅）；设计 13.13.4 的事件表里也没有这一项
- **问题**：`/teams/` 的说明「每队最多 N 人」、每张战队卡上的「6 / 10 人」、各位置筛选后面的数量、战队主页的「现役 6 / 10」，都来自 `team_max_members`。改了这个设置以后，静态页最多要等到凌晨的全量生成才会更新
- **状态**：已核对代码（这是设计空白，有每天全量生成兜着）

### 07-10 赛事取消、结束、改名、改回草稿时，不重新生成战队主页的「参赛记录」
- **位置**：`tournaments/services.py:255-268`（`after_change` 只排赛事详情、赛事列表、首页）；`teams/templates/teams/detail.html:98-115` 会显示赛事名称、「已取消 / 已结束 / 已通过」和参赛次数；设计 13.13.4 的「赛事创建、修改、发布、取消、结束」一行没有写战队主页
- **失败场景**：赛事取消以后，战队主页上还写「已通过」；赛事改回草稿以后，战队主页上还链着一个 404 的赛事页。都要等到凌晨全量生成
- **状态**：已核对代码（设计空白）

### 07-11 换队标、删队标都不删旧图，旧图也和编辑上传的图混在同一个根集合里
- **位置**：`teams/views.py:219-227,256-265`（只有失败时才 `_drop_unused_logo`）、`teams/images.py:15-21`（没有指定 `collection`，就进了根集合）
- **问题**：每换一次、删一次队标，旧图就留在图片库里。管理页「选好文件就上传」，来回试几张就是几张，而且原图都公开（07-3）。根集合里的图会出现在有根集合选图权限的人的选图对话框里（比如给文章选封面时）
- **状态**：已核对代码；选图对话框里实际能看到哪些图，没有核对

### 07-12 建队页「建不了」的提示框用了不存在的样式类
- **位置**：`teams/templates/teams/create.html:16`：写的是 `c-notice--warning`，`assets/css/input.css:2625` 里只有 `c-notice--warn`
- **问题**：队长已经当满 3 支队的队长、或者被关了建队功能时，这块提示没有警告的底色和图标颜色
- **状态**：已核对代码

### 07-13 已解散的战队页面还显示「现役成员 · 还没有成员」和「现役 0 / 10 人」
- **位置**：`teams/templates/teams/detail.html:24,53-77,121`；细节文档 5.3 第 6 条写的是「已解散的战队：只写『该战队已解散』，不显示成员和退役名单」
- **问题**：退役名单藏了，现役那一节和页头、侧栏的人数还在
- **状态**：已核对代码

### 07-14 注销清单里退役记录那一行写反了
- **位置**：`accounts/services.py:356`：`"teams.TeamAlumnus.user": "保留，退役记录显示「已注销用户」"`
- **问题**：代码（`teams/services.py:448-451`）和设计（细节 5.4、设计 7.4「注销账号时一起删」）都是删掉。这个字典只用来在测试里登记每一列怎么处理，不影响行为，但后来的人会被它误导
- **状态**：已核对代码

### 07-15 成员个人主页有 N+1
- **位置**：`members/services.py:146-153`（战队没有 `select_related("logo")`）、`members/templates/members/detail.html:62`、`103`（`article.url` 不带请求，AGENTS 163 提醒过，每篇一次查询）
- **问题**：一位写了 10 篇文章、在 3 支有队标的战队里的成员，打开主页大约多 13 次查询。这页是实时渲染的
- **状态**：已核对代码（查询数没有实际量过）

---

## 查过没问题

- **邮箱只给超管看（216）**：把模板（全部 `*.html`）和 Python 里出现 `.email`、`email__icontains` 的地方都 grep 了一遍。给非超管看的地方都已经改成 `sees_emails` / `person_label`：分组人选器的 HTML 和 JSON、搜人只按昵称、文章作者下拉的 `viewer` 默认是不给看。剩下打印邮箱的都只有超管能进：后台的「用户与权限」「战队」两个标签（`access.is_superuser`）、`teams/templates/teams/admin/assign_captain.html`、`members/models.py:17` 的 Wagtail InlinePanel（`/wagtail/` 只给超管）。`User.__str__` 是昵称（昵称必填，至少 2 个字）。`core/outbox.who` 只有在没有昵称时才显示地址，战队的信收件人都是用户。战队的信里没有任何人的邮箱。站内搜索成员只按昵称匹配
- **队内联系方式**：只出现在 `teams/slots/join.html` 里队长 / 队员那两个分支（预渲染用的是访客身份，`core/prerender.py:150-160`）、个人中心「我的战队」（已经过滤掉解散的队）、入队通过的信。没有进静态页，也没有进后台的 `TeamForm`
- **停用 / 注销的成员**：战队主页上停用的人只剩默认头像、昵称、「账号已停用」和入队时间（`avatar.html` 判断 `is_active`，`member_url` 对停用的人给空字符串）；注销时 `leave_all_teams` 删掉成员和退役记录，并刷新这些战队的主页；停用、恢复时 `accounts/signals.py` 的 `PUBLIC_FIELDS` 里有 `is_active`，会刷新现役和离开过的战队主页、成员展示；待审批列表、7 天提醒、通过时都会跳过停用的申请人
- **改状态的入口都经 service 查队长或超管**：通过、拒绝、撤回、退出、移除、转让、指定、解散、去掉退役记录；210 的 T2、T4、T5、T6、移除队长都已经修了，事务里的检查也看过（`create_team`、`apply_to_team`、`assign_captain`）
- **预渲染刷新**：建队、改资料、通过申请（等事务提交后）、退出、移除、转让、解散（删静态页 + 刷新列表）、去掉退役记录、停止招募，都会刷新战队主页、列表、首页、成员展示；对已解散的队都会跳过战队主页
- **成员展示**：只列已加入的人（`joined_users`），隐藏的分组不出现，空名字的分组不出现，组内按排序再按昵称，筛选时编号不变（147 决定只按主位置筛，是有意的）；个人主页对停用、没验证邮箱的人是 404，加了 `noindex`；分组的增、删、移动、改职务都会通过信号刷新 `/members/`
- **后台战队编辑**：`TeamForm.clean_name` 查重、改完照样调用 `on_team_changed`

## 没来得及看

- 07-1、07-2 的复现脚本要先在测试里建好 Wagtail 根集合再跑；`repro2`（07-3、07-5）收尾时还在排队，没拿到输出
- 状态片段接口的缓存头（`private, no-store` 已经看到）和 Caddy 对带查询参数请求的分流，没有逐条走
- 后台成员分组页 `group_member_*` 的变异覆盖（拆掉 `sees_emails` 会不会红），没有跑变异测试
- 战队的信对停用账号要不要发（解散、移除时停用成员也会收到信），设计 3.7 没写，没有当成缺陷记
- 设计 5.5.1 的「图片（队标…）送审，可以在后台开启」：全站 grep 不到任何地方提交 `TargetType.IMAGE`，像是没做。归 AI 审核那块，没有展开
