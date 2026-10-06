# 217 复核 06：内战（`scrims/` 全部、`static/js/scrim-split.js`）

读过：AGENTS.md、REVIEW-GUIDE.md、210 `review.md`（S2–S6、S8、S10、S11 已在 211–216 修）、设计第 9 章、12.9.1；`scrims/` 全部代码和模板、`static/js/scrim-split.js`、`static/js/autosave.js`（216 的 `data-autosave-queue`）、`backoffice/views/events.py` 和 `ScrimForm`、`core/agenda.py`、`content/home.py`、`core/admin_todo.py` 的内战部分、`journey.py admin` 的分队步骤。

复现脚本：`findings/06-repro_scrims.py`（pytest；除最后的暴力对照外，每条断言「问题存在」，绿 = 复现）。在测试机上跑过一次（`bash scripts/remote-check.sh run uv run pytest -q -s -p no:cacheprovider handoff/rounds/217-second-review/findings/06-repro_scrims.py`），输出末尾 `13 passed in 9.90s`，退出码 0。也就是 7 条「问题存在」的断言全绿，5v5/6v6 对暴力穷举的对照也全绿：`rq_5v5 mixed checked 36`、`rq_5v5 flexible checked 10`、`rq_6v6 mixed checked 6`、`rq_6v6 flexible checked 2`、`6v6 all-flex generate: 0.545s`。本地日志被 `tail -120` 截掉了前面的输出，各条打印只留下了引用到的几行。

## 中

### 06-1 不限位置规格的「最高分」只看勾了的位置，没看游戏 ID 上的全部段位

- 严重度：中
- 位置：`scrims/models.py:263-271`（`best_rating`）、`scrims/teaming.py:80`（`best=signup.best_rating or 0`）、`scrims/split_admin.py:147`、`scrims/services.py:142-145`（报名规则）
- 问题：设计 9.4「每人取**所选游戏 ID 上**已填段位中的最高分」。`best_rating` 只在 `self.roles`（报名时勾的位置）里取最大值。不限位置的报名规则是「这个游戏 ID 随便哪个位置有段位就行」，所以有人能报上名，`best_rating` 却是 `None`，算法按 0 算（`or 0`）。
- 失败场景：不限位置 5v5。甲只勾了坦克，坦克没段位，输出是大师 4，报名照样通过；分队时按 0 分算，被当成最弱的人，两队明显不平衡。复制文字写 `玩家甲 XXX#1 青铜 5`（`format_rank(0)` 是青铜 5，见 06-2）。乙勾了支援（白金 2），输出是大师 4，按设计算大师 4，实际按白金 2 算。现有测试 `test_open_format_ignores_roles_and_uses_the_best_rank` 只用了「段位刚好在勾的位置上」的人，测不到这种情况。
- 怎么验证：`06-repro_scrims.py::test_open_format_best_ignores_ranks_of_unticked_roles`
- 状态：已复现（测试机，断言问题存在的用例通过）

### 06-2 打开着的旧分队页把「已经移出分队」的人原样放回去，「分队有变化」也被清掉

