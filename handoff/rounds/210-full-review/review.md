# 210 全站代码与功能复核（独立复核的结论）

**结论：能继续用，但有 1 条高（D1：一篇带失效 b23 短链的文章能拖慢全站搜索和预渲染，任何验证过邮箱的成员都能做到）要先修；15 条中等严重度的缺陷值得尽快修，另有 50 多条低严重度的。** 全部是静态复核（七个独立的复核代理只读通读代码、测试和设计，再由我核对），**除「已核对」标记的以外，都没有在测试机上重现**——用户 10-06 说额度不够，先写进文档；重现留给修的那一轮，每条都写了怎么验。

基线（真实跑过，见 `report.md`）：测试机整组检查全绿（1904 条测试），三条浏览器旅程（新人第一晚、全部地址、干部那一晚）全部走通，GitHub CI 最近 5 次全绿。守卫普查（`mutate_guards.py`，加上了 `backoffice`，299 个硬守卫）在测试机 `/srv/sjtu-ow-check/sweep/` 后台跑着，结果落在那里的 `handoff/rounds/210-full-review/results.jsonl`，**还没取回**（见 `report.md`「普查」）。

内容与 AI 审核那份报告在第一次提交（`86cddb1`）之后才到，写在下面「补充」一节（编号 D），没有并进前面的表。

编号：A 账号，T 战队赛事，S 内战评论，C 核心运维，F 前端，B 后台，D 内容与 AI 审核。「已核对」= 我自己把代码路径或源码读过一遍确认；「未重现」= 只有代理的静态结论（两个代理独立报出同一条的，注明）。

## 中（建议下一轮就修）

