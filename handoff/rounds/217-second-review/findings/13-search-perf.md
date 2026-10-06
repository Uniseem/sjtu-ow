# 217 复核 13：搜索、首页、性能

复核人：独立复核代理（只读，不修）。范围：`search/`、`content/home.py` 与首页区块、`core/agenda.py`、sitemap / robots、成员页和战队列表、请求链路上的缓存与中间件。

复现脚本：`findings/13-probe.py`（pytest 文件，断言「问题存在」，另有几条只量查询数和耗时）。在测试机上跑过一次（`bash scripts/remote-check.sh run uv run pytest -q -s -p no:randomly handoff/rounds/217-second-review/findings/13-probe.py`），结果 `16 passed in 41.16s`，退出码 0。断言「问题存在」的几条全绿，即已复现。**注意**：本机只留下输出的最后 120 行（命令接了 `| tail -120`），前面几条测试打印的中间数字（缓存表行数、各次登录的报错原文、13-3 各参数的状态码、sitemap 查询数）没有留下；结论以断言为准，13-3 只打印不断言，所以仍是「已核对代码」。

## 发现

### 13-1 中：默认缓存（DatabaseCache）满 300 条后按键名字母序删掉三分之一，别的限流计数跟着清零，包括 allauth 按账号的登录失败锁定

- **位置**：`sjtu_ow/settings/base.py:124-128`（`default` 是 `DatabaseCache`，没设 `MAX_ENTRIES`，所以是 Django 默认的 300、`CULL_FREQUENCY` 3）；`core/ratelimit.py:22-37`；Django `django/core/cache/backends/db.py:121-132,258-288`（每次 `set`/`add` 先 `COUNT(*)`，超过 300 就 `_cull`：先删过期的，还超过就把**按 `cache_key` 排序的前三分之一**整段删掉，不管有没有过期）
- **问题**：本站所有限流都放在这一个缓存里。键名（带 `:1:` 前缀）排序后，`:1:allauth:rl:…`（登录失败、重置密码、注册）、`:1:moderation-patrol`、`:1:prerender:all-pending`、`:1:sjtu_ow:autosave-made:…`、`:1:sjtu_ow:rl:avatar-upload…`、`…rl:comment…`、`…rl:me-export…`、`…rl:team_apply/team_create…` 都排在 `…rl:search…`、`…rl:state…` 前面。只要活着的键超过 300 条，下一次写缓存就把这些排在前面的整段删掉
- **失败场景**：
  1. 正常高峰：`/_fragments/state/` 每个登录访客每页都调一次，`over_limit("state:<ip>")` 每个 IP 每分钟一个键、活 120 秒，所以 2 分钟内大约 150 个不同 IP（设计 15.1 写的同时在线上限是 200 人；手机网络的 CGNAT 地址也各不相同）就超过 300 条。此后每次写缓存都在清：allauth 的 `login_failed 5/300s/key`（按账号的密码猜测锁定）、每天 5 次的头像上传、每天的建队/申请次数、每小时的导出都会不定期归零
  2. 故意的：攻击者从一段 IPv6 地址（见 13-2）各发一次 `/search/?q=x`，几百个请求就把表撑过 300 条，然后接着猜某个账号的密码，按账号的锁定一直被清掉。按 IP 的 `login_failed 10/m/ip` 在 allauth 那边按 /64 截断，挡得住同一段地址，但挡不住几个段轮换
  3. 副作用：`moderation-patrol` 键被删后，worker 的下一次 beat 会再排一轮 AI 巡查（`moderation/patrol.py:203-212`，设计 5.5.3 是每 `PATROL_MINUTES` 最多一轮），多花接口费用；`prerender:all-pending` 被删，合并全量预渲染的 30 秒窗口失效
- **怎么验证**：`13-probe.py` 的 `test_13_1_cull_wipes_the_daily_avatar_limit`（头像限额用满 → 310 个不同 IP 各搜一次 → 第 7 次上传不再被拒）和 `test_13_1_cull_wipes_allauth_login_failed_lockout`（同一账号错 6 次被锁 → 320 次换地址的搜索 → 第 7 次的报错不再是「次数过多」）。也可以直接在 shell 里看 `django_cache` 表：超过 300 行后 `allauth:rl:login_failed:*` 那几行消失
- **修法方向**（不在本轮做）：限流单独一个缓存别名、把 `MAX_ENTRIES` 设到远大于高峰的量（比如 10 万）且 `CULL_FREQUENCY` 别按字母序整段删；或者限流计数改用自己的表、按过期时间清
- **状态**：已复现（测试机：`test_13_1_cull_wipes_the_daily_avatar_limit` 和 `test_13_1_cull_wipes_allauth_login_failed_lockout` 都通过，即头像限额和 allauth 的按账号锁定在缓存表撑过 300 条后都被清零；中间打印的行数没留下）