- 严重度：中
- 位置：`scrims/split_admin.py:129-149,171-175`、`scrims/services.py:588-626`（`save_teams`）、`static/js/scrim-split.js:168-176`；勾选表同理：`scrims/services.py:560-575`（`set_selection`）
- 问题：213/S2 让报名的人换游戏 ID、改位置、取消时被移出分队（`is_selected`、`team` 都清掉），并标记 `roster_changed_at`。但分队页每次移动都把整张板子的隐藏值（`team-<pk>`、`role-<pk>`）POST 回去。`save_teams` 照单全收：`is_selected = bool(team)`，评分用 `rating_for(role)`，最后 `roster_changed_at=None`。自动保存的回复只换复制文字、总分和问题行，不换板子，所以管理员看不到有人变了。勾选表同理：旧页面上勾或取消任何一个人，整张勾选列表一起 POST，`set_selection` 会把已经移出的人重新勾回来。
- 失败场景：管理员在截止前开着分队页调整。坦克甲在报名页改成「只打支援」，服务器把他移出分队并标了「分队有变化」。管理员接着在旧板子上拖别人一下，甲就回到 A 队坦克位，`is_selected=True`，提示也没了。复制文字发到群里写的是「坦克：甲」，可他已经说不打坦克了。甲自己的报名区和提醒邮件也写「当前分队：A 队 · 坦克」。213/S2 修的就是这件事，但只要分队页开着，修的效果就没了。
- 怎么验证：`06-repro_scrims.py::test_stale_board_puts_back_a_player_who_changed_roles`、`::test_stale_pick_list_reselects_a_player_who_changed_id`（测试机输出 `after: a tank True [Role.SUPPORT]`：只报支援的人回到了 A 队坦克，而且是上场状态）。修法方向：表单带上 `teams_generated_at` 或 `roster_changed_at` 的版本号，对不上就回「名单变了，刷新」，不存；或者服务器只接受 `is_selected` 仍为真的人。
- 状态：已复现（测试机，断言问题存在的用例通过）

## 低

### 06-3 没段位的位置「按 0 分算」，复制文字却写成真实段位「青铜 5」；青铜 5 的人在卡片上显示「—」

- 严重度：低
- 位置：`scrims/services.py:702-713`（`format_rank(row.rating_used)`）、`scrims/split_admin.py:145`、`scrims/teaming.py:43,333`、`scrims/templates/scrims/admin/_card.html:5`（`rating_used|default:"—"`）、`static/js/scrim-split.js:138`（`rating ? … : "—"`）
- 问题：附录 A 里 0 分就是青铜 5（068 轮专门修过）。v7.19（S5、S6）规定没段位的位置存 0，复制文字直接 `format_rank(0)`，于是写成「青铜 5」。反过来，卡片和脚本用的是真假判断，真正青铜 5 的人（0 分）显示成「—」，和「没段位」分不清。068 轮修过的「真假判断」问题在卡片上又出现了。
- 失败场景：生成分队时提示「玩家甲（坦克）按 0 分算」，复制文字里却是 `坦克：玩家甲 X#1 青铜 5`，群里的人以为他有段位。
- 怎么验证：`06-repro_scrims.py::test_unranked_placement_reads_bronze_five_in_copy_text`
- 状态：已复现（测试机，断言问题存在的用例通过）

### 06-4 拖到一个「没勾、但游戏 ID 上有段位」的位置：服务器存这个段位，板子按 0 算，两边对不上（S5 只修了一半）

- 严重度：低
- 位置：`scrims/split_admin.py:145`（`signup.rating_for(role) or 0`，读的是游戏 ID 上的任意位置）、`scrims/models.py:255-261`（`rating_map` 只放勾了的位置）、`static/js/scrim-split.js:83-97,117-166`
- 问题：甲只报了坦克，游戏 ID 上的输出是大师 4。把他拖进输出区：脚本里 `ratingFor` 查不到 `damage`，算 0，卡片显示「—」；服务器存 `rating_used=26`，自动保存回来的总分用 26 盖掉页面上的总分。下一次移动，`refresh()` 又按 0 重算，总分在两个数之间来回跳。复制文字写大师 4。v7.19 写的是「和算法、页面上显示的一致」，算法根本不会把他放到没勾的位置。
- 怎么验证：`06-repro_scrims.py::test_unticked_role_with_a_rank_is_stored_but_board_counts_zero`（测试机输出 `rating_used = 26 rating_map = {"tank": 22}`）
- 状态：已复现（测试机，断言问题存在的用例通过）

### 06-5 卡片按钮「A」「B」总是放进该队的第一个区（坦克），没有不用鼠标改位置的办法

