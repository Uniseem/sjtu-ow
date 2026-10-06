# 217 复核 16：测试质量

复核人：子代理 16。只记录，不改代码和测试。

## 先说明：这次实际在测试机上跑成了什么

- **新守卫普查只跑了一小段**：`16-sweep.sh`（210 的 `mutate_guards.py` 加 `--resume`）在锁里跑，基线 4 份全绿（`2076 passed, 2 deselected`，每份约 5 分 20 秒），硬守卫 12 个里跑完 4 个，**4 个全被抓到**：`accounts/services.py:840 reactivate_account if is_deleted(user)`、`backoffice/forms.py:78 IdChoiceField.to_python`、`comments/services.py:286 edit if problems`、`comments/services.py:312 delete if comment.is_hidden`。后面排队的复核代理有十来个，我这一跑要占锁 30 多分钟，就停掉了，按 AGENTS「硬规则 7」改到单独的工作树 `/srv/sjtu-ow-check/r217-16`（锁外）跑合并版 `16-sweep.py`。它刚开始跑基线，协调方就通知收尾，也停掉了。**没有拿到结果**。
- `16-mutate.py`（40 个手挑的变异）和 `16-order.py`（顺序依赖的复现）都是还在排队时撤掉的，**没有跑**。
- 所以下面的条目全部是「已核对代码」或「推测」，没有一条是「已复现」。脚本都留在 `findings/`，218 起可以直接跑：
  - `16-sweep.py`：基线只跑一次，依次跑 210 之后新出现的 12 个硬守卫、**181 之后新出现的 29 个软守卫（其中 backoffice 下的全都从没扫过：181 时还没有 backoffice/）**，再加 `16-mutate.py` 的 40 个手挑变异，共 81 个。`--list` 列清单。要在锁外的工作树里用 `nice -n 10 … --workers 3` 跑（测试机全量单份 5 分多钟，估计 1–1.5 小时）
  - `16-order.py`：在临时副本里复现 16-1，约 1 分钟，可以走 `remote-check.sh run`
  - 测试机上留了工作树 `/srv/sjtu-ow-check/r217-16`（检出的是 `f49adcb` 快照），用完 `git -C /srv/sjtu-ow-check/repo worktree remove --force /srv/sjtu-ow-check/r217-16` 删掉

## 发现

### 16-1 中：transaction 测试提交的缓存行在测试之间串味，「worker 停了」那条测试顺序一变就红

- **位置**：`core/tests/test_pages.py:50`（`test_healthz_returns_200_when_database_is_busy`，`transaction=True`，用了 `worker_heartbeat` fixture）→ `core/tests/test_admin_functions.py:466`（`test_the_owner_hears_when_the_worker_is_down`，断言「心跳缺失」）；`conftest.py`（没有清 `django_cache` 表）
- **问题**：`transaction=True` 的测试结束时 Django 只 flush 模型表，`django_cache` 不是模型，不会被清；`pytest.ini` 又是 `--reuse-db`，所以写进去的行连**下一次** pytest 都看得到。busy 测试写的心跳 `timeout=WORKER_HEARTBEAT_STALE_SECONDS*2` = 240 秒（按真实时间）。240 秒内跑 `test_the_owner_hears_when_the_worker_is_down` 就看到「心跳过期」或者根本有心跳，断言的「心跳缺失」不成立。同一次运行里因为文件按字母排（admin_functions 在 pages 前面）碰不上；但 `scripts/pytest-shards.sh` 的分片工作树跨两次检查保留同一个 `data/test.sqlite3`，两条测试按编号轮流分片时有大约四分之一的机会分进同一片，两次检查隔不到 4 分钟（今天十几个代理排队跑，正是这种情况）就会偶发红。本机连着跑 `pytest core/tests/test_pages.py` 再跑 `pytest core/tests/test_admin_functions.py` 也一样
- **同类风险**：限流计数也存在 `django_cache`（`core/ratelimit.py`），`conftest.py` 又把 `ratelimit.time` 固定在同一个时间桶，transaction 测试里打到按 IP 计数的地址（`state:`、`search:`、`calendar:`，测试客户端都是 127.0.0.1）的次数会留给后面的测试；allauth 的限流（`signup` 20/m/ip 等）也在这张表里。216 的 `test_concurrent_hits_are_all_counted` 自己注意到了（「a re-run would count on from 8」），手动删了自己的键；其它 transaction 测试没有
- **失败场景**：CI 或 `remote-check.sh` 偶发红一条和改动无关的测试，下次重跑又绿——最容易被当成「机器忙」放过去
- **怎么验证**：`bash scripts/remote-check.sh run .venv/bin/python handoff/rounds/217-second-review/findings/16-order.py`：对照（单跑）应绿；同一次 pytest 先 busy 后 down 应红；两次 pytest（--reuse-db）应红。修法建议：conftest 加一个 autouse fixture，transaction 测试结束后 `cache.clear()`（或测试开始前清）
- **状态**：已核对代码（复现脚本写好了，排队时撤掉，没跑）

