# 15 211–216 的改动本身（回归与没修完）

复核人：块 15 代理。范围：`git diff 86cddb1..HEAD -- . ':!handoff' ':!docs'` 的业务代码逐块读过，对照 210 review 的失败场景重推一遍，再看相邻行为和 design v7.14–v7.20。

**没有在测试机上跑任何复现**：协调人中途要求收尾、不再开新的测试机运行。下面全部是「已核对代码」（代码路径逐行读通）或「推测」（路径读通、发生频率或时序没量）。每条都写了复现的办法，留给修的那一轮。

## 中

### 15-1 删分类：草稿改过分类的已发布文章，原分类显示「没有文章在用」，删除时 500（212 D2 引入）

- 严重度：中
- 位置：`content/services.py:234-265`（`category_use_counts`）、`backoffice/views/categories.py:28-35,103-115`、`content/models.py:267-273`（`category` 是 `on_delete=PROTECT`）
- 问题：`category_use_counts` 每篇文章只算一次，最新修订（或定时修订）里的分类**覆盖**页面行上的分类（`by_page[int(object_id)] = category_id`）。可是页面行的 `category` 外键是 PROTECT：已发布文章的页面行还指着旧分类时，旧分类在计数里成了 0。212 之前按 `category.articles.count()`（页面行）计数，这种情况会正确拒绝。
- 失败场景：文章 A 已发布在分类 Z（页面行 category=Z）。编辑在后台把 A 的草稿改到分类 X（自动保存只写修订）。如果 Z 里没有别的文章，分类列表上 Z 的文章数是 0、显示「删除」按钮；点删除 → `category.delete()` → `ProtectedError` → 500。另一个变体：一篇文章同时有排了定时的修订 R1（分类 Y）和更新的草稿 R2（分类 X），两条修订都进了 `rows`，按迭代顺序只留下一个，另一个分类算 0、被删掉。定时上线时 `as_object()` 遇到删掉的分类，就是 D2 当初说的 500，排在后面的定时文章也发不出去。
- 怎么验证：照 `content/tests/test_category_delete.py` 写一条：建分类 Z、X，在 Z 下发布一篇文章（`save_revision().publish()`）；`draft = page.get_latest_revision_as_object(); draft.category = X; draft.save_revision(user=editor)`；内容编辑 `Client(raise_request_exception=False)` GET 分类列表，应该没有 Z 的删除地址（现在有）；POST `category_delete` Z，应该是 302 加拒绝提示（现在是 500）。修法：页面行、最新修订、定时修订里出现过的分类**都**算「在用」（每个分类各自计数，不要每页只留一个）。
- 状态：已核对代码（Django 删 PROTECT 引用时抛 `ProtectedError`，视图没有接住）

### 15-2 保存时联网查 b23 短链，有几条路径在 IMMEDIATE 写事务里，占着整库写锁（211 D1/D10 引入）

- 严重度：中
- 位置：`content/models.py:410-428`（`ArticlePage.save` → `stored_counts` → `analyse` → `video_src` → `get_embed` → `follow_b23`，`urlopen(timeout=10)`）、`tournaments/models.py:125-135`、`scrims/models.py:118-128`（`plain_text`，同一条路）；在事务里调用的有：`content/drafts.py:start_article` → `parent.add_child`（treebeard 的 `add_child` 带 `@transaction.atomic`）、`core/autosave.py:125`（`save_valid_fields` 的 `with transaction.atomic(): stored.save(update_fields=…)`，`description` 在里面就重算）
- 问题：211 把正文渲染从「读页面时」挪到了「`save()` 时」。渲染里每条第一次见到的 b23 短链都要联网（失败的结果缓存 1 小时，成功的永久缓存）。本站所有写事务都是 `BEGIN IMMEDIATE`（设计 12.12），所以写锁从事务开始一直持有到联网结束。别的写操作（会话、自动保存、评论；216 起限流计数 `over_limit` 也包在事务里，所以 `/_fragments/state/`、搜索这些 GET 也要写锁）等满 5 秒就报 `database is locked`，返回 500。211 以前联网只发生在渲染（GET）时，不占写锁。
- 失败场景：（1）验证过邮箱的成员点「写文章」，先把一篇带 50 条各不相同的 `https://b23.tv/<随机>` 的正文粘进去，第一次自动保存就建文章（`start_article` → `add_child`，事务里），持锁时间约为 50 × 每次往返（b23 不通时每条 10 秒）。换一批随机链接就能重来一次，「新建」没有次数限制；不开脚本、整张表单提交的新建文章走同一条路。（2）赛事或内战管理员在说明里**逐字打**一个 b23 地址：每停 800 毫秒自动保存一次，每次都是一个新的半截地址，在 `save_valid_fields` 的事务里查一次。
- 怎么验证：测试里把 `content.embeds.follow_b23` 换成桩，记下 `django.db.connection.in_atomic_block` 再抛 `EmbedNotFoundException`；内容编辑带 `X-Autosave: 1` POST `backoffice:article_new`，`body="https://b23.tv/abc"` → 桩记下的是 True。赛事编辑页自动保存只改 `description` 同样是 True。修法方向：字数、纯文本要么在事务外算，要么算的时候不联网（b23 只在渲染页面时查，或发布后交给 worker 回填）。
- 状态：已核对代码（treebeard 4.x `mp_tree.py` 的 `add_child` 带 `@transaction.atomic`；Wagtail 的 `PublishRevisionAction` 没有事务，所以「发布」这一步本身不在锁里）

