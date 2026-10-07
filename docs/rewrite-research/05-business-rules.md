# 05 · 业务规则对等契约（237 条）

来源：服务层业务规则调研代理。**每条均为「重写后必须逐条仍然成立」的可检验规则**，一句话 + file:line（基线 `ec44ae4`）。这是重构的验收清单。

与任务描述不符的两处现状：① 头像自 v6.73 起是**先换后管**（上传即生效，管理员事后可撤下）；②「未满 14 周岁不要注册」只写在协议页文案里，代码无年龄字段、无强制。

## 一、账号（accounts / 权限组）

**注册与登录**
1. 注册必填：邮箱、密码、确认密码、昵称（2–16 字）、是否交大（二选一）、同意用户协议、同意跨境存储，两个协议勾选框必填 — `accounts/forms.py:25-48`
2. 邮箱验证为强制，6 位数字验证码、15 分钟有效、最多 3 次尝试、支持重发 — `sjtu_ow/settings/base.py:219,243-247`
3. 找回密码同样走验证码：3 分钟有效、最多 3 次尝试 — `base.py:248-250`
4. 邮箱全站唯一；登录名即邮箱；防止账号枚举 — `base.py:221,257-258`
5. 登录/注册限流按访客 IP（取 Caddy 传入的 `X-Real-IP`，而非 REMOTE_ADDR，否则反代后全员连坐）— `accounts/adapter.py:53-57`、`core/ratelimit.py:11-19`
6. allauth 限流数字：signup 20/m/ip、login 30/m/ip、login_failed 10/m/ip + 5/300s/key、reset_password 20/m/ip + 5/m/key、confirm_email 1/10s/key、manage_email 10/m/user、change_password 5/m/user、reset_password_from_key 20/m/ip、reauthenticate 10/m/user — `base.py:261-271`
7. 改登录邮箱必须重新认证（重输密码），重认证窗口 5 分钟 — `base.py:251-255`
8. 会话 14 天；注册成功跳「个人资料」页并提示补全游戏 ID/联系方式 — `base.py:200`、`accounts/adapter.py:42-51`
9. 新用户按 is_sjtu 自动进「交大用户」或「校外用户」组，其他组不动，每次保存都同步 — `accounts/services.py:53-63`、`accounts/signals.py:73-78`
10. 「未满 14 周岁不要注册」仅为协议页文案，注册表单无年龄校验

**功能开关（can_use）**
11. `can_use` 判定顺序：未登录/停用 → 一律拒绝；单用户规则（可允许可禁止）优先；其次任一所在组有组限制即拒绝；默认允许；未知 feature 抛 ValueError — `accounts/permissions.py:15-30`
12. 被拒时对用户只显示固定文案，绝不透露原因（是停用还是被禁）— `accounts/permissions.py:7-12`、`tournaments/registration.py:59-64`

**投稿者组**
13. 「投稿者」资格 = 账号启用 + 邮箱已验证 + can_use(ARTICLE_SUBMIT)；满足即自动加入、不满足即自动移出 — `accounts/services.py:187-210`
14. 邮箱确认、EmailAddress 保存、组关系变化、Feature 规则增删都触发该同步 — `accounts/signals.py:100-137`
15. 服务端背书的邮箱（createsuperuser、verify_email）直接记为已验证并置为主邮箱，不发邮件 — `accounts/services.py:166-184`

**游戏 ID 与资料**
16. 每人最多绑 5 个游戏 ID（全站设置 max_game_accounts 默认 5）— `accounts/services.py:66-70,125-131`
17. battletag 全站唯一（不分大小写）— `accounts/forms.py:183-191`
18. 「资料完整」= 至少 1 个游戏 ID + 至少 1 种联系方式（报名前置条件）— `accounts/services.py:73-84`
19. 每种类型的联系方式只能填一条 — `accounts/forms.py:227-241`
20. 个人宣言一行 ≤30 字且不能含链接（正则拦截 http/www/常见域名）— `accounts/forms.py:68,105,131-135`
21. 公开段位 = 所有游戏 ID 中每个位置的最高分；段位更新时间距今 >180 天标记为过期；不勾「公开段位」则完全不显示 — `accounts/roles.py:17-18,74-87,99-106`

**头像（现为「先换后管」）**
22. 头像上传限 5 次/天/人 — `accounts/services.py:651,699-700`
23. 上传即通过并立即设为头像（默认信任），旧的自传头像图片随即删除 — `accounts/services.py:687-717`
24. 图片限制：仅 JPG/PNG/WebP、≤5MB、最短边 ≥128px、≤4000 万像素；处理时 EXIF 转正、中心裁方、缩到 512px、重存 WebP（位置/设备/时间等元数据全部清除）— `accounts/images.py:18-24,31-63`、`accounts/forms.py:301-315`
25. 管理员撤下头像：必须选审核原因、只在「已通过且正在使用」状态可撤；撤下即换默认头像、删图片，事务提交后给本人发信（经 hold 排队）— `accounts/services.py:749-786`、`accounts/notifications.py:32-44`
26. 同一提交不能被处理两次（状态不匹配即报「已被处理过」）— `accounts/services.py:749-757`
27. 本人移除头像立即生效、无审核，自传图片删除 — `accounts/services.py:720-733`