### 16-2 中：没有一条测试看前台响应真的带的是严格 CSP；把后台的宽松策略套到全站不会红

- **位置**：`core/middleware.py:61`（`if request.path.startswith((prefix, wagtail)): response._csp_config = ADMIN_CSP`，`ADMIN_CSP` 的 script-src 带 `'unsafe-inline' 'unsafe-eval'`）；测试 `core/tests/test_chapter15_audit.py:490-506` 只读 `settings.SECURE_CSP` 这个字典，`backoffice/tests/test_backoffice.py:126-131` 只断言后台**有** `'unsafe-inline'`，`core/tests/test_letters.py:227` 只看邮件样张的覆盖
- **问题**：grep 全部测试，没有一条对前台页面（首页、文章、`/_fragments/state/`、404/500 错误页）读 `response["Content-Security-Policy"]` 并断言没有 `unsafe-inline`。中间件的路径判断写宽了（比如改成 `startswith("/a")`、或者有人给前台某个视图加 `csp_override`），设置字典照样严格，测试全绿，访客拿到的却是允许内联脚本和 eval 的策略。预渲染页由 Caddy 发头，那边有 `test_latency.py:45` 一字不差比对，不受影响；受影响的是 Django 直接回的页面（登录、个人中心、后台以外的表单页、错误页）
- **怎么验证**：`16-mutate.py` 的 C1（把那行条件换成 `True`）。预计 survived
- **状态**：已核对代码（推测会 survived，没跑）

### 16-3 中：211–216 又加了约 10 条只对 JS 源码做子串断言的「守卫」，它们的变异「抓到」是同义反复

- **位置**：`core/tests/test_autosave_js.py`（212 F2，4 条，文件头自己写明「cannot catch logic errors」）、`backoffice/tests/test_216_backoffice_edges.py:82-105`（B5、F9）、`:375`（F5）、`scrims/tests/test_216_split_edges.py`（S8 两条）、`core/tests/test_prerender.py:~265-274`（215 F1，`state.js`）
- **问题**：这些测试断言的就是 `mutate.py` 改掉的那串字（`RETRY_MAX = 60000`、`.then(done, done)`、`if (!response.ok || response.redirected) {`……），所以 212/215/216 报告里「ok 改坏后红了」只证明字还在，证明不了行为。逻辑写反（比如 B5 的 `!==` 写成 `===`、F1 的 8 秒兜底在 `fill()` 之后才挂、S8 的 `queuedBehind` 返回了错的保存）全都抓不到。210 已记 F8（同一类，当时 4 处），这几轮数量翻了一倍多；真正的行为守卫 `journey.py` 不在 CI 里，也不走「保存途中又打字」（B5）、「断网」（F1）、「会话失效时选图」（F5）、「两张表同时保存」（S8）这些路径。另外 212 D3 的修订号要靠 `autosave.js` 把回答里的 `latest_revision` 写回隐藏框，这一步除了 `journey.py admin` 碰巧走到发布以外没有任何测试
- **失败场景**：重构 autosave.js 时保留了这些字符串但改错了逻辑，CI 全绿
- **怎么验证**：做一处只改逻辑、不碰被断言字符串的变异，比如把 `state.js` 里 `start()` 的 `fill();` 挪进 `setTimeout` 的回调、或者把 autosave.js 回填 `data.values` 的整个 `forEach` 包进 `if (false)`（`latest_revision` 不再回填），跑 `core/tests` 和 `backoffice/tests`，预计全绿。根本办法是把 `journey.py` 里走自动保存的几步放进 CI，或者给 autosave.js 写一个能在 Node 里跑的小测试
- **状态**：已核对代码