| # | 问题 | 出处 | 场景 | 怎么验 | 状态 |
|---|---|---|---|---|---|
| T1 / B1 | **赛事自动保存的跨字段规则落错字段**：`TournamentForm.clean` 把「报名开始 ≥ 截止」固定报在 `registration_closes_at`、「下限 > 上限」固定报在 `roster_max`；改的是另一项（开始时间、下限）时 `valid_changes` 照样放行。新建/复制路径 `obj.save()` 没捕获 → `IntegrityError` 500，`autosave.js` 每 5 秒重试；编辑路径 `save_valid_fields` 捕获后返回 `saved=[]`，**同一次请求里的其它合法改动也没存，而页面写「有 1 项没存（其余已保存）」、错误挂在用户没碰的字段上**。`autosave_together` 四行是死代码（只在 `NON_FIELD_ERRORS` 时起作用，而 `validate_constraints` 对已报错字段跳过）。`ScrimForm` 有没有同类规则没看 | `backoffice/forms.py:436-460`、`backoffice/views/events.py:51-67`、`core/autosave.py:69-82,95-111`、`static/js/autosave.js:267-271` | 赛事管理员在「复制赛事」页先把报名开始改到截止之后 → 500 无限重试；编辑页把下限 5 改成 7（上限 6）→ 状态栏说其余已保存，其实下限和同时改的简介都没存，刷新后才发现 | 带 `X-Autosave: 1` POST `tournaments:copy`，`registration_opens_at` = 截止 + 1 天 → 现在 500；POST `tournaments:edit`，`roster_min = roster_max + 1` → 现在 `saved == []`。`core/tests/test_autosave_events.py:148,167` 只测了错误落点就是改动项的方向 | 两个代理独立报出；已核对代码路径，未重现 |
| A1 | **联系方式类型改成已有的类型 → 500**：表单没有 `user` 字段，`UniqueConstraint(user, type)` 在 `form.is_valid()` 里被跳过；`ContactMethodForm.save` 里 `full_clean()` 再抛 `ValidationError`，自动保存分支（`save_valid_fields`）没有 `try`，非自动保存分支有 | `accounts/views.py:298-303`、`accounts/forms.py:226-233`、`core/autosave.py:86-93` | 成员有 QQ 和微信两条，编辑 QQ 那条把类型改成微信 → 500，`autosave.js` 每 5 秒重试一次 | 两条不同类型，带 `X-Autosave: 1` POST `/me/contacts/<pk>/` 改成另一条的类型 | 已核对代码路径，未重现 |
| A2 | **内容编辑能看到并按子串搜索全体成员的邮箱**：成员分组编辑页（门是 `members.change_membergroup`，内容编辑有）的搜人接口按 `email__icontains` 搜、列表和 JSON 都打印邮箱；文章作者下拉也列全部邮箱。设计 4.1 只给超管「用户」，个人中心「账号安全」页写着「邮箱只有你自己和超级管理员能看到」 | `backoffice/views/members.py:369-427,482-493`、`members/services.py:218-231`、`backoffice/forms.py:150`、`templates/me/security.html:15` | 内容编辑搜 `@`、`@sjtu`……每次 10 条，逐步导出全体邮箱 | 内容编辑 GET `/admin/member-groups/<pk>/people/?q=@` | 已核对（`members/tests/test_members.py:156` 反而把显示邮箱固化成期望）。要么改文案和设计，要么人选器只显示昵称——**要用户拍板** |
| S1 | **被禁言的人仍能「编辑」旧评论、编辑不限流**：`comments/services.edit` 只查本人和可见，不查 `can_comment`（功能权限、文章是否关闭评论）；视图 `edit` 没有 `_too_many` | `comments/services.py:279-296`、`comments/views.py:157-165`、`comments/templates/comments/_own.html:1` | 站长禁言某人，此人把旧评论改成广告，连改几十次（每次重新送审、重排静态页） | 建禁言规则后 POST `/comments/<pk>/edit/`，现在 200 且正文变了；`test_anonymous_and_gated_users_cannot_post` 只测 `create` | 已核对代码路径，未重现 |
| S2 | **分队后玩家改「能打的位置」，分队结果不更新也不提示**：`sign_up` 只在换游戏 ID 时清 placement 并标 `roster_changed_at`，只改 roles 什么都不做；缓冲区的人换 ID 被清掉 `is_selected` 也不标记 | `scrims/services.py:179-192`、设计 9.2 | 甲被分到 A 队坦克，截止前改成只打输出；分队页和复制文字仍写「坦克：甲」，没有「分队有变化」 | 照 `test_changing_the_game_id_clears_the_placement` 写一条只改 roles 的，断言 `teams_are_stale(scrim)` | 已核对代码路径，未重现 |
| T2 | **队长能把队长转给已停用的账号**，战队随即进入「队长停用」死锁（只能申请不到、等超管指定）；管理页对标着「账号已停用」的成员也显示「转让队长」。`assign_captain` 有这道检查（179 补的），`transfer_captain` 没有 | `teams/services.py:459-482`、`teams/templates/teams/manage.html:76-84` | 队长误点停用成员那行的「转让」 | `transfer_captain(new_captain=停用成员)` 期望 `TeamError` | 已核对代码路径，未重现 |
| C1 | **SMTP 连接没有超时**：`build_smtp_backend` 不传 `timeout`，没有 `EMAIL_TIMEOUT`；worker 单线程，一次卡住的发信让它永久停摆，而心跳线程照写、`/healthz` 照绿，worker 容器没有 healthcheck | `core/mail.py:188-202`、`core/worker.py:54-73` | 邮件服务商 TLS 握手后不响应 → 验证码、提醒、预渲染全停，只能人工重启 worker | 用 `nc -l` 只 accept 不回应做 SMTP，触发一封信，看 worker 停在那条任务、healthz 仍 ok | 已核对（grep 无 `timeout`/`EMAIL_TIMEOUT`） |
| C2 | **worker 被 SIGKILL 后认领的任务永远 RUNNING**：升级重建容器默认 10 秒宽限，正在跑的 `prerender_all`、`send_broadcast`、一封正在投递的邮件就卡成 RUNNING，不重试；healthz 只数 READY，待办只数 FAILED，清理只删 SUCCESSFUL/FAILED，没有任何代码复位 RUNNING | `django_tasks_db`、`core/health.py:138-153`、`core/admin_todo.py:127-153`、`deploy/docker-compose.yml:40-58` | 升级时群发到一半被杀，剩下的人永远收不到，无提示 | 跑一个 `sleep 60` 的任务，`compose kill -s KILL worker`，重启后看 `DBTaskResult.objects.running()` | 已核对（grep `RUNNING` 只命中 health/admin_todo/测试） |
| C3 | **生产环境 500 没有任何日志**：`prod.LOGGING` 只配了 `sjtu_ow.mail`；`django.request` 的 ERROR 落到 Django 默认的 `console`（`require_debug_true`）和 `mail_admins`（`ADMINS` 空），traceback 哪都不去；500 页上的「请求编号」从没写进日志，还优先取客户端自带的 `X-Request-ID` | `sjtu_ow/settings/prod.py:31-44`、`core/middleware.py:25-36`、`core/views.py:93-97`；设计 15.5、13.15 | 用户把请求编号发给管理员，`docker compose logs web` 只有 gunicorn 一行 500 | 生产配置下访问一个会抛异常的视图看日志 | 已核对代码路径，未重现 |
| C4 | **上传的字体原文件可以被任何人下载**：原文件存 `MEDIA_ROOT/fonts/<id>/original/<上传文件名>`，Caddy `handle /media/*` 直接 `file_server`；设计 15.2 L2897「不直接提供上传的原始文件」 | `core/models.py:427-428`、`deploy/Caddyfile:73-77` | `curl https://站点/media/fonts/1/original/SourceHanSansSC-Bold.otf` 200 | 后台传一个字体，直接请求那个地址 | 已核对代码和 Caddyfile |
| F1 | **状态片段请求在网络层失败时整页占位区永远是灰块**：`state.js` 的 `htmx.ajax(...).then(清掉 ow-state-pending)` 没有失败回调，htmx 2.0.10 的 `onerror` 会 reject；`.ow-state-pending [data-slot] > *` 是 `visibility: hidden`。429/5xx 时 resolve 但不换片段，登录用户看到「登录」按钮和只读评论、无提示 | `static/js/state.js:33-40`、`assets/css/input.css:401-408`、`core/views.py:51`（每 IP 每分钟 120 次，校园网共用出口可能撞到） | 已登录成员打开预渲染页，`/_fragments/state/` 被重置 → 页头、提示条、操作面板、整个评论区全是灰块 | DevTools 屏蔽 `*/_fragments/state/*` 后打开一个有静态文件的页面 | 已核对 `state.js`，未在浏览器重现 |
| F2 / B2 | **自动保存失败后每 5 秒无限重试**，不看状态码、不退避；会话过期（302 → 登录页 200）、403、500 都一样，不提示去登录；`beforeunload` 把失败态算进「有未保存」，每次离开都被拦；战队管理页是 multipart，失败时**每次重试都重传队标文件**。写文章这种开半天的页面最容易碰到：会话过期后接着打字，正文一次都没落库 | `static/js/autosave.js:120-169,378-383`、`teams/views.py:233` | 另一个标签页退出登录后回来改昵称 → 每 5 秒一条 POST，永远「保存失败」 | 两个标签页，一个退出 | 两个代理独立报出；已核对代码，未重现 |
| B3 | **图片「改」「删」两道按张的守卫只有超管测过，拆掉不会红**：门 `uses_images` 只要求某个集合上有 add/change/choose，投稿者在「投稿图片」只有 add+choose，只能改删自己传的，靠的就是视图里两个 `if`；196 的 `mutate.py` 没列这两处 | `backoffice/views/images.py:153-154,198-201`；测试只有 `core/tests/test_autosave.py:285-306`（超管） | 守卫被误删后，任何验证过邮箱的成员能删别人的封面图 | 投稿者 A 传一张，投稿者 B POST `image_edit` / `image_delete` 应 403 且图还在 | 已核对（grep 测试目录只有超管用例） |