**注销（原地匿名化）**
28. 注销必须重输当前密码，且密码尝试限 5 次/小时 — `accounts/forms.py:264-281`、`accounts/views.py:396-411`
29. 在任队长的用户不能注销：必须先转让队长或解散每支未解散战队 — `accounts/services.py:294-304`
30. 用户行永不删除，只匿名化：email→deleted-{pk}@deleted.invalid、昵称→「已注销用户」、清 motto/角色/is_sjtu/验证记录、is_active=is_staff=is_superuser=False（注销即摘超管）、set_unusable_password、清全部组、deactivation_note=「用户自行注销」— `accounts/services.py:368-421`
31. 注销级联顺序：先撤内战报名（报名 PROTECT 游戏 ID）→ 退出所有进行中临时队 → 删个人报名 → leave_all_teams（退队+退役记录删除+待审申请取消）→ 删游戏 ID/联系方式/EmailAddress/FeatureUserRule/MemberGroupMembership/HeldLetter(actor) → 删头像记录与图片 → 删该用户的昵称/宣言审核记录 — `accounts/services.py:386-421`
32. 全部指向人的外键处置有映射表（ON_DELETION），新增列必须登记（有测试兜底）：文章/评论保留但署名「已注销用户」，报名名单快照保留，操作人字段保留 — `accounts/services.py:328-365`

**停用/启用**
33. 停用必须填原因 — `accounts/services.py:827-834`
34. 停用后：其所有待审入队申请自动取消（备注「账号已停用」）；其任队长的战队 is_recruiting 自动置 False — `accounts/services.py:799-813`、`teams/services.py:73-86`
35. 注销过的账号（@deleted.invalid 结尾）不能再启用 — `accounts/services.py:820-824,837-844`
36. 重新启用会清空停用原因 — `accounts/services.py:837-844`

**导出个人信息**
37. 导出限 5 次/小时，JSON 附件、Cache-Control: no-store — `accounts/views.py:378-393`
38. 导出覆盖 15 个自有数据域：账号、游戏 ID、联系方式、战队、头像上传记录、退役记录、入队申请、赛事报名快照、个人报名、内战报名、成员分组、文章、评论、评论点赞、功能规则；不含他人数据和管理员操作记录；EXPORTED/NOT_EXPORTED 两张映射表与测试同步维护，新增表忘了登记测试会红 — `accounts/services.py:427-473,476-646`

**后台可见性**
39. 只有超管能按邮箱搜索用户、看到用户邮箱（内容编辑自 216 轮起不行）— `members/services.py:218-236`、`backoffice/forms.py:57-68`
40. 用户编辑页的联系方式只对超管或有 view_contactmethod 权限者（赛事管理员、内战管理员）显示 — `accounts/services.py:35,847-878`
41. 五个 staff 组都授予后台访问权（wagtailadmin.access_admin）— `accounts/services.py:141-155`

**角色组权限总表**
42. 内容编辑：文章分类/成员分组/评论管理/AI 审核队列/页面与图片全权；认证作者与投稿者：文章区 add+publish（自己的）、投稿图片集合；赛事管理员：Tournament CRUD + 见联系方式；内战管理员：Scrim CRUD + 见联系方式 — `content/services.py:407-471`、`members/services.py:182-206`、`comments/services.py:322-336`、`moderation/services.py:368-389`、`tournaments/services.py:376-400`、`scrims/services.py:250-272`

## 二、内容（content）

**草稿与修订**
43. 自动保存复用同一份修订：仅当最新修订是本人的草稿、非 live、未定时、且 30 分钟内创建时 overwrite — `content/drafts.py:17,45-55`
44. 同一人连续编辑只占一份修订；不同人各占各的（overwrite 条件含 user_id）— `content/drafts.py:45-55,58-67`
45. 两人同时编辑：表单回传 latest_revision，与当前最新修订不一致即拒绝保存并提示「另一个人改过」；非数字值拒绝而非忽略；无该字段按原样保存 — `content/drafts.py:22-42`
46. 新文章从第一次改动即存在（标题空时页面行存「（无标题）」）；发布时整表单校验（标题、分类必填）才放行 — `content/drafts.py:18-20,70-89`、`content/models.py:262-273`
47. 自动保存只保存合法字段，非法字段保留旧值（部分保存，不整体失败）— `backoffice/views/articles.py:166-193`

**发布门槛与权限**
48. 投稿直接发布：内容审核工作流已整体退役 — `content/services.py:367-396`
49. 普通成员（投稿者/赛事/内战管理员/认证作者）只能发布、撤下自己的页面；内容编辑与超管可操作任何人的 — `content/permissions.py:78-96`
50. 非超管、非内容编辑在页面树/后台只见 live 页面和自己的页面 — `content/permissions.py:45-55`、`content/wagtail_hooks.py:13-30`
51. 普通成员的编辑器没有「网址和发布时间」字段组（slug/seo_title/search_description/go_live_at/expire_at）— `backoffice/forms.py:99-105,190-192`
52. 只有内容编辑（和超管）能改文章「作者」字段 — `content/permissions.py:70-75`
53. 纯投稿者只能选 allow_submission 的分类、没有评论开关字段 — `backoffice/forms.py:185-189`

**定时上线/撤下**
54. worker 每 30 秒一拍：心跳 + 检查定时发布/到期撤下（无到期时仅两条查询即返回）— `core/worker.py:54-73`、`content/services.py:474-494`
55. 定时上线那一刻，此前安排的「上线时通知全体成员」自动发出 — `content/signals.py:73-88`、`core/services.py:333-349`
56. 文章撤下、删除、改网址、移动时：对应静态页当场请求删除并刷新列表/首页 — `content/signals.py:91-148`
57. 定时规则：expire_at 必须晚于 go_live_at 且在将来 — `backoffice/forms.py:212-219`