- 严重度：低
- 位置：`static/js/scrim-split.js:212-228`（`querySelector('[data-zone][data-zone-team="a"]')` 取第一个匹配，在角色限定规格下就是坦克区）
- 问题：设计 9.5「角色限定规格下可以修改分到的位置」；页面提示写着「不用鼠标的话，每张卡片上的按钮也能移动」。但按钮只能换队，落点固定是坦克区：把一个输出移到缓冲区再移回来，他就成了坦克（存的分数跟着变，位置人数标红）。只用键盘或触屏的管理员没有办法分配输出或支援。`journey.py admin` 来回移的正好是 A 队第一张卡（本来就是坦克），所以测不出来。
- 失败场景：管理员在手机上把 A 队的一个输出移到缓冲区腾位置，再按「A」移回来，他变成了坦克，A 队变成两坦一输出。
- 怎么验证：浏览器里对一张输出卡点「缓冲」再点「A」，看它落在哪个区，以及隐藏框 `role-<pk>` 的值
- 状态：已核对代码

### 06-6 分队以后改规格（或「仅限交大」）不提示；角色限定规格下没有位置的人从复制文字里消失，总分却算上了

- 严重度：低（设计空白）
- 位置：`backoffice/views/events.py:39-73,429-437`（编辑已发布的内战，规格照存）、`scrims/services.py:693-707`（只输出坦克、输出、支援三行）、`scrims/split_admin.py:51-54,139-140`
- 问题：已发布、已分队的内战在后台从「不限位置」改成「角色限定」：所有人的 `assigned_role` 都是空，分队页把他们放进「未分位置」，`team_total` 仍然算上他们，复制文字却只剩「A 队（总分 N）」，一个人都没有；`teams_are_stale` 不变，没有任何提示。5v5 和 6v6 之间互改、打开「仅限交大」时，已有的报名同样不复查。另外「未分位置」区的 `role` 是空的，服务器回退到 `signup.assigned_role`：从坦克区拖进这个区的人，库里仍存坦克。
- 怎么验证：`06-repro_scrims.py::test_format_change_after_split_drops_everyone_from_copy_text`（测试机输出的复制文字只有 `【周五内战】… · 角色限定 5v5`、`A 队（总分 120）`、`B 队（总分 120）` 三行）
- 状态：已复现（测试机，断言问题存在的用例通过）

### 06-7 报名截止时间可以晚于开始时间，开始以后还能报名、改报名、取消，状态显示「报名中」

- 严重度：低（设计空白）
- 位置：`backoffice/forms.py:530-556`（`ScrimForm` 没有 `clean`）、`scrims/models.py:143-154`、`scrims/services.py:118,210`
- 问题：设计 9.1 说截止时间「为空表示开始前都可以报名」，隐含截止不晚于开始，但表单不检查。截止填错（比如开始后 5 小时）时，开始以后到自动结束前（6 小时）都还能报名，已经分进队的人能在比赛中取消，触发「分队有变化」。
- 怎么验证：`06-repro_scrims.py::test_signup_deadline_after_start_is_accepted`
- 状态：已复现（测试机，断言问题存在的用例通过）

### 06-8 已结束的内战还能「取消内战」，会给报名的人发「取消了，原定的时间不用再留出来」

- 严重度：低（设计空白，和赛事一致）
- 位置：`scrims/services.py:362-374`（只拦已取消和没填完的草稿）、`backoffice/views/events.py:178-181`（已结束的也给「取消内战」）
- 问题：v7.16 说「状态只能往前走」，但只写了发布和结束两条。已结束的内战被取消后，从「最近结束」里消失，首页「累计内战」减一，还排了一封「已取消」的信（经 `hold` 由管理员确认后发出）。
- 怎么验证：`06-repro_scrims.py::test_a_finished_scrim_can_still_be_cancelled`
- 状态：已复现（测试机，断言问题存在的用例通过）

### 06-9 分队页「分队有变化」的提示文字过时

- 严重度：低
- 位置：`scrims/templates/scrims/admin/split.html:16`
- 问题：提示写「有人取消报名或换了游戏 ID」，但 v7.16 起改能打的位置也会触发（还有注销账号）。管理员按提示去找取消和换 ID 的人，会找不到。
- 状态：已核对代码