### 13-2 低：自己写的按 IP 限流按完整 IPv6 地址算，一个 /64 里换地址就能绕过

- **位置**：`core/ratelimit.py:11-19`（`client_ip` 原样返回 `X-Real-IP`），用在 `search/views.py:23`（每分钟 30 次）、`core/views.py:71`（状态片段 120 次）、`core/views.py:163`（日历 30 次）
- **问题**：allauth 自己的 IP 限流先把 IPv6 截成 /64（`allauth/core/internal/ratelimit.py:123-135` 的 `truncate_ip`），本站的 `over_limit` 不截。家宽、手机、VPS 通常一次给一整个 /64，换地址不花钱
- **失败场景**：一个人从自己的 /64 里每次换一个地址搜索，搜索的 30 次/分钟限额永远不生效（搜索每次都要把全部文章的正文读进 Python 匹配，见下面「查过没问题」里的规模说明）；同时每个地址都在缓存表里留一个键，就是 13-1 的放大器。前提是正式站能用 IPv6 访问（用户自己的反代 `anylocate.cc` 有没有 AAAA 记录没查，属于推测部分）
- **怎么验证**：`13-probe.py` 的 `test_13_2_one_ipv6_slash_64_never_hits_the_search_limit`：同一地址 31 次最后一次是 429；同一 /64 里换 100 个地址，一次 429 都没有
- **状态**：已复现（测试机 `test_13_2_…` 通过：同一地址第 31 次 429，同一 /64 换 100 个地址 0 次 429）；正式站是否能走 IPv6 是推测

### 13-3 低：状态片段的编号参数用 `isdigit()` / `int()`，上标数字和 20 位数字是 500

- **位置**：`teams/slots.py:12-14`、`scrims/slots.py:42-44`、`tournaments/slots.py:102-104`（都是 `argument.isdigit()` 再 `int(argument)`）；`comments/services.py:32-40`（`int(page_pk)` 没有长度限制）
- **问题**：`"²".isdigit()` 是 True，但 `int("²")` 抛 `ValueError`；`article-comments:99999999999999999999` 交给 `ArticlePage` 的 `pk`（`page_ptr` 一对一外键）查，就是 AGENTS 166/167 记的 `OverflowError`。这几处没走 `core.converters.as_id()`。`/_fragments/state/` 是公开接口，不用登录
- **失败场景**：任何人 GET `/_fragments/state/?slots=team-join:²`（或 `scrim-actions:²`、`tournament-actions:²`、`article-comments:99999999999999999999`）→ 500，错误日志被刷。`core/tests/test_garbage_input.py:55` 只喂了 `team-join:abc`
- **怎么验证**：`13-probe.py` 的 `test_13_3_state_fragment_slot_arguments`（打印每种参数的状态码，期望看到 500）
- **状态**：已核对代码（`str.isdigit` 对上标数字为真、`int` 不收，这是 Python 的既定行为；一对一外键溢出 AGENTS 已有记录）

### 13-4 低：搜索的「赛事与内战」先列完全部赛事再列内战，命中 21 场以上赛事时内战一条都不出；已结束的内战不分新旧都搜

- **位置**：`search/services.py:118-125`
- **问题**：`rows = 赛事列表 + 内战列表`，两段各自按更新时间倒序，`_gather` 收满 21 条就停。设计 13.16 是「每类最多 20 条，按更新时间倒序」，表里这一类写的是「已发布的内战活动（含最近结束的）」，内战列表用的是 `public_scrims()`（结束 30 天内，`scrims/services.py:43-53`），搜索却是 `status__in=[PUBLISHED, FINISHED]`，几年前结束的也搜得到
- **失败场景**：搜「秋季」，历年秋季赛超过 20 场时，昨天刚发布的「秋季内战」不出现；两年前的内战作为结果出现，而列表页早就不列了
- **怎么验证**：`13-probe.py` 的 `test_13_5_events_list_tournaments_first_and_all_old_scrims`
- **状态**：已复现（测试机该条通过：21 场赛事命中时新内战不在结果里，400 天前结束的内战被搜到）

### 13-5 低：搜索摘录在 casefold 改变长度的字符后面截错位置