**网址规则**
58. slug 留空则按标题生成（unicode slugify，截 60 字，取不到用 article），与兄弟页冲突则追加 -2、-3… — `backoffice/forms.py:221-235`
59. 网址片段不能是保留词：admin、wagtail、accounts、comments、documents、me、api 等（RESERVED_CHILD_SLUGS）；自动生成撞保留词时加 -article 后缀 — `content/models.py:24-32,125-132`、`backoffice/forms.py:228-230`
60. 手填 slug 需在同父页面下可用（唯一性校验在字段上）— `backoffice/forms.py:202-210`

**Markdown 渲染**
61. CommonMark + 表格 + 删除线；单个换行即 <br>（breaks=True）；HTML 不解析、原样文本显示 — `content/markdown.py:268-276`
62. #/## 均渲染为 h2，### 及以下为 h3（h1 留给页面标题）— `content/markdown.py:32,183-186`
63. 单独成行的本站图片 → <figure> 大图 + 图注（figcaption 取 alt 文本）；一行多图各成一个 figure — `content/markdown.py:82-85,103-126`
64. 外站图片不内嵌：行内本站图片=小 <img>，行内外站图片=纯链接（alt 或「图片」），非 http 协议只显示 alt 文本 — `content/markdown.py:43-54,244-255`
65. 「本站」判定：无协议无域名的站内路径，或域名与 SITE_URL 完全一致（CSP 不允许外站图）— `content/markdown.py:43-54`
66. 单独成行的 B 站链接（bilibili.com 各子域，含 BV 号或 /video/ 路径）→ 嵌入 player.bilibili.com 播放器 iframe（带分页 p 参数）— `content/markdown.py:57-79,127-142`、`content/embeds.py:36-58`
67. b23.tv 短链需一次网络跳转解析；解析失败把失败结果缓存 1 小时，命中成功的结果永久缓存 — `content/markdown.py:66-78`、`content/embeds.py:27-29,61-90`
68. 正文中的裸 URL 自动转为链接 — `content/markdown.py:30,145-171`
69. 引用块最后一行以「——」开头渲染为出处脚注 — `content/markdown.py:208-241`

**统计与目录**
70. 字数 = 中文字符数 + 拉丁单词数；阅读分钟 = 字数/400 + 每图 10 秒 + 每视频 60 秒，向上取整且最少 1 分钟 — `content/article_meta.py:17-19,40-51`
71. 正文纯文本、字数、阅读分钟在保存时落库，页面/搜索/审核不再重复解析 Markdown — `content/models.py:285-289`、`scrims/models.py:118-128`
72. 目录仅当 h2/h3 总数 ≥3 时显示；锚点用 h-1、h-2 数字编号 — `content/article_meta.py:20,61-75`、`content/models.py:332-336`

**通知全体成员（文章）**
73. 只有能改作者的人（内容编辑/超管）可用 — `core/services.py:92-102`
74. 必须已发布或已安排定时上线，否则拒绝；同一篇只能有一个「上线时通知」排队 — `core/services.py:239-247`
75. 同一篇对全体 30 分钟冷却（EVERYONE_GAP_MINUTES=30）— `core/services.py:26-27,248-261`
76. 收件人 = 启用中 + accepts_announcements=True + 已验证主邮箱（sjtu_only 内容仅交大用户），每人单独一封、各带自己的退订链接；发送时才重算收件人 — `core/services.py:109-121,352-381`
77. 第二封起在信里注明「之前已经发过 N 次」— `core/services.py:170-178`
78. SMTP 未配置时不能发 — `core/services.py:262-265`
79. 每次发送记一条 Broadcast 历史 — `core/services.py:156-162,273-330`

**其他**
80. 分类被使用数的统计包含草稿（自动保存的分类只存在于修订里）— `content/services.py:234-269`
81. 首页置顶文章最多 3 篇 — `content/models.py:168-175,193-196`
82. 默认封面/默认头像图片池的任何增删移会触发全站静态页重建 — `content/signals.py:166-202`

## 三、战队（teams）

83. 队名 2–16 字，且不能与任何未解散战队重名（不分大小写，含唯一约束兜底）— `teams/forms.py:47-48`、`teams/services.py:46-50,130-155`
84. 每人每天最多创建 3 支战队（表单合法才计数，重名不消耗额度）— `teams/views.py:23,104-111`
85. 每人最多同时担任 3 支未解散战队的队长（全站设置，默认 3），检查在建队写事务内重复执行 — `teams/services.py:38-39,118-127,138-140`
86. 战队人数上限 = 全站设置（默认 10）— `teams/services.py:34-35`
87. 只有队长（或超管）能改战队资料、审批申请、移除成员、转让队长、解散；修改资料时同样查重名 — `teams/services.py:169-174,282,458,480,517-519,559-562`