## 低

### 15-3 草稿预览里的字数和阅读时间是旧的（211 引入）

- 位置：`content/models.py:410-428`、`backoffice/views/articles.py:313-317`（`article_preview` → `draft.serve_preview`）、`content/templates/content/article_page.html:28-29`
- 问题：`body_words`、`body_minutes` 只在 `save()` 里算。自动保存只存修订（`save_revision` 序列化内存里的对象，不走 `save()` 的重算），修订里存的是上一次的数。预览用最新修订的对象，模板读的就是这两个旧值。211 以前是 `facts` 现场算，预览是对的。发布时 `object.save()` 会重算，所以线上页面是对的。
- 失败场景：作者把 200 字的草稿扩写到 5000 字，点「预览草稿」，页头还是「约 1 分钟 · 200 字」。
- 怎么验证：建文章、发布，自动保存一段长正文，GET `article_preview`，页头数字等于发布时的值。
- 状态：已核对代码

### 15-4 撤下内容「当场删」和 worker 正在生成同一页之间有竞争，静态文件会被写回（215 C5 引入）

- 位置：`core/prerender.py:376-412`（`request_removal` / `_remove_now`）、`core/prerender.py:236-262`（`generate`：渲染 → `write_page` → `record.save()`）
- 问题：215 以前，删除是 worker 的任务，和生成任务在同一个 worker 里排队执行，渲染一定先写完、再删。现在 web 在提交后直接删。worker 如果正好在渲染这一页（渲染时页面还是公开的），会在 web 删完以后写出文件，`record.save()` 也把刚删掉的记录按原主键插回去。之后没有任何事件再删它，要等 04:15 的全量 `prerender`（`generate_all` 删不在目标里的页）。
- 失败场景：文章因为评论或修改排了重新生成（30 秒后执行），编辑正好在 worker 渲染这一页的几百毫秒里撤下文章，撤下的文章作为静态文件继续公开，最长约一天。
- 怎么验证：单测里在 `render_html` 和 `write_page` 之间插桩，在两步之间调一次 `drop(path)`，最后文件和记录都还在。修法：`write_page` 前（或 `record.save()` 前）复查这个记录有没有被删，或者生成时也确认对象仍然公开。
- 状态：已核对代码（发生的频率是推测：窗口很窄）

### 15-5 一次「存好了但回答丢了」的自动保存，会让这张编辑页之后的保存全部被当成「别人改过」拒绝（212 D3 和 F2 叠加）

- 位置：`content/drafts.py:29-42`（`stale_base`）、`backoffice/views/articles.py:166-190`、`static/js/autosave.js:236-253`（网络错误时退避重试）
- 问题：隐藏框 `latest_revision` 只能从服务器的回答里更新。一次新建了修订的保存（同一个人 30 分钟以后的第一次保存，或者别人的修订之后的第一次保存），服务器已经提交、回答却在路上丢了，页面重试时带的还是旧编号，于是被 `stale_base` 拒绝。拒绝是 200 JSON 加错误，不会再重试，这张页面之后每次保存都被拒，提示「另一个人在你打开以后改过这篇」，其实是他自己。216 的 B8 只处理了「新建」时回答丢失的情况。
- 失败场景：手机网络下写文章，一次保存的回答丢了；之后打的字一直存不上，按提示刷新页面会丢掉刷新前打的内容。
- 怎么验证：服务端模拟：A 打开编辑页（修订 R1），让 A 的保存生成 R2（`overwritable` 不成立的情况），再用旧的 `latest_revision=R1` 重发同一请求 → 返回 `STALE_MESSAGE`。修法方向：修订带上作者；最新修订是本人在这张页面的上一次保存时（比如按 `X-Autosave-Key` 记下）不算「别人改过」。
- 状态：已核对代码

### 15-6 T7 可以绕过：已结束的赛事还能「发布」回已发布，然后照常审核、编队；设计 9.1 说内战「和赛事一致」，实际不一致