### 16-4 低：预渲染的秘密标记只测了三个里的一个

- **位置**：`core/prerender.py:29-33`（`csrfmiddlewaretoken`、`csrf_token`、`sessionid`）；测试 `core/tests/test_prerender.py:463` 只取 `sorted(SECRET_MARKERS)[0]`，即 `csrf_token`
- **问题**：从元组里删掉 `csrfmiddlewaretoken` 或 `sessionid`，测试照绿。`csrfmiddlewaretoken` 是最该拦的那个（匿名页上出现表单令牌）；目前靠第一道「响应带 Cookie 就拒」兜着（渲染出令牌时一般会设 csrftoken Cookie），所以是纵深防御少了一层的测试，不是现成的洞
- **怎么验证**：`16-mutate.py` 的 C3、C4。修法：测试对三个标记逐个参数化
- **状态**：已核对代码

### 16-5 低：allauth 的限流配置没有任何测试钉住数字

- **位置**：`sjtu_ow/settings/base.py:261-271` `ACCOUNT_RATE_LIMITS`；`core/tests/test_chapter15_audit.py:527` 的「限流和设计一致」只列了本站自己的常量（评论、点赞、搜索、状态片段、建队、申请）
- **问题**：`login_failed` 的「每 IP 10 次」有行为测试（`core/tests/test_client_ip.py:51`），但「同一账号 300 秒 5 次」（防对单个账号撞密码）、`signup`、`reset_password`、`confirm_email`、`change_password`、`reauthenticate` 的数字改大或删掉都不会红。`reset_password` 每 key 5 次/分钟和 `confirm_email` 10 秒 1 次是防发信轰炸的（设计 15.2）
- **怎么验证**：`16-mutate.py` 的 R1–R4。修法：在 `test_the_rate_limits_match_the_design` 里断言这个字典等于设计里的表，再给 `5/300s/key` 补一条行为测试
- **状态**：已核对代码

### 16-6 低：除了退订以外，没有测试证明 POST 真的要 CSRF 令牌

- **位置**：`core/views.py:38`（healthz）、`:176`（退订）两处 `@csrf_exempt`；测试里只有 `core/tests/test_announcements.py:285` 一处 `Client(enforce_csrf_checks=True)`，用来证明退订**不**要令牌
- **问题**：Django 测试客户端默认不查 CSRF。以后有人给评论、申请入队、注销这类视图加 `@csrf_exempt`（比如为了 HTMX 图省事），没有测试会红。去掉 `CsrfViewMiddleware` 倒是会被 `test_prerender.py:287` 顺带抓到（它断言响应里有 csrftoken Cookie），但那是巧合
- **修法建议**：一条结构测试：遍历 URLconf，`csrf_exempt` 的视图集合必须正好是 {healthz, 退订}；再挑一个写操作用 `enforce_csrf_checks=True` 断言 403
- **状态**：已核对代码

### 16-7 低：「验证过邮箱自动进投稿者」会掩盖赛事/内战管理员自己的传图权限