**入队申请**
88. 可申请条件（全部满足）：已登录、can_use(team_apply)、战队未解散、不是成员、招募中、未满员、队长账号未停用（无队长的战队不能申请）、至少绑 1 个游戏 ID、没有该队待审申请 — `teams/services.py:194-220`
89. 申请限流 20 次/天/人 — `teams/views.py:24,164`
90. 意向位置至少选一个；留言 ≤200 字；有留言则同步送 AI 审核 — `teams/services.py:240-241,257-265`、`teams/forms.py:87-105`
91. 提交申请后邮件通知队长（经 hold 排队）— `teams/services.py:254-256`
92. 审批通过在一个写事务内重新检查：申请人注销/停用 → 申请自动取消并报错；已是成员 → 自动取消（不回滚）；满员 → 拒绝通过 — `teams/services.py:272-322`
93. 通过时创建成员资格、删除该人此队的退役记录、发结果邮件（通过的信附队内联系方式，若有）— `teams/services.py:307-317`、`teams/notifications.py:41-65`
94. 待审申请满 7 天：给队长发一封汇总提醒（每队一封，captain_reminded_at 保证只提醒一次）— `teams/services.py:372-406`
95. 待审满 14 天无人处理：自动关闭并通知申请人（夜任务执行）— `teams/services.py:360-362,409-422`、`core/management/commands/cleanup_old_data.py:51,115-120`
96. 队长管理页的待审列表只显示 applicant__is_active=True（停用账号的申请隐藏）— `teams/services.py:607-617`

**成员变动**
97. 队长不能直接退出，必须先转让队长或解散 — `teams/services.py:429-431`
98. 队员退出/被移除时写入或更新退役记录（TeamAlumnus）；重新入队则删除退役记录 — `teams/services.py:721-740`
99. 队员退出时若其仍留在已提交的赛事报名名单，邮件告知队长哪些名单还留着及其截止时间 — `teams/notifications.py:126-164`、`tournaments/registration.py:469-490`
100. 不能移除自己；不能移除队长（超管也不行，须先转让）— `teams/services.py:460-468`
101. 退役记录只有本人、该队队长或超管能删除 — `teams/services.py:743-759`

**队长转让/指定**
102. 转让队长只能转给现有成员；不能转给停用账号；对方担任队长数达上限则拒绝 — `teams/services.py:477-500`
103. 超管指定队长（救援路径）：非超管不可；已解散的队不可；停用账号不可；目标不在队时可先入队（满员则拒绝）；整个流程一个事务 — `teams/services.py:510-528`

**解散与队标**
104. 解散拦截：战队还有进行中（待审/已通过）且赛事处于草稿/已发布状态的报名时不能解散 — `teams/services.py:531-554`
105. 解散动作：置 disbanded_at、删除全部成员资格、待审申请全部取消、通知全体成员、静态页删除 + 列表/首页/成员页刷新 — `teams/services.py:557-588`
106. 队标：仅 JPG/PNG/WebP、≤5MB（不裁剪不转码，原样存图库）；建队失败时已上传的 logo 立即删除 — `teams/forms.py:11-13,72-84`、`teams/images.py:6-23`
107. 队名和简介每次变更都送 AI 审核（失败只记日志，绝不阻塞操作）— `teams/services.py:679-718`
108. 队长账号停用的战队进入「无队长战队」名单：不能收申请、不能报名赛事；超管后台待办列出 — `teams/services.py:53-60`、`core/admin_todo.py:230-247`

## 四、赛事（tournaments）

**创建/发布/状态**
109. 发布门槛：标题非空、报名开始/截止时间均已填且截止晚于开始 — `tournaments/services.py:187-203`
110. 已取消的不能再发布；只有已发布的可标「已结束」；没填好的草稿不能取消（直接删除）；发布过的赛事不能删除，只能取消 — `tournaments/services.py:206-217,220-226,229-239,250-254`
111. 报名方式（整队/个人）一旦有任何报名就不能再改 — `tournaments/services.py:83-85`、`backoffice/forms.py:521-526`
112. 「报名自动通过」开关一旦有任何队报名就不能再改 — `tournaments/services.py:78-80`
113. 整队模式的 roster_min 不能超过全站战队人数上限；roster_min≥1、roster_max≤20、max≥min — `tournaments/services.py:166-177`、`backoffice/forms.py:493-514`
114. 赛事说明非空时每次变更送 AI 审 — `tournaments/services.py:270-271,360-373`

**整队报名**
115. 提交前预检（全部问题一次列出）：赛事收战队、已发布且在报名时间窗、战队未解散且操作者是队长、人数在 [min,max]、每个成员各自通过成员检查、无人在别的队名单上 — `tournaments/registration.py:90-128`
116. 成员检查：can_use(tournament_register)（对队长隐藏原因）、资料完整（游戏 ID+联系方式）、sjtu_only 时必须是交大用户 — `tournaments/registration.py:48-70`
117. 一人同一赛事只能在一个活跃名单上 — `tournaments/registration.py:73-87`
118. 所选游戏 ID 必须属于该成员；未选/无效则回落到其第一个 ID；一个都没有则报错 — `tournaments/registration.py:131-154`
119. 名单是快照：昵称、battletag、段位、是否交大、是否队长在提交时定格 — `tournaments/registration.py:157-180`
120. 提交→PENDING；auto_approve 开启时同一事务内由 SYSTEM 直接置 APPROVED（不另发状态变更邮件）— `tournaments/registration.py:265-302`
121. 新加入活跃名单的非队长队员每人收到「你已被报名参加」邮件（无需确认）— `tournaments/registration.py:256-279`
122. 状态机：PENDING→APPROVED / REJECTED；APPROVED→REJECTED（=撤销）；活跃名单占名额，驳回/撤回后 is_active=False 释放名额 — `tournaments/registration.py:334-366,416-454`
123. 每次状态变化写 RegistrationStatusLog；队长收到每一次管理员变更的通知邮件（系统操作不发）— `tournaments/registration.py:198-219,369-380`
124. 撤回报名：只有队长、仅限活跃状态、且在报名截止前 — `tournaments/registration.py:383-401,328-331`
125. 驳回必须填备注（≤300 字）；临时队伍不能在审核页驳回 — `tournaments/registration.py:432-454`
126. 赛事已取消或已结束后不能再审核、不能再编队（否则会发出假通过的邮件）— `tournaments/registration.py:404-413`
127. 报名详情只有队长和名单上的人可见；选手联系方式只有参赛者可见 — `tournaments/registration.py:502-510,457-466`、`tournaments/slots.py:82-89`