## 低（排进后面的轮次）

**账号与成员**

- A3 `ContactMethodForm.autosave_together = ("type","value")` 不起作用：`ContactMethod.clean` 抛的是字段级 `{"value": …}`，`type` 单独 `update_fields=["type"]` 落库绕过 `clean()` → 库里出现「微信 12345」。`core/tests/test_autosave.py:146` 只改值不改类型，把那行删掉测试仍绿（`accounts/forms.py:214`、`accounts/models.py:335-341`、`core/autosave.py:69-83,105`）
- A4 头像上传：`try` 只包住 `open/size/load`，`ImageOps.exif_transpose` 在外面；APP1 段是 `Exif\0\0` + 垃圾的 JPEG、带畸形 `Raw profile type exif` 文本块的 PNG → 500 而不是「读不出这张图片」（`accounts/images.py:34-49`；Pillow 12.3 `Image.py:4159`、`TiffImagePlugin.py:600-602`）
- A5 改登录邮箱不需要重新输入密码：`ACCOUNT_CHANGE_EMAIL = True`，没设 `ACCOUNT_REAUTHENTICATION_REQUIRED`；改密码要旧密码，邮箱是最弱一环（`sjtu_ow/settings/base.py:250`）。建议开（allauth 自带 300 秒窗口和限流，`templates/account/reauthenticate.html` 已有）
- A6 `/me/delete/` 每次 POST 都 `check_password`，没有限流，是一个拿到会话就能试密码的口（`accounts/views.py:396-415`）
- A7 自动保存的「部分保存」改段位不更新 `ranks_updated_at`：`save()` 只在整张保存时设它，`update_fields=concrete` 不含它；180 天变灰失效（`accounts/models.py:258-270`、`core/autosave.py:105`；`core/tests/test_autosave.py:122-139` 正是这个形状但没断言时间戳）
- A8 后台停用/启用直接改 `is_active`，不走 service（设计 17.3）；启用不清 `deactivation_note`；**对注销过的账号也能点「启用」**，`can_use()` 对它变 True、成员分组选择器会列出它（`backoffice/views/members.py:170-195`）
- A9 `delete_account` 清了 `is_staff`、密码、邮箱、组，**没清 `is_superuser`**（`accounts/services.py:368-411`）；配合 A8，曾是超管的匿名账号能以 `is_superuser=True` 活过来
- A10 / S9 `core.ratelimit.over_limit` 不是原子计数：默认缓存 `DatabaseCache` 没有 `incr`，走 `BaseCache.incr` 的 get→set；并发请求能超过「每分钟 3 条评论」「每天 5 次头像」这类限额。**已核对** Django 源码（`django/core/cache/backends/db.py` 无 `def incr`）。限额是防刷不是安全边界，allauth 的登录限流不走这里
- A11 设计 3.5.1 L305「头像内容编辑审核通过后才公开」和 195 轮「上传即生效」矛盾；`AvatarSubmission` 的注释同样过时。硬规则 1：设计该同步
- A12 停用账号的自传头像照常显示（`templates/components/avatar.html:9` 不看 `is_active`），细节 2.4、5.3 说停用的人只留默认头像——是不是设计本意**要用户定**
- A13 游戏 ID 的越权守卫（`accounts/views.py:201,242` 的 `user=request.user`）没有「拆掉就红」的测试；联系方式有（`accounts/tests/test_me.py:76`）
- 日历订阅地址（`core/calendar_feed.py`）是永久签名、不能作废：地址泄露后本人没有办法换一个（设计 13.5 v6.49 要的就是固定地址，属取舍；**已核对**）