- **位置**：`search/services.py:55-69`
- **问题**：在 `text.casefold()` 里找到的位置直接拿去切原文。`ß`→`ss`、`ﬁ`→`fi`、`İ`→`i̇` 这类字符会让折叠后的文字变长，命中词前面每有一个，位置就往后偏一格
- **失败场景**：正文前面有几十个这种字符（德文、合字、土耳其文的名字），摘录切到命中词后面，读者看不到为什么命中。社团内容里少见，所以是低
- **怎么验证**：`13-probe.py` 的 `test_13_4_excerpt_misses_the_hit_after_length_changing_folds`（`"ß"*60 + "龙刃" + …`，摘录里没有「龙刃」）
- **状态**：已复现。测试机输出：`摘录：'…。。。。（全是句号）…'`，命中的「龙刃」不在摘录里

### 13-6 低：首页置顶文章只看 `live`、不看 `public()`，设了浏览限制的文章照样出现在预渲染首页

- **位置**：`content/models.py:202-208`（`if rel.article.live`）；后台置顶表单的候选是 `ArticlePage.objects.live()`（210 复核 B4 提到的 `backoffice/forms.py` 那个字段）
- **问题**：首页别的区块（`content/home.py:30,43`）、相关文章、搜索、sitemap 都用了 `.public()`，置顶这条没有
- **失败场景**：超管在 `/wagtail/` 给一篇已置顶的文章加了密码或登录限制，标题、摘要、封面、作者仍然写在所有人都能拿到的静态首页上。只有超管能设浏览限制，所以是低
- **怎么验证**：置顶一篇文章，给它建一条 `PageViewRestriction`，未登录 GET `/`，页面里还有它的标题
- **状态**：已核对代码

### 13-7 低：成员页每个可见分组单独查一次组员

- **位置**：`members/services.py:79-92`（`for group in …: group.memberships.select_related("user")…`）
- **问题**：查询数随可见分组数线性增长。`core/tests/test_chapter15_audit.py:121` 的守卫只建了一个分组，测不出来
- **失败场景**：分组少（几个到十几个）时影响很小；带参数的筛选页（`/members/?role=tank`）是实时渲染，也照样跑这段
- **怎么验证**：`13-probe.py` 的 `test_measure_member_groups`
- **状态**：已复现。测试机输出：`/members/ 1 个分组 → 7 次 | 6 个分组 → 12 次`

### 13-8 中：成员页不分页，设计规模（5000 人）下实时渲染要 1–2 秒、HTML 4.3 MB；带任意查询参数就绕过预渲染

- **位置**：`members/views.py:9-31`、`members/services.py:52-95`（`showcase()` 每次把全部成员、头像、游戏 ID、战队、分组读出来；筛选是在 Python 里过滤全部成员之后）、`members/templates/members/index.html:25-89`（分组名片 + 「全部成员」两份列表，没有分页）
- **问题**：设计 15.1 规模假设注册用户 5000 人以内，实时渲染页 p95 300 ms。`/members/?role=…`、`?free=1` 按设计 4.7 是实时渲染；而且 Caddy 只在没有查询参数时给静态文件，`/members/?x=1` 这样随便加个参数也会落到 Django 实时渲染整页。这个地址没有限流
- **失败场景**：成员到两三千人以后，任何人连续请求 `/members/?a=1`、`?a=2`……，每次占一个 gunicorn 进程 1–2 秒（正式站 5 个进程），几个并发就能把实时页面全部拖慢。不加参数的 `/members/` 是预渲染的，但静态文件本身 4.3 MB（未压缩），手机网络下很重（设计 15.1「服务器在海外，页面要保持轻量」；300 KB 的预算只写了首页）
- **怎么验证**：`13-probe.py` 的 `test_measure_member_page_at_scale`。测试机输出（每项 3 次里最快的一次，测试客户端，不含网络）：

```
  500 人 /members/                200 最快 171 ms，HTML 447 KB
  500 人 /members/?role=tank      200 最快 69 ms，HTML 158 KB
  2000 人 /members/                200 最快 576 ms，HTML 1749 KB
  2000 人 /members/?role=tank      200 最快 297 ms，HTML 593 KB
  5000 人 /members/                200 最快 1928 ms，HTML 4359 KB
  5000 人 /members/?role=tank      200 最快 999 ms，HTML 1463 KB
```

  （测试用的成员都没有自己的头像，走默认头像池；有头像的人多了只会更慢）
- **状态**：已复现（量出来的数）。正式站现在的人数远没到 2000，所以是规模到了才会出问题；要不要分页、筛选页要不要限流，需要用户拍板

## 查过没问题