**个人报名（散人池）与编队**
128. 个人报名条件：个人模式 + 时间窗内 + 成员检查 + 无名单冲突 + 选自己的游戏 ID + 至少勾一个位置；重复提交用唯一约束兜底 — `tournaments/registration.py:530-547,580-608`
129. 已被编入队伍后不能自行改报名信息；截止前可取消，已编队则须先退出队伍 — `tournaments/registration.py:595-597,611-623`
130. 编队板（form_teams）：先全部校验后写入，任何一条错误整个操作不生效；队名必填 ≤16 字、同赛事活跃名单中不重名（不分大小写）、人数 ≤roster_max、一人不能进两队、两支新队不能同名 — `tournaments/registration.py:645-710,758-823`
131. 编队两阶段写：先从所有原队移出再写入，避免「一人一活跃名单」约束在移动时触发 — `tournaments/registration.py:825-841`
132. 布局中缺席的现有临时队 = 全员回散人池并解散；空的新队条目忽略 — `tournaments/registration.py:807-809,849-857`
133. 新编入/新加入的成员每人收「已编入临时队伍」邮件；被移回/被解散的收「回到散人池」邮件 — `tournaments/registration.py:926-933`、`tournaments/notifications_registration.py:150-198`
134. 队员可在截止前自行退出临时队（成员行硬删除）；最后一人退出时队伍自动解散（SYSTEM 日志）并通知赛事管理员组邮箱 — `tournaments/registration.py:956-999`
135. 管理员解散临时队：全员回散人池，报名置 WITHDRAWN（不发状态信，另有回池信）— `tournaments/registration.py:741-755,935-953`

**改期与提醒**
136. 改期（note_time_change）：已发布、新时间在未来且与旧时间不同才触发；记录 moved_from（多次移动保留最早那次，改回原时间则清空），并清 reminder_sent_at 让提醒按新时间重发；保存时不自动发信，须管理员手动「通知报名的人」— `tournaments/services.py:292-314`、`core/services.py:294-318`
137. 「通知报名的人」邮件：时间移动过则写明「原来 X，现在 Y」，可附管理员说明（≤500 字）；发出后清 moved_from — `tournaments/notifications.py:40-66`、`core/services.py:273-330`
138. 开赛提醒：默认提前 24 小时（全站设置可配），一场只发一次（reminder_sent_at 条件更新）；任务执行时重读赛事，时间后移则自我顺延 — `tournaments/services.py:317-357`、`tournaments/tasks.py:12-47`
139. 提醒在窗口内保存的，至少推迟 10 分钟再发（REMINDER_GRACE）— `core/tasks.py:17-28`
140. 提醒发给已通过名单上每个活跃成员（含队伍、游戏 ID、选手联系方式）；一个都没发出去则不标记已发；散人池的人只有在已有人被编队后才收到提醒 — `tournaments/notifications.py:83-157`、`tournaments/tasks.py:38-46`
141. 取消赛事：每个活跃报名的队长收到取消邮件（临时队则通知全员）— `tournaments/services.py:88-109,242-247`

**待办与复制**
142. 赛事管理员待办：待审报名数（排除已取消赛事）、每场「N 人等待编队」、开赛超 3 天未标结束 — `core/admin_todo.py:16,44-94`
143. 复制（copy_for_new）：只照抄 COPIED_FIELDS（title/summary/description/cover/registration_mode/roster_min/max/sjtu_only/auto_approve/participant_contact），状态、报名、提醒、通知不带；三个时间字段整体平移 N 个整周使最早时间落在未来（至少 +1 周）— `tournaments/services.py:403-426`、`core/services.py:384-411`

## 五、内战（scrims）

**生命周期**
144. 状态只能前进：只有草稿能发布；已取消/已结束的不能再发布；只有已发布的能标结束 — `scrims/services.py:324-359`
145. 发布门槛：标题非空 + 开始时间已填 — `scrims/services.py:314-321,334-336`
146. 没填好的草稿不能取消（直接删除）；只有无人报名的草稿能删除 — `scrims/services.py:362-374,275-285`
147. 开始后 6 小时自动结束（任务重读内战、未发布不动、时间后移自我顺延）— `scrims/services.py:288-311`、`scrims/tasks.py:15-31`
148. 草稿内战对外 404（不泄露存在）— `scrims/services.py:79-81`
149. 已结束内战在公开列表保留 30 天（FINISHED_VISIBLE_DAYS）；取消的保留详情页但离开列表 — `scrims/services.py:43-53`、`scrims/models.py:56`
150. 取消内战：通知所有报名者（仅活跃且有邮箱者）— `scrims/services.py:362-374`
151. 开赛前提醒：默认提前 2 小时（全站设置），一场一次；每名报名者一封，含本人分队去向和社团 QQ 群链接 — `scrims/services.py:507-538`、`scrims/notifications.py:93-126`
152. 内战改期与赛事同规则（moved_from + 提醒重发 + 手动「通知报名的人」）— `scrims/services.py:477-497`