**战队与赛事**

- T3 报名页 `account-<pk>` 填非数字 → `filter(pk="abc")` ValueError 500，应按 AGENTS 硬规则用 `as_id()`（`tournaments/registration.py:131-149`；`test_garbage_input` 的 POST 清单没有这个组合）
- T4 `assign_captain` 不是原子的：先 `TeamMembership.create` 再 `transfer_captain`，后者因「已当 3 支队队长」抛错时这个人已悄悄入队（`teams/services.py:486-499`）
- T5 `apply_to_team` 没有事务，并发双击第二次撞 `one_pending_application_per_team` → `IntegrityError` 500（视图只捕获 `TeamError`）；`create_team` 的 `create_blocker` 也在 `atomic` 外（`teams/services.py:230-247`、`teams/views.py:170-183`）
- T6 创建战队的每天 3 次按「尝试」计数，`over_limit` 在 `form.is_valid()` 之前求值，三次重名提交后当天建不了（`teams/views.py:106-108`；**已核对**）
- T7 赛事取消/结束后，后台仍能通过、驳回、编队；通过会写出「报名已通过」的信、战队主页多一条参赛记录（`tournaments/registration.py:398,412,736`、`backoffice/views/events.py:137-140`）。设计 8.5 没写赛事状态，算设计空白
- T8 `_write_adhoc_roster` 的 `battletag=account.battletag` 不判 None（`_write_roster` 判了）；赛事结束后删游戏 ID 再编队 → 500，极边缘（`tournaments/registration.py:706`）
- T9 测试质量：`TournamentForm.autosave_together` 四行删掉不红（见 T1）；`approve_application` 的 `select_for_update()` 在 SQLite 上是空操作，注释容易让人以为它在起作用（串行靠 IMMEDIATE，和 12.12 一致）
- `remove_member` 超管可以移除队长，留下无队长的战队（`teams/services.py:442-456`）

**内战与评论**

- S3 `finish` 没有状态守卫、`publish` 只拦 CANCELLED：已取消的内战能被「标记已结束」重新上列表；标题时间都空的草稿 finish 后 `is_public` 为真、`/scrims/<pk>/` 公开可访问；finished 能 publish 回去。对比 `tournaments/services.finish` 要求 PUBLISHED（`scrims/services.py:311-334`、`scrims/admin_views.py:42-58`；`test_auto_finish.py` 只测 worker 任务）
- S4 已结束/取消的内战上点「生成分队」，有人删了报名用的游戏 ID（结束后允许删）→ `signup.game_account.battletag` AttributeError 500（`scrims/teaming.py:74`、`accounts/services.py:97-99`）
- S5 角色限定下把人放到他没段位的位置：服务器存别的位置的分（`rating_for` 为 None 退回 `best_rating`），JS 显示 0；`_autosave` 不替换 `data-team-total`/`data-gap`，板子总分和复制文字对不上（`scrims/split_admin.py:141-143,174-181`、`static/js/scrim-split.js:83-97`）
- S6 报名后把某个位置的段位改成未定级，分队按 0 分算、无提示；`check_feasible` 只在全部位置都没段位时报错（`scrims/teaming.py:62-80,107-111`）
- S7 作者能删除已被隐藏的评论（编辑拦了、删除没拦），把正文清空后后台只剩空行（`comments/services.py:299-310`）
- S8 / F3 分队页两张自动保存表单互不等待：取消勾选（pick）的响应整块替换 `[data-split-board]`，**里面包着 teams 表单**；在飞的拖拽保存可能被盖掉，下一次移动把旧板子的隐藏值整个 POST 回去（`scrims/split_admin.py:160-166`、`scrims/templates/scrims/admin/_board.html:5,16`、`static/js/autosave.js:133-140,206`）。两个代理独立报的；可能，没构造验证
- S10 后台内战列表每个草稿一次 `signups.exists()`（`can_delete`），已 `annotate(signup_total)` 没用上；赛事列表同样（`backoffice/views/events.py:182`）
- S11 设计 12.9.1 字段表缺 `roster_changed_at`、`moved_from`