### 06-10 分队页正在保存勾选时拖了卡片，这次移动被悄悄丢掉（216/S8 修法的副作用）

- 严重度：低
- 位置：`static/js/autosave.js:178-197`（排队等前一个保存），`static/js/autosave.js:183-186`（表单被换掉就不存，也不提示）
- 问题：勾选的保存还没回来时拖了一张卡，分队表单的保存排在后面；勾选的回复把整块板子换掉，旧表单已经不在页面上，这次移动直接丢弃。页面上卡片弹回原位，状态行是新板子的「拖动或用按钮移动……」，没有说刚才那次没存上。不会写坏数据，只是动作无声丢失。
- 状态：推测（读代码推出来的，没在浏览器里构造过）

## 查过没问题

- **状态守卫**（213/S3）：`publish` 只对草稿，`finish` 只对已发布，worker 的 `finish_past_scrim` 跳过非已发布，起始时间推后时会重新排期；`cancel_scrim` 拦已取消和没填完的草稿
- **报名资格**：登录、停用、`can_use("scrim_signup")`、资料完整、仅限交大、已发布、截止时间、游戏 ID 归属（`as_id`）、两种规格的段位规则、至少一个位置（还有数据库检查约束）；重复提交撞唯一约束时报「已经报名过」；`cancel` 要在截止前；213/S2 改位置、换 ID、缓冲区的人都会清掉分队并标记
- **算法**（读代码）：固定第 1 人在 A 队，126/462 种分法；`_assignments` 按需求穷举；`_prune` 按（总分、各位置分）去重，对任何对手的评分都不变，不会丢最优解；`_best_pairing` 按总分差由小到大向外走，用 `gap > best[0]` 和 `gap > limit[0]` 剪枝都是严格大于，所以并列的分法不会被剪掉，`generate` 按队员组合收齐并列再随机选（同一组合内的位置分配是确定的，测试注释里写明这是有意的）；`check_feasible` 的人数、每个位置能打的人数、全无段位三条；S4 游戏 ID 删了时 `players_from` 不报错。随机的 5v5（46 组）和 6v6（8 组）与暴力穷举比对，最优分数和并列分法的集合完全一致，12 人全能型 6v6 跑 0.545 秒（**已复现**，见上）
- **分队页输入**：`team`、`role` 都按白名单取；编号只限这场内战的报名；没有脚本时的「保存」「生成」都能用；门是 `placed("events","scrims")` 加 `can_manage`
- **自动保存排队**（216/S8）：两张表单同属一个队列，`queuedBehind` 在 POST 之前检查，等待中的保存在表单被换掉后放弃，不会把旧板子 POST 回去（会丢动作，见 06-10）
- **复制格式**：和 9.6 一致（标题行、空行、「A 队（总分 N）」、按位置分行、「 / 」分隔、含游戏 ID）；游戏 ID 删了时显示「（游戏 ID 已删除）」
- **前台**：详情页只列昵称和位置，没有段位和游戏 ID（静态页和片段都这样）；草稿在详情、片段、报名、取消、「我的内战」里都是 404 或看不到；自己的分队只在本人的报名区、「我的内战」、首页「我的安排」、提醒信里出现；分队页的联系方式按 `can_see_contacts` 给
- **首页和定时**：`upcoming_scrims` 只取已发布、还没开始的前 5 场；截止和开始时刻会重新生成 `/`、`/scrims/`、详情页；发布、结束、取消、编辑、报名都会刷新相应页面；开始前的提醒在改时间后作废重排，`moved_from` 由「通知报名的人」清掉；取消内战的信经 `hold` 发出
- **后台**：列表用 `signup_total`，`can_delete` 不再逐条查（S10）；待办「报名已截止、还没分队」和设计 14.1 一致

## 没来得及看

- 06-5、06-10 没在浏览器里构造过
- 提醒信、取消信的正文逐字对照设计 10.2；`core/calendar_feed.py` 对内战的处理；搜索怎么收录内战说明（归 13 块）