- **位置**：`content/services.py:463-464`（给赛事管理员、内战管理员单独授「投稿图片」的 add/choose，注释说就是因为他们「不一定在投稿者里」）；测试里的管理员几乎都用 `accounts/tests/test_onboarding.py:46` 的 `_user()` 建，它会建一条**已验证**邮箱，`sync_submitter_group` 随即把人放进投稿者
- **问题**：删掉这两行，用 `_user()` 建的管理员照样能传图（投稿者有同样的权限），推测没有测试红。真实场景是没验证邮箱、或者投稿功能对他所在的组关掉了的管理员：写赛事说明时插图 403。`backoffice/tests/test_door.py:68` 的 `_with_permission` 已经注意到这一点（「No verified address, so not even 投稿者」），但只用在门口测试里
- **怎么验证**：`16-mutate.py` 的 G1（同理 G2：认证作者的栏目权限）
- **状态**：推测

### 16-8 低：211 的「保存时算好」字段只钉住了赛事一种

- **位置**：`content/models.py:414`、`scrims/models.py:120`、`tournaments/models.py:127` 的 `if update_fields is None or "description"/"body" in update_fields` 以及随后把派生字段并进 `update_fields` 的几行；测试 `search/tests/test_search.py:176`（`test_the_stored_plain_text_follows_saved_descriptions_only`）只用 `Tournament`
- **问题**：自动保存走 `save(update_fields=[改了的字段])`。内战的说明、文章正文只改这一个字段时派生字段（`description_plain`、`body_plain/words/minutes`）有没有跟着重算并落库，没有对应测试；那两段（scrims、content）删掉后搜索和字数会悄悄停在旧值。文章正文的自动保存实际走的是 Wagtail 修订，所以 content 那段可能是等价的，内战那段不是（`backoffice/views/events.py` 的内战编辑走 `save_valid_fields`）
- **怎么验证**：`16-mutate.py` 的 D10a–D10e
- **状态**：已核对代码（内战）/ 推测（文章）

### 16-9 低：212 D3 的修订号检查有一个入口没测：资讯栏目介绍的自动保存

- **位置**：`backoffice/views/pages.py:201-205`（`index_intro` 里 `if autosave.wants(request) and stale:`）；测试 `content/tests/test_drafts.py:331` 测了网站页面和首页置顶，没测栏目介绍。212 `mutate.py` 的 D3 改的是 `content/drafts.py` 里 `stale_base` 本身，一处改坏所有入口一起红，所以看不出单个入口漏掉
- **问题**：这一处的检查删掉，两个人同时改栏目介绍会互相覆盖，没有测试红。三个模板里的隐藏框 `latest_revision`（`page_edit.html:8`、`draft_form.html:12`、`article_edit.html:8`）也只有文章和网站页面的读到过（`_opened_revision`），`draft_form.html` 删掉隐藏框以后表单不带修订号，`stale_base` 对空值放行，保护整个失效
- **怎么验证**：`16-mutate.py` 的 D3a、D3c（D3b 预计被 `test_plain_pages_and_pins_refuse_a_stale_base` 抓到；置顶那段测试是直接 POST `base - 1`，不读页面，所以 D3c 可能 survived）
- **状态**：已核对代码

### 16-10 低：211 的失效短链缓存，「查到以后清掉失败行的到期时间」没有测试

- **位置**：`content/embeds.py:130`（`"cache_until": None`）、`content/embeds.py:42`（`?bvid=` 过 BV 校验）、`content/markdown.py:76`（失败也记缓存）
- **问题**：`content/tests/test_markdown.py` 211 补的测试覆盖了「失败记一小时」（monkeypatch `follow_b23`），但「一小时后重试成功，失败行的 `cache_until` 要清成 None」这一步删掉后，成功的结果会在下一次渲染时又被当成过期、再去联网；推测没有测试走「先失败后成功」这条路
- **怎么验证**：`16-mutate.py` 的 D1a、D1b、F10
- **状态**：推测

### 16-11 低：隐私过滤大多是查询里的 filter 或模板条件，守卫普查看不见