**核心与运维**

- C5 下线内容的静态文件不是「立即删除」而是排给 worker（`request_removal` 只 `enqueue`）；worker 不在时撤回的文章继续公开，没有提示。`web` 已经可写挂载了 `prerendered`，可以直接删（`core/prerender.py:373-381`；设计 13.13.5 L2661、16.2 L2983；**已核对**）
- C6 预渲染页和静态文件不带 HSTS：Caddy 的 `(page_security)` 只有 CSP、XFO、nosniff、Referrer、COOP；首访落在预渲染首页，HSTS 基本没生效，`SECURE_HSTS_PRELOAD` 也达不到要求（设计 15.2 L2887）。正式站前面用户自己的反代补没补不知道。**已核对 Caddyfile**
- C7 `restore` 的密钥校验表 `ENCRYPTED_COLUMNS` 漏了 197 加的 `moderation_api_key`：只配了 AI 密钥的库用错密钥恢复，「校验通过」，之后 `SiteSettings.load()` 每页都抛 → 整站 500（`core/management/commands/restore.py:28-31`；**已核对**）
- C8 `core/net.py` 的 `is_internal` 没有 `not is_global`：`100.64.0.0/10`（含正式站自己的 WARP 网段 `100.96.0.0/12`）放行；解析和连接之间可被 DNS 重绑定（`urllib` 再解析一次）。只有能进字体库的超管能触发（`core/net.py:22-47`、`core/fonts/download.py:48-60`；**已核对**）
- C9 `/healthz` 对公网开放并返回全部细节（数据库异常原文、磁盘百分比、积压数）；外部监控只需要状态码（`core/views.py:34-43`、`deploy/Caddyfile:79`）
- C10 镜像：容器以 root 跑（没有 `USER`）；`fetch_tailwind_cli.py` 下载第三方可执行文件不校验 sha256 就在构建期执行；`.dockerignore` 没排除 `backups/`（本机有的话会随 `COPY . .` 进镜像，里面是邮箱和联系方式）
- C11 请求编号由客户端指定并回显（并入 C3）

**后台**

- B4 首页置顶表单收 20 位数字的文章编号会 500：`ModelChoiceField(queryset=ArticlePage.objects.live())`，`ArticlePage.pk` 是 `page_ptr` 一对一外键，没有整数溢出兜底（`backoffice/forms.py:277-284`；`test_garbage_input.POSTS` 没有 `article_1` 这类键）。可能，和 AGENTS 166 的记录一致
- B5 网址片段跟着标题走时，服务器回的 `values["slug"]` 可能盖掉编辑刚打的片段（改标题的请求在途时在网址框打字并离开），窗口一个往返（`backoffice/views/articles.py:186-187`、`static/js/autosave.js:226-239`）
- B6 新建分类、成员分组时第一次改动若有错（撞名 slug、排序非数字）对象不建、`location` 为空，和 13.17「第一次改动就建好」不一致；赛事内战文章用 `new_from_valid_fields` 做到了（`core/autosave.py:95-98`、`backoffice/views/categories.py:48-63`、`members.py:438-459`）
- B7 「静态页面 → 重新生成」填了非法路径仍提示「已排入队列」（`core/prerender_admin.py:62-72` 不看 `request_page` 的返回值）
- B8 「新建即草稿」攒空对象，没人提醒、没有定时清理；网络抖动时重试还发到 `new/` 会再建一条（`content/drafts.py:48-67`、`static/js/autosave.js:162-169`）
- B9 普通成员的文章草稿若撞上同级 slug，`Page.clean()` 抛 `{"slug": …}` 而表单里没有 `slug` 字段 → `add_error` 抛 `ValueError` 500；前提很窄（`backoffice/forms.py:162-164`）。可能
- B10 写新文章的页面无条件 `can_publish: True`（`backoffice/views/articles.py:198`），对没有发布权限的人点发布是 403 而不是提示（现在各组都有权限，潜在）
- B11 群发没有次数或冷却限制，内容编辑连点十次就给全站发十封；设计 10.4 就是这样写的，只提醒要不要加「N 分钟内不再发」（`core/services.py:256-296`）

**前端**