**报名资格**
153. 报名检查：已登录、账号未停用、can_use(scrim_signup)、资料完整、sjtu_only 校验、已发布且未过截止 — `scrims/services.py:98-120`
154. 报名截止 = signup_closes_at，留空表示开赛前都能报 — `scrims/models.py:142-145`
155. 游戏 ID 资格：必须选择自己的游戏 ID；角色限定赛每个勾选位置都必须有段位；开放赛至少一个位置有段位 — `scrims/services.py:123-153`
156. 至少勾一个位置 — `scrims/services.py:126-129`
157. 改游戏 ID 或改位置 → 清空已有分队（is_selected/team/assigned_role/rating_used 全清），并打 roster_changed_at 标记提醒管理员 — `scrims/services.py:179-231`
158. 报名截止后不能取消报名；取消时若已被分队同样打标记 — `scrims/services.py:203-217`

**分队（teaming）**
159. 可行性前置检查：勾选人数必须正好 players_needed（5v5=10、6v6=12）；角色限定赛每个位置「能打的人数 ≥ 2×每队需求」；所选 ID 上无任何段位者直接判无解 — `scrims/teaming.py:92-114`
160. 每队位置需求：5v5 = 1 坦克/2 输出/2 支援；6v6 = 2/2/2 — `scrims/models.py:45-48`
161. 平衡目标（字典序）：先两队总分差最小，再各位置分差之和最小；总分相同的方案中随机取一（支持「重新生成」出不同结果）— `scrims/teaming.py:168-174,276-302`
162. 搜索空间控制：第一名固定在 A 队，枚举其余组合（5v5 为 C(9,4)=126、6v6 为 462）；每队的合法角色分配全枚举后按 (总分,各位置总分) 去重排序；两侧配对用二分定位 + 向外扩展 + 已知最优剪枝，保证约 1 秒内算完 — `scrims/teaming.py:1-13,120-165,177-246`
163. 未定级（无该位置段位）按 0 分使用时，生成结果要列出这些人和位置提醒管理员 — `scrims/teaming.py:305-321`
164. 管理员手工保存分队不校验位置配比，只校验 signup 属于本场；配比不符显示警告但允许保存 — `scrims/services.py:588-626,667-678`
165. 保存分队的替补缓冲区：勾选上场但未放进任何队的玩家保留 is_selected，但清空 team/assigned_role；保存后置 teams_generated_at、清 roster_changed_at — `scrims/services.py:606-626`
166. 玩家只能看到自己的去向：「A 队 · 坦克」「替补」「这次没排上场」；公开页面不显示任何分队 — `scrims/services.py:731-749`
167. 分队有变化判定：roster_changed_at > teams_generated_at — `scrims/services.py:234-238`
168. 报名截止已过、尚未开始、且没有任何 A/B 队的已发布内战 → 内战管理员待办 — `core/admin_todo.py:97-117`
169. 复制内战：只抄 title/description/format/sjtu_only + 两时间整周平移 — `scrims/services.py:752-763`
170. 复制到 QQ 群的文案（copy_text）：按队、按位置分组列出「昵称 battletag 段位」及每队总分 — `scrims/services.py:681-714`

## 六、评论（comments）

171. 只有 live + public 的文章页能评论 — `comments/services.py:32-40`
172. 发言资格：已登录 + can_use(article_comment) + 该文章 comments_enabled（关闭后旧评论仍显示）— `comments/services.py:49-60`
173. 先发后审：评论立即公开，事务提交后送 AI 审核；送审失败只记日志绝不阻塞 — `comments/services.py:85-113`
174. 回复只有一层：回复「回复」落到其顶层帖下，reply_to_user 记录被回复者；隐藏/删除的评论不能再被回复 — `comments/services.py:63-89`
175. 正文非空、≤500 字 — `comments/services.py:66-71`
176. 发言限流：3 次/分钟 + 100 次/天每人 — `comments/views.py:17-18,57-60`
177. 编辑与发表共用资格与限流：被禁言或文章已关评论的作者不能改自己的旧评论；编辑后正文重新送审 — `comments/services.py:279-301`
178. 作者删除：is_deleted=True、清空正文、取消置顶，行保留；被管理员隐藏的评论作者不能删 — `comments/services.py:304-319`
179. 隐藏/取消隐藏/置顶/取消置顶需要内容编辑权限或超管；隐藏同时取消置顶 — `comments/services.py:124-142,249-271`
180. 置顶规则：只能置顶顶层、未隐藏、未删除的评论；每篇文章最多一条置顶（新置顶自动释放旧的）— `comments/services.py:232-261`
181. 点赞：登录 + 评论可见才能赞/取消；like_count 用条件 F 表达式增减、不落负；限流 60 次/分钟 — `comments/services.py:212-229`、`comments/views.py:19,149-151`
182. 评论列表：普通读者只见未隐藏未删除的；被隐藏/删除但仍有存活回复的顶层评论显示无正文占位；版主可见隐藏项并带标记 — `comments/services.py:145-181`
183. 排序：new（置顶 > 时间倒序）或 top（置顶 > 赞数 > 回复数 > 时间）；每页 20 条 — `comments/services.py:17-18,168-176`

## 七、审核（AI moderation）