- 位置：`tournaments/services.py:206-217`（`publish` 只拦 CANCELLED）、`tournaments/registration.py:404-414`（`_still_open`）、`docs/design.md` 9.1「状态只能往前走（v7.16，和赛事一致）」
- 问题：213、214 的报告都记过「赛事 `publish` 只拦 CANCELLED」，216 没修。216 加的 T7 守卫只看当前状态，所以 已结束 → POST `tournament_action/<pk>/publish` → 已发布，就能再通过报名、发「报名已通过」的信，正是 T7 要拦的事。后台菜单只对草稿显示「发布」，但地址直接 POST 是通的。
- 怎么验证：`finish` 一个赛事，`services.publish(tournament=…, actor=管理员)` 不报错，之后 `registration.approve` 也不报错。
- 状态：已核对代码

### 15-7 「30 分钟内不再通知全体成员」从安排的时刻算，不从真正发出的时刻算（216 B11）

- 位置：`core/services.py:248-261`（`announcement_problem` 用 `created_at`）、`core/services.py:333-349`（`send_waiting` 只改 `waits_for_publish`，不改时间）
- 问题：定时上线的文章安排「上线时通知全体成员」时就建了 `Broadcast`。上线那一刻真正发出时，`created_at` 还是安排的时间。只要安排早于上线 30 分钟以上，上线后马上就能再发一封给全站。
- 怎么验证：建 `waits_for_publish=True` 的记录，把 `created_at` 改到 2 小时前，调 `send_waiting`，紧接着 `announcement_problem(kind, obj)` 返回 `""`。
- 状态：已核对代码

### 15-8 空草稿清理不看赛事的「简介」，有字的草稿也会被删（216 B8）

- 位置：`core/management/commands/cleanup_old_data.py:140-152`
- 问题：赛事只按 `title=""`、`description=""` 判断，没看 `summary`（简介）。docstring 写的是「Anything with a word in it stays」，设计 13.17 写「标题和正文都空着」。只写了简介、7 天没动的赛事草稿会被删掉。
- 怎么验证：建赛事草稿，只填 `summary`，把 `updated_at` 改到 8 天前，跑 `cleanup_old_data` → 草稿没了。
- 状态：已核对代码

### 15-9 T1 同类的跨字段规则还有一处没成组：改「报名方式」时，人数下限的错误落在 `roster_min` 上，报名方式单独存进去了

- 位置：`backoffice/forms.py:502-513`（`touched = {"roster_min", "registration_mode"}`，错误报在 `roster_min`）、`autosave_together` 的两组都不含 `registration_mode`
- 问题：212 把开始/截止、上下限分成两组，但「整队报名时下限不能超过全站战队人数上限」这条规则跨 `roster_min` 和 `registration_mode` 两个字段，错误只落在 `roster_min`。改的是报名方式时，`registration_mode` 照样存。结果是一个下限超过战队人数上限的整队赛，没有战队能报名。状态栏会显示这条错误，但「其余已保存」已经把报名方式存进去了。这不是 212 引入的，是 T1 那类问题没修完。
- 怎么验证：全站战队上限 6，赛事 `roster_min=8`、个人报名；自动保存只把 `registration_mode` 改成整队 → 响应 `saved` 里有 `registration_mode`。
- 状态：已核对代码

### 15-10 自动保存对 400、413 这类请求错误每 60 秒重试，没有尽头（212 F2）

- 位置：`static/js/autosave.js:222-253`
- 问题：设计 13.17（v7.15）只写了两类：「永久」（401、403、404、登录页）和「再试」（网络错误、5xx、429）。代码把其余所有非 2xx 都归到「再试」。400（比如正文超过 `DATA_UPLOAD_MAX_MEMORY_SIZE` 2.5 MB 时的 `RequestDataTooBig`）、413 永远不会自己好，页面一直写「保存失败，60 秒后重试」，`beforeunload` 也一直拦着离开。
- 怎么验证：读代码：`failed.permanent = response.ok`，对任何非 2xx 都是 false。浏览器里把一个字段改到超过 2.5 MB 即可看到。
- 状态：已核对代码

### 15-11 设计 5.6 说「编辑、删除和发表受同样的限制」，删除其实不受禁言和关闭评论的限制

- 位置：`docs/design.md` 5.6（v7.16 那句）、`comments/services.py:305-320`（`delete` 只拦 `is_hidden`）
- 问题：句首说三者限制一样，冒号后面只展开了编辑。代码里被禁言的人照样能删自己的评论，删除也不占限额。要么改文档的措辞，要么照文档补检查，需要定一下。
- 状态：已核对代码（设计和代码不一致）

### 15-12 字体下载连接固定在解析出的第一个地址，不再像以前那样逐个试（216 C8）