- F4 密钥框存过一次之后明文留在 DOM 里，这张表单之后每一次自动保存都把 `smtp_password` 再发一遍、服务端重新加密存一遍；`apply()` 只清服务端在 `values` 里点名的字段，设置页的自动保存分支不返回 `values`（`backoffice/templates/backoffice/settings/site.html:5`、`core/forms.py:21-47`、`static/js/autosave.js:143,226-239`、`backoffice/views/settings.py:27-33`）
- F5 `backoffice.js` 图片对话框把任何响应（含会话过期后的登录页）原样塞进对话框，在里面提交会被当成上传（`static/js/backoffice.js:192-204`）
- F6 头像审核的 `next` 回跳没传 `require_https`，其余三处都传了（`moderation/avatar_admin.py:87-89`）
- F7 图片选择器的 `label` 指向 `<input type="hidden">`，「选择」「清除」按钮没有字段名，全站设置页读屏听到 N 个一样的「选择, 按钮」（`backoffice/templates/backoffice/widgets/image_picker.html`、设计 13.11）
- F8 几条测试只是对 JS 源码做子串断言（`test_autosave_split_team.py:111-121`、`content/tests/test_drafts.py:228-236`、`test_menus_and_context_menu.py:41-90`、`test_admin_functions.py:334-338`），逻辑错了抓不到；真正的行为守卫是 `journey.py admin`，不在 CI 里。`test_templates.py:30-43` 只扫 `style="`，不扫 `on*=` 和无 `src` 的内联 `<script>`（今天 grep 没有这类内容，是缺口不是缺陷）
- F9 头像「即选即传」用 `form.submit()`，不触发 `submit` 事件，「先 flush 再提交」和 `beforeunload` 的配合不会跑（`static/js/autosave.js:326-338`）
- F10 `content/embeds.py:34` 的 `?bvid=` 不校验，正文里能往 B 站播放器地址追加参数（`autoplay=1` 之类）；`escape()` 和 `frame-src` 钉死，只影响播放器参数

## 补充：内容与 AI 审核（报告在 `86cddb1` 之后到）

**高**

- **D1 查不到的 b23 短链不缓存，正文每渲染一次就联网一次；搜索又把全部已发布正文渲染一遍——任何能发文章的成员都能用一篇文章拖慢全站。** `video_src` 的 b23 分支调 Wagtail `get_embed`，Wagtail 8 只在找到时才 `Embed.update_or_create`，`EmbedNotFoundException` 什么都不记，下一次渲染再查（`follow_b23` 是 `urlopen(timeout=10)`）。渲染次数还被放大：一次文章页请求渲染 3 遍（`render` + `facts` 里 `analyse`、`plain_text`）；每张文章卡 `article.facts.minutes` 再渲染 2 遍；**每次搜索把所有已发布文章正文和赛事内战说明 `plain_text` 一遍**；worker 单进程，评论、点赞都触发该文章重生成。场景：验证过邮箱的成员发一篇正文里 50 行各不相同、查不到的 `https://b23.tv/xxxx`，之后每个访客的搜索都要等 50 次到 b23 的往返，b23 不通时每次 10 秒 → 一次搜索 500 秒，5 个 gunicorn 进程被 5 个搜索占满；worker 重生成该页时卡住，验证码邮件跟着等。不用恶意，一条过期的 b23 链接就让每次搜索、每次预渲染慢一秒以上（`content/markdown.py:66-75`、`content/embeds.py:52-58`、`content/models.py:328,333`、`templates/components/post_card.html:13`、`search/services.py:96-97,129`）。验证：mock `follow_b23` 抛 `EmbedNotFoundException`，`render("https://b23.tv/abc")` 两次，调用应是 2；`test_a_short_link_is_looked_up_once` 只测成功时缓存。修法：失败也记一条（`Embed` 有 `cache_until`），或发布时把播放器地址算好存起来，渲染不联网；字数、阅读时间发布时算好存进字段（D10）。代码路径读通，未重现

**中**