184. AI 路径唯一允许的写操作是写 ModerationItem 行；绝不改内容、账号或可见性；技术上模型无任何工具（tools 禁用）、只输出固定 JSON — `moderation/services.py:1-7`、`moderation/providers.py:1-6`
185. 送审前置：文本非空 + 全站开关开且已配置（有 key 或自建 base_url），否则不入队 — `moderation/services.py:49-70,104-105`
186. 送审目标全覆盖：昵称、宣言、文章/页面、队名/队简介、赛事/内战说明、评论、入队留言 — `moderation/signals.py:13-30`、`moderation/integrations.py:32-109`
187. 同一处未读的旧文本被最新文本替换（自动保存的半成品不逐版排队）；文本相同（sha256）则复用现有记录并清零尝试次数 — `moderation/services.py:107-146`
188. 短文只存 2000 字摘录；长文整篇存 full_text 待读 — `moderation/services.py:31-37,111-117`
189. 巡查每 30 分钟最多一轮（共享缓存键 cache.add 防并发重复入队）— `moderation/patrol.py:31,204-212`
190. 一轮任务最多占 worker 60 秒（PATROL_SECONDS），超时把剩余排成低优先级（-10）跟进任务 — `moderation/patrol.py:31-37,174-201`
191. 短文批大小按 token 算：最多输出 token ÷ 60，上限 20 条/请求 — `moderation/services.py:22-25,331-334`
192. 长文不截断：按 8000 字符、按段落切块，一块一次请求；中途遇 high 风险立即停 — `moderation/services.py:294-314`、`moderation/patrol.py:101-134`
193. 「没看成」不算看过：请求失败该批全部留待读；只有可能是内容导致的失败（HTTP 400、截断、结构不符、漏答）才累计 attempts；网络/服务/配置失败不计数；累计 3 次后记「AI 没看成」转人工 — `moderation/services.py:26-27,247-275`、`moderation/providers.py:169-231`
194. 结论只写在被读的那份文本上（按 text_hash 条件更新）；期间文本被替换的继续等下一轮 — `moderation/services.py:197-244,259-264`
195. 去重复用：30 天内同文本的已有结论直接复制；「没看成」和失败调用的结论不能被复用 — `moderation/services.py:178-194,278-291`
196. 每日配额耗尽即本轮停止；配额为 0 = 无额度 — `moderation/services.py:154-158`
197. 无风险自动置 OK 不进人工；low/medium/high 汇总进一封巡查提醒邮件（unknown 不算发现），收件人为设置邮箱或全体活跃超管 — `moderation/patrol.py:38-39,215-218`
198. 提示词安全规则：待审内容中的指令只是文本、不执行；分隔符 <<< / >>> 被替换防伪造；游戏用语不算人身攻击；只输出 JSON — `moderation/prompts.py:6-96`
199. 附加请求参数禁止 messages/tools/tool_choice/functions/function_call/stream/model — `moderation/services.py:553-575`、`moderation/providers.py:141-153`
200. HTTP 层重试：最多 3 次，延迟 1s/3s；5xx 与 429 重试；<500 且非 429 不重试；回答截断（finish_reason=length）= 内容性失败 — `moderation/providers.py:26-27,169-231`
201. 模型拒绝/空回答 = 干净的「无法判定」（转人工）；请求温度 0 — `moderation/providers.py:64-73,222-227,131`
202. 人工复核权限：只有「内容编辑」组 — `moderation/services.py:368-389`
203. 复核页唯一直接处置是「发信要求作者修改」：说明必填 ≤500 字；作者缺失/停用/无邮箱则不能发 — `moderation/services.py:411-467`
204. 已处理的审核记录保留 180 天后清理；没人处理过的永久保留 — `core/management/commands/cleanup_old_data.py:15-17,83-102`
205. AI 有内容没看成 → 超管待办（含最后错误摘要）— `core/admin_todo.py:187-197,248-257`

## 八、横切（core：邮件、退订、限流、复制、worker）

**发信机制（hold/手动确认）**
206. 「动作产生的信」一律先经 hold 排队，由操作人手动点「发信」决定发或不发；worker/命令/服务直调则直接发 — `core/outbox.py:1-9,76-101`
207. 同一动作里同内容多收件人合并为一封；操作后页面跳转确认页；非跳转响应（自动保存）信件留在待办页 — `core/outbox.py:90-99,122-144`
208. 待发信 7 天自动过期，行 30 天清理；操作人账号被注销时批次自动由系统代发 — `core/outbox.py:26,122-133`
209. 邮件主题前缀只由发送层统一加一次（[SJTU-OW]，可配置）— `accounts/adapter.py:59-61`
210. 邮件投递失败重试 1/5/30 分钟共 3 次，之后放弃并进超管待办（近 7 天统计）— `core/tasks.py:15-16,66-77`、`core/admin_todo.py:127-153`
211. 逐封邮件清单（事件 → 收件人 → 触发时机 → 确认方式）：
    - 新入队申请 → 队长 → 提交时 → hold
    - 申请通过/拒绝 → 申请人 → 队长决定时 → hold
    - 申请等了 7 天提醒 → 队长（每队一封汇总）→ 夜任务 → 直接发
    - 申请 14 天自动关闭 → 申请人 → 夜任务 → 直接发
    - 被移出战队 → 本人 → 移除时 → hold
    - 队员退出 → 队长（附仍在名单的赛事）→ 退出时 → hold
    - 成为新队长 → 新队长 → 转让时 → hold
    - 战队解散 → 全体成员 → 解散时 → hold
    - 报名提交/重提/名单同步 → 队长（临时队全员）→ 提交时 → hold
    - 队员被列入名单 → 每名新队员 → 提交时 → hold
    - 报名状态变化 → 队长/临时队全员 → 管理员操作后 → hold（SYSTEM 自动通过不发）
    - 编入临时队 → 每名新编成员 → 编队时 → hold
    - 移回散人池/临时队解散 → 相关成员 → 编队调整时 → hold
    - 临时队成员退出 → 赛事管理员组邮箱 → 退出时 → hold
    - 赛事取消 → 各活跃队长/临时队全员 → 取消时 → hold
    - 赛事开赛提醒 → 已通过名单每人 → 提前 N 小时任务 → 直接发
    - 散人未编提醒 → 池中每人（仅当已有人编队）→ 同上任务 → 直接发
    - 赛事有更新（通知报名的人）→ 全体参与者 → 管理员手动 → hold（Broadcast 记录）
    - 内战取消 → 所有报名者 → 取消时 → hold
    - 内战提醒 → 每名报名者 → 提前 N 小时任务 → 直接发
    - 内战有更新 → 报名者 → 管理员手动 → hold
    - 头像被撤下 → 本人 → 撤下时 → hold
    - 巡查发现汇总 → 设置地址或全体超管 → 每轮巡查末 → 直接发
    - 要求作者修改 → 作者 → 复核页动作 → 直接发