- **搜索的转义与注入**：匹配在 Python 里做子串（`search/services.py:50-52`），不拼 SQL，`%`、`_` 没有通配含义；搜索词、标题、摘录在模板里都自动转义（`search/templates/search/results.html`，`empty_state.html` 也没有 `|safe`）；`|add:query` 左边是中文字符串，不会被当成数字相加
- **搜索的范围**：文章 `.live().public()`（草稿、撤下、有浏览限制的都不出）；`body_plain` 只在 `save()` 带上 `body` 时重算，草稿走 `save_revision`（`update_fields` 不含 `body`），所以草稿正文不会写进已发布文章的 `body_plain`（`content/models.py:410-427`、`content/drafts.py`）；新建的文章 `live=False`。赛事排除草稿和取消；战队排除已解散；成员只按昵称匹配、摘录是公开的个人宣言、范围是 `joined_users()`，和成员页一致；不搜邮箱、游戏 ID、联系方式
- **超长搜索词**：先截 50 字，最多 5 个词；输入框 `maxlength="50"`
- **搜索的 N+1**：测试机量过，命中赛事、内战、成员时 3 份和 10 份都是 21 次查询；每条命中的地址都不查库（`get_url(request)` 带请求、赛事和内战地址是拼的、`member_url` 是拼的、`is_recruiting` 是字段）；结果数封顶 20
- **搜索的规模**：每次搜索把全部已发布文章整行（含 `body` 原文）读进内存匹配，设计 13.16 明确接受「几百篇以内」。没有超出设计假设，不算缺陷；测试机量过：每篇约 3000 字，100 篇时搜不到的词最快 14 ms，300 篇时 28 ms
- **我的安排**（`core/agenda.py`）：测试机量过，状态片段（account、messages、my-agenda）3 条报名 25 次查询、10 条 26 次（多的一次是缓存过期重写，不随条数涨）；每次片段有一次 INSERT/UPDATE 写 `django_cache`（限流计数），这是 13-1 的来源。四次固定查询（内战报名、哪些内战已分队、整队名单、散人），不随条数增长；草稿、取消的赛事和内战不进；内战开始后 6 小时内还列着，和设计细节 7 一致
- **首页数据**（`content/home.py`）：资讯、公告、战队都有上限和 `select_related`；近期内战 `upcoming_scrims` 有 `limit`；报名数一次 `signup_totals`；置顶最多 3 篇
- **sitemap / robots**（`content/views.py`）：只列公开文章和普通页面、未解散战队、`listed_tournaments`（不含草稿和取消）、`public_scrims`；`get_full_url(request)` 带请求，不会每篇查一次站点根路径；robots 禁止的目录覆盖设计 13.14 要求的全部
- **战队列表**：`open_teams` 一次查询带人数；三个筛选计数 `team_totals` 一次聚合；`recruiting_roles__contains` 的三个位置代码互不为子串
- **中间件**：`RequestIDMiddleware`、`LoggedInHintCookieMiddleware` 不碰库；`PrerenderMissMiddleware` 只对未登录、无查询参数、200 的 HTML 才读一次缓存里的目标表；`HeldLettersMiddleware` 只管登录后的 POST；`AutosaveReplayMiddleware` 只管自动保存请求
- **全站设置**：`fonts` 和 `build_seo` 调 `SiteSettings.load(request)`，Wagtail 把它缓存在请求上，一个请求只查一次
- **文章列表**：`/news/` 分页（`Paginator`），坏的 `page` 参数由 `get_page` 兜住

## 顺带看到（不在本块，交给 08 预渲染）

- 推测：`core/prerender.py:330-370` 的 `request_page` 在「已经排过」时只更新 `requested_at`，而 `generate()` 在渲染**结束后**把 `requested_at` 设回 None（`core/prerender.py:246,259`）。渲染进行中提交的改动会被当成「已经排过」吞掉，渲染又是在改动之前读的数据，那次改动要等下一次请求或夜间全量才上静态页。没验证

## 没来得及看

- 测试机这次的输出只留下最后 120 行：sitemap 3 份对 10 份的查询数、13-3 各参数的状态码没有看到。13-3 要在修的那一轮单独确认是不是 500
- 状态片段里每个槽位用 `render_to_string(..., request=request)` 渲染，会把全部上下文处理器（含 `build_seo` 生成默认分享图的缩略图地址）重跑一遍，一次最多 12 个槽位；没有量过它对 150 ms 目标的影响
- 正式站的 `django_cache` 现在有多少行、高峰时有多少（能直接说明 13-1 在正式站上是否已经在发生）