- **D2 删分类只数页面行，草稿修订里引用的分类删得掉**；删了以后那篇文章的编辑页、预览、定时上线全部 500。自动保存的草稿只写修订，页面行的 `category` 停在建行那一刻（通常是 `None`）；删掉分类后 `get_latest_revision_as_object` → modelcluster 对 `on_delete=PROTECT` 直接 `raise Exception`；`publish_scheduled` 的循环没有 try，排在它后面的定时文章也发不出去。违反设计 5.3 L566「还有文章（包括草稿）在用的分类不能删除」（`backoffice/views/categories.py:29,72,95`、`content/drafts.py:41`）。验证：内容编辑自动保存新文章 → 编辑页选分类 X → 删 X 成功 → GET 编辑页 500。修法：计数把修订 JSON（或 `ReferenceIndex`）算上。代码路径读通，未重现
- **D3 两个人同时改同一篇，后存的把先存的整个顶掉**：每次自动保存发整张表单、不带修订号，`_autosave` 把表单里有效的字段套在**这次请求读到的**最新修订上 `save_draft`；`overwritable` 只决定「覆盖自己的还是另起一份」，没有「我打开以后别人改过」的判断。网站页面同样（`backoffice/views/articles.py:166-188,288-289`、`backoffice/views/pages.py:94-101`、`content/drafts.py:23-33`）。场景：A、B 同时开着「关于我们」，A 改第一段存了，B 改标题存 → 最新草稿正文是旧的，两人来回互相抹。设计 13.17 L2754 说的「别人接着改另起一份」默认的是先后。验证：两个 client 各 GET 一次编辑页再交替自动保存不同字段。修法：表单带隐藏的 `latest_revision` 编号，不一致就回「别人改过了」不存。代码路径读通，未重现

**低**

- D4 = F10：`?bvid=` 查询参数不过 `BV_RE`，能往播放器 iframe 塞 `autoplay=1`（两个代理独立报出）
- D5 正在被巡查的记录被「发布后再发布」原地改成新文字：`submit` 对还没看的记录直接改 `text_hash/full_text`，`review_long` 已把旧文读进内存、看完后 `record` 写 `checked_at` 并清 `full_text` → 旧文的「无风险」落到新文头上，新文再也不看（`moderation/services.py:127-137`、`moderation/patrol.py:114-143`）。修法：`record` 时核对 `text_hash` 没变再写
- D6 巡查信把 `quote`/`reason` 里的网址自动变成可点链接（`wrap_text` 对所有段落 `URL.sub`）：作者写「管理员请到 https://钓鱼站/admin 重置密码」，超管收到的信里就是一条标着「引用」的链接；「要求作者修改」的信同理（`moderation/notifications.py:83`、`core/letters.py:178-208`）。只把站内地址做成链接
- D7 附加请求参数的禁用清单 `EXTRA_BODY_FORBIDDEN` 禁了 `messages/tools/tool_choice`，没禁 OpenAI 旧式 `functions`/`function_call`；`stream`、`response_format`、`model` 也能被覆盖，`stream:true` 会让每轮「响应不是 JSON」不计次数永远重试（`moderation/services.py:534`、`moderation/providers.py:141-144`）。只超管能填
- D8 `providers.review` 只接 `URLError, TimeoutError, OSError`，不接 `http.client.HTTPException`（`IncompleteRead`、`BadStatusLine`）：半截断流时异常冒到任务层，这一轮没有 `note_failure`、没有 follow-up（`moderation/providers.py:175`）
- D9 设计附录 C L3419 还写着 AI 密钥和地址在环境变量，197/v7.1 起都在后台（5.5.3 正文已改，附录没改）
- D10 字数和阅读时间每次都重新解析 Markdown（`article_meta.py:26-29` 两次完整渲染），搜索每次解析全部正文；和 D1 叠加。发布时算好存字段
- 测试绿但没测到：`test_a_short_link_is_looked_up_once` 只 mock 成功；`test_markdown.py` 没有 REVIEW-GUIDE 192 点名的 `![x" onerror=…]`、`> ——<script>`、`?bvid=` 输入；`test_category_delete.py` 的文章全是页面行、没有草稿修订引用；`test_drafts.py:102` 只数修订条数、没测同时打开；`test_patrol_failures.py` 没有「巡查中途再提交」

**查过没问题**：手拼 HTML 全经 `escape`，`src`/`href` 来自 markdown-it 且过 `validateLink`（拒 `javascript:`、`vbscript:`、`file:`、非图片 `data:`）和 `normalizeLink`，`own_image` 拒 `//host`；预览和上传接口都套 `placed`、上传按集合权限只进「投稿图片」；发布/撤下/删除别人的文章由 `OwnArticlesPermissionTester` 限在 owner 或有 change 权限的人；草稿不从栏目、相关、首页、sitemap、搜索、预渲染、分享卡片露出，AI 只在 `page_published` 送审；网址跟标题的四种情形；草稿修订的 `overwritable` 和 Wagtail 自己的检查；AI 巡查和 5.5.3 逐条对得上（计次规则、`GAVE_UP`、一次失败停轮、60 秒截止、follow-up 优先级、30 天沿用、每日上限、批大小、`<<<`/`>>>` 替换、请求只有文本无 tools）；密钥只在 `Authorization` 头、日志只含状态码、表单不回显、`EncryptedTextField` 落库；复核页权限和 `next`；首页数字；sitemap/robots；坏输入

**没来得及看**：`content/legacy_body.py` 逐行、`backoffice/views/images.py`、`moderation/avatar_admin.py`、评论对未发布文章的接口、`core/prerender.py` 对 404 的处理、`/wagtail/` 超管路径的旧表单、205/198 变异脚本的覆盖