**退订规则**
212. 只有全员通知类邮件带退订链接，且只发给 accepts_announcements=True 的人；退订 token 用签名盐，仅对启用账号有效 — `core/services.py:19,124-150,373-381`
213. 与本人有关的邮件不可退：关掉活动通知后报名/申请/提醒/头像等照常发 — `accounts/views.py:361-375`

**限流数字汇总**
214. 搜索 30 次/分/IP — `search/views.py:11,23`
215. 状态片段接口 120 次/分/IP — `core/views.py:20,71`
216. 日历订阅 30 次/分/IP — `core/views.py:156,163`
217. 评论 3 次/分 + 100 次/天每人 — `comments/views.py:17-18,59-60`
218. 点赞 60 次/分每人 — `comments/views.py:19,149-151`
219. 建队 3 次/天每人 — `teams/views.py:23,110`
220. 入队申请 20 次/天每人 — `teams/views.py:24,164`
221. 头像上传 5 次/天每人 — `accounts/services.py:651,699`
222. 个人信息导出 5 次/小时每人 — `accounts/views.py:378-384`
223. 注销密码尝试 5 次/小时每人 — `accounts/views.py:396-411`
224. allauth 各项见第 6 条

**复制功能（copy_ahead）**
225. 复制只搬白名单字段 + 时间字段平移整数周使最早时间落在未来：weeks_ahead = (now - earliest) // 1 周 + 1；无时间字段则 +1 周 — `core/services.py:384-411`

**worker 与任务**
226. worker 单实例；每 30 秒心跳 + 定时发布检查 + AI 巡查入队，各 job 独立容错 — `core/worker.py:54-95`
227. worker 启动时把孤儿 RUNNING 任务重置为 READY 重跑（接受广播可能重复送达）— `core/worker.py:24-43`
228. 任务去重 enqueue_once：同任务同参数且到期时间不晚于已有的不再排队；提醒/自动结束类任务自行重读数据、过期任务自动顺延 — `core/tasks.py:31-63`
229. 定时静态页刷新：赛事在报名开始/截止时刻、内战在报名截止/开始时刻预约首页/列表/详情页重建 — `tournaments/services.py:274-289`、`scrims/services.py:441-466`

**清理与保留**
230. 每日 04:00 清理：完成任务记录 30 天、已处理审核记录 180 天（未处理永不删）、HeldLetter 30 天、过期会话、14 天无人处理的入队申请（关闭并通知）、7 天无一个字的空草稿 — `cleanup_old_data.py:14-20,36-60,71-170`
231. 已完成内战公开保留 30 天 — `scrims/models.py:56`
232. 静态页旧版本保留 30 天（STATIC_KEEP_DAYS）— `core/management/commands/cleanup_static.py:54-60`

**其他横切**
233. 站内搜索：纯子串匹配（casefold），查询 ≤50 字符、最多 5 个词、每类内容最多 20 条；正文用保存时落库的纯文本，Markup 和链接地址永不参与匹配 — `search/services.py:17-20,39-43,85-111`
234. 个性化片段（slots）注册表：页面名后带冒号参数（如 team-join:88），最多渲染 12 个 — `core/slots.py:13-47`
235. 昵称/宣言/头像/段位等公开字段变化会触发展示它的静态页重建 — `accounts/services.py:249-283`、`accounts/signals.py:24-70`
236. 邮箱成员判定（joined_users）= is_active=True 且至少一个已验证邮箱；成员展示、搜索、后台加分组都基于它 — `members/services.py:19-27`
237. 成员分组职务：总计 ≤20 字、每个职务 ≤10 字；后台按昵称搜人上限 10 条、排除已在组内的人 — `members/services.py:280-288,211-236`

## 陷阱规则（重构最易漏）

- 注销账号的摘超管和「注销过不能再启用」（第 30、35 条）。
- 建队/审批/编队的写事务内二次检查语义（并发正确性依赖 IMMEDIATE 事务串行化）（第 85、92、130 条）。
- 报名名单快照与活跃名额联动（is_active 跟随状态重写；成员退出临时队必须硬删而不是打标记，否则 _set_status 会复活它）（第 119、122、134 条）。
- 分队算法的并列随机与 1 秒预算；替补缓冲区不清 is_selected 的特殊语义（第 161、165 条）。
- AI 审核「失败不计入看过」「结论只落在被读文本上」两条一致性规则（第 193、194 条）。
- hold 信件的手动确认流程与 7 天/30 天生命周期（第 206-208 条）。
- 定时发布、AI 巡查、提醒、静态页预约全部跑在单 worker 30 秒节拍上（第 54、189、226 条）。