- 位置：`core/fonts/download.py:68-72`
- 问题：`public_addresses(...)[0]` 加 `socket.create_connection((一个地址, port))`。以前 `create_connection(host)` 会把解析出的地址逐个试一遍（IPv6 不通时换 IPv4）。主机先解析出 IPv6、而服务器出 IPv6 不通时，下载直接失败。测试机只有 IPv6、出 IPv4 靠 WARP，两台机器的解析顺序不同。
- 怎么验证：桩 `resolved_addresses` 返回 `[不可达的 IPv6, 可达的 IPv4]` → 现在失败，修前成功。修法：对每个检查过的地址依次尝试。
- 状态：已核对代码（实际影响是推测，要看服务器的网络）

## 查过没问题

- **211**：失败缓存和 Wagtail `get_embed` 读写的是同一行（`get_embed_hash(url)`，没有宽高）；`find_embed` 补 `cache_until: None` 是对的；`?bvid=` 的 `fullmatch` 拦得住加参数；搜索换成 `body_plain` 后匹配结果不变（按词切开，换行不影响）；内战邮件读 `description_plain`；三个回填迁移（迁移里调线上代码，空库时没影响）。
- **212**：`valid_changes` 的分组语义对 `CategoryForm` / `MemberGroupForm` 的单字段组和原来一致；`ContactMethodForm.clean` 的同类型检查（`exclude(pk=None)` 没问题）；F4 的密码框不算文本框，一定会被清空；隐藏的 `latest_revision` 框也不算文本框，B5 的「打过字就不覆盖」碰不到它；B6 的两处新建分支；`stale_base` 在新建文章和旧页面上不误拦。
- **213**：S1 的编辑走 `can_comment`，限流和发表共用计数；S7 拦得住；S2 改位置会清 `is_selected` 并标「分队有变化」，和设计 9.2 一致；S3 的 `finish_past_scrim` 自己先过滤 PUBLISHED，自动结束不受新守卫影响；A8、A9（注销账号判断、清超管、启用时清原因）；T2 的模板和服务层；`delete_account` 不调评论的 `delete`，S7 不会挡住注销。
- **214**：SMTP `timeout` 传进去了；复位残留任务只在 worker 启动时跑一次（字体处理的 `another_face_is_processing` 排除自己，复位后不会死等）；`django.request` 和 `sjtu_ow.errors` 落到标准输出；请求编号只由服务器生成。
- **215**：Caddy 新加的 `/media/fonts/*` 404 和 HSTS（有真 Caddy 探针）；`/healthz` 读 `request.user` 出错时当匿名、仍返回 503；容器健康检查只看状态码，不读细节，不受影响；`state.js` 的 `done` 可以重复调用、请求晚到照样换进去；后台待办里的「worker 没在运行」链给超管。
- **216**：A2 隐藏邮箱：后台模板、`person_label`、`PersonChoiceField` 的 viewer、搜人接口都核过；还显示邮箱的 `teams/admin/assign_captain.html` 和用户列表只给超管看，`/_styleguide/emails` 用的是假数据。A12：头像组件的调用方传的都是 User；`is_active` 在 `PUBLIC_FIELDS` 里，停用和启用都会刷新页面。T7：所有对外入口（审核、批量通过、编队、解散）都经过守卫的函数，取消赛事不会内部调到它们。日历：从没换过地址的人签名和以前一样，195 以前的旧地址在换过以后失效。`AutosaveReplayMiddleware`：钥匙按用户隔离，只有在新建地址拿到 `location` 时才记，D3 的修订号回填在重试以后还能接上。S5 的总分替换：替换的元素在模板里都有，`scrim-split.js` 的 `__wired` 不会重复绑。S8 排队：等待中的表单被换掉后放弃保存，不会死锁。T3 换成 `as_id` 后行为和原来一致；T5、T6、移除队长；B9 的 `_update_errors`；B4 的 `IdChoiceField`；C10 镜像（代码只读，卷归 app，cron 的 `exec` 也是 app）；A5 的设置只影响 allauth 的邮箱页，没有别的改邮箱入口；A6；A10 的事务（默认缓存在同一个库，嵌套时用保存点）；D5 的 `record` / `note_failure` 按 `text_hash` 写，`copy_recent_verdict` 也走 `record`，配额按调用次数算，不受「没写进去」影响；D6 的站内地址判断（`SITE_URL` 后面带 `@`、换域名后缀的都不算站内）；D7、D8。

## 没来得及看

- 所有条目都没在测试机上复现（协调人要求收尾，没开新的运行）。
- 216 的 `IdChoiceField` 用在集合选择框上时，Wagtail 集合树的 `depth` 显示没看；`backoffice.js` F5 的 `response.redirected` 在 fetch 跟随跨源跳转时的表现没看。
- `deploy_ship.sh` 和服务器上的 `Caddyfile.vps` 不在仓库里，C10 交接卷和 C6 HSTS 在正式站上的实际状态只读了报告。
- 各轮新测试本身是否「拆掉就红」，留给块 16。