## 代理「查过没问题」的覆盖面（摘要）

- **账号**：越权（游戏 ID、联系方式按 `user=request.user` 取）、CSRF、注册/登录/验证码/找回密码的限流和枚举防护、停用账号的会话失效、注销的顺序和清单、导出只有本人数据、成员展示和搜索只露昵称、头像上传三道检查、`can_use()` 和 4.3.2 一致、`next` 只交给 allauth、Cookie 配置、日历签名
- **战队赛事**：所有改状态的视图经 service 查队长/超管、后台的门 `access.runs_tournaments`；报名状态机和 8.5 表逐行对上；IMMEDIATE + atomic 的并发保护、`test_concurrency.py` 用真线程；编队页 POST 的归属校验；15 封顺带的信都走 `outbox.hold`；时间改动和 `KeepSeconds`；复制不带状态字段；联系方式只给该看的人；赛事详情、列表、审核列表的查询数
- **内战评论**：门和权限；报名资格全套；分队页输入；算法（126/462 种分法穷举、剪枝无损、并列收齐、8 个种子的暴力对照）；复制格式和 9.6 一致；13.13 的刷新事件；评论可见性、越权、点赞唯一约束、CSRF；取消内战的信在 `HeldLettersMiddleware` 的 batch 里
- **核心运维**：CSP（无 nonce，全部外部文件，Caddy 和 Django 一字不差有测试）、Cookie 和安全头、反代信任链（`X-Real-IP` 由 Caddy 覆盖）、预渲染三道闸（匿名 Client、Set-Cookie 即拒、`SECRET_MARKERS`）、Caddy 分流顺序、邮件队列的 `on_commit` 和重试、加密字段「大声失败」、备份恢复顺序、healthz 逻辑、worker 心跳、Compose 卷（worker 和 web 一致，有测试）、CI 和 `check.sh` 一致、时区
- **后台**：**权限核对表全部一致**（每个地址的门和 `docs/admin.md` 4 的表逐行对上，`test_door.py` 用四个非超管角色扫全部地址并断言 `backoffice_gate`，拆掉 `placed` 里的 `gate` 会红）；`UserForm` 白名单，`is_superuser/is_staff/groups` 不可 POST，提超管只能在 `/wagtail/`（有意）；自动保存三条规则和 13.17 一致；密钥字段不回显、空着保留（两条测试）；文章自动保存只存修订不发布；发信页按 actor 过滤、`decide` 原子认领；`ArticleForm` 的作者/分类/slug 规则（196 变异过 6 处）；坏输入都过 `as_id`
- **前端**：**没有找到 XSS 或 CSRF**：所有 `innerHTML` 收的都是服务端渲染的 HTML，`|safe` 全仓库只有维护页的内联 CSS，没有 `autoescape off`、没有变量进 `<script>`；每个 POST 表单的 `csrf_token` 逐文件数过；预渲染页里依赖 `request.user` 的输出只在 `slots/*.html`；CSP 下无内联样式和事件；15 处 `target="_blank"` 都有 `rel="noopener"`；`theme.js` 等 localStorage 都在 try/catch 里

## 代理没来得及看的

`backoffice/views/members.py` 的战队列表编辑页、`core/announce_admin.py` 的预览、`ScrimForm.clean` 有没有 T1 同类规则、`teams/images.py` 队标解码、`moderation` 对评论送审的去重、`/wagtail/` 下超管专用的用户表单、6v6 分队的暴力对照、`core/fonts/processing.py`、13.13.4 事件表逐行对照、服务器上的 `Caddyfile.vps`（HSTS 补没补）、`static/vendor/` 里的第三方库本身、旧后台视图（`review_admin.py`、`teams_admin.py`、`split_admin.py` 非自动保存部分）的内部逻辑、后台列表页模板的按钮是否按权限隐藏。

## 建议的修法顺序

0. **先修 D1**（b23 查不到也缓存、字数阅读时间发布时算好存起来、搜索不再逐篇渲染）——这是唯一一条任何成员都能触发的全站影响
1. **211**：T1（连带查 `ScrimForm`）、A1、A3、F2、F4、B6、D3（带修订号）、D2（删分类数修订）——都是 202–207 自动保存的收尾，一起修
2. **212**：S1、S7、S2、S3、T2、T7、A8、A9、B3——权限和状态守卫，每条补「拆掉就红」的测试
3. **213**：C1、C2、C3——worker 和日志，改完在服务器上真演练一次（064 的坑）
4. **214**：C4、C5、C6、C9、F1——Caddy 和预渲染
5. 其余低的按顺手修；A2、A12、T7、B11 的设计空白先问用户