- **位置**：`accounts/services.py:877`（后台用户页的联系方式）、`tournaments/review_admin.py:42`、`scrims/split_admin.py:71`、`tournaments/registration.py:502 visible_to`、`members/services.py:23,80,141`、`scrims/services.py:81`、`search/services.py:89,117,120,149`、`teams/templates/teams/slots/join.html`、`comments/services.py:180`、`comments/templates/comments/_item.html:6`、`_reply.html:5`
- **问题**：`mutate_guards.py` 只认「if 条件: 拒绝」，`filter(is_visible=True)`、`exclude(status=DRAFT)`、`{% elif comment.is_hidden and not can_moderate %}` 这类过滤从 042 起的四次普查都没碰过。逐个读测试，大多数有对应测试（成员页隐藏分组、搜索排除草稿和解散战队、队内联系方式只给队员、隐藏评论），但没有机械地核过每一处。评论的隐藏是两道（查询 + 模板），各删一道可能都不红（等价），需要分别判断
- **怎么验证**：`16-mutate.py` 的 P1–P17。建议 218 把这类过滤加进普查的模式（或固定维护这份手挑清单）
- **状态**：推测（逐条结果没拿到）

### 16-12 低：`healthz` 在数据库坏了、又带着登录会话时会不会 500，没有测试

- **位置**：`core/views.py:58-63` `_sees_health_details` 的 `try/except`（215 C9）；`core/tests/test_pages.py:78` 的只读库测试用的是匿名客户端
- **问题**：匿名请求不读库，`request.user` 不会抛；只有带会话 Cookie（比如站长自己开着 `/healthz`）时才读库。删掉 try 不会红
- **怎么验证**：`16-mutate.py` 的 C5
- **状态**：推测

## 查过没问题

- **时间相关的偶发**：测试里没有 `date.today()`、按「今天/明天」字面断言的地方；限流的时间桶在 `conftest.py` 固定；日程测试用的是 ±天，不碰零点
- **只用超管测权限**：211–216 新加的权限测试都用了非超管（215 C9 有 `is_staff` 的内容编辑、216 A2 用内容编辑、216 B10 用只有 add 的账号、213 B3 用两个投稿者）；后台门口的 `test_door.py` 刻意用没验证邮箱的账号避开投稿者
- **mock 掉被测对象**：`teams` 限流测试 mock 的是 `over_limit` 的结果，数字另有设计一致测试、`over_limit` 本身另有测试；`search` 的 monkeypatch 是为了证明不再渲染；预渲染三道闸的测试 mock 的是 `Client.get` 的返回，闸本身是真的
- **限流**：头像上传（`accounts/tests/test_avatar_upload.py:247`）、导出、注销、评论、点赞、编辑评论、搜索、状态片段、日历、建队、申请都有行为测试
- **211 的迁移测试守卫**（`conftest.py` 的 `_migration_tests_leave_the_schema_at_latest`）：逻辑对，用导入时绑定的 `MigrationExecutor` 避开了被 monkeypatch 的情况
- **210 普查之后新出现的 12 个硬守卫**：除了上面跑过的 4 个，其余 8 个都在 213/216 的 `mutate.py` 里逐个改坏过（scrim publish/finish、transfer_captain、remove_member 队长、`_still_open` 两处），只有 `core/net.py:47` 的 `if not addresses or any(...)` 整体没被单独改过（216 C8 改的是 `is_internal` 里的一半）
- **216 T7 的 `_still_open`**：四个调用点（通过、驳回、编队、拆队）各有参数化测试，不只是函数本身

## 没来得及看

- 81 个变异的实际结果（`16-sweep.py`，见开头）——这是本块最主要的产出，218 先跑它
- 181 之后新出现的 29 个软守卫逐条读测试（清单：`python3 handoff/rounds/217-second-review/findings/16-sweep.py --list`）
- 205/198 的 `mutate.py` 覆盖面（210 也没看）
- `journey.py` 三条旅程实际断言了什么、哪些只是「没报错」
- 其它 transaction 测试（`core/tests/test_held_letters.py`、`scrims/tests/test_scrims.py:318,509`、`tournaments/tests/test_concurrency.py`）具体留下了哪些按 IP 计数的缓存行（16-1 的同类风险）
