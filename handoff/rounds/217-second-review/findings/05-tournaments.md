# 217 复核 05：赛事报名

范围：`tournaments/registration.py`、`review_admin.py`、`teams_admin.py`、`registration_views.py`、`services.py`、`notifications*.py`、`slots.py`、`tasks.py`、`static/js/tournament-teams.js` 和板子模板，对照设计 8.1–8.8、10.2、10.5、13.13.4。210 已修的（T1–T9）不重复。

复现脚本：`handoff/rounds/217-second-review/findings/05-repro_tournaments.py`（每条 test 断言「问题存在」，绿 = 复现）。已经在测试机上跑过：`bash scripts/remote-check.sh run uv run pytest -q -s -p no:cacheprovider handoff/rounds/217-second-review/findings/05-repro_tournaments.py`，输出结尾是 `9 passed in 1.93s`，退出码 0（交回报告之后才排到，结果补在这里）。所以 05-1 到 05-8 是「已复现」；05-9、05-10 没写进脚本，仍是「已核对代码」。05-8 的输出里有 `cells starting with '=': ['=1+1']`。

统计：中 2、低 8。

---

## 05-1 队伍编排页没有版本或过期检查：页面开着的时候别人做了改动，这边一保存就整个撤掉（中）

- **位置**：`tournaments/teams_admin.py:81-109`（`layout_from_post`）、`tournaments/registration.py:807-809`、`828-842`
- **问题**：`layout_from_post` 遍历的是**数据库里现在的**个人报名和临时队伍，而不是页面打开时的那一份。POST 里没写 `team-<pk>` 的人一律当作「散人池」（默认 `""`）；页面打开之后才建的队不在 POST 里，就没有成员，`form_teams` 会把它解散（「layout 里缺的队，所有人移出」）。没有任何版本号或 `roster_version` 的比对。
- **失败场景**：
  1. 管理员 A 打开编排页，四个人都在散人池。管理员 B（或者 A 在另一个标签页）用其中两个人编成「甲队」。A 在旧页面里把另外两个人编成「乙队」后保存：甲队被解散（状态改为已撤回），两个人回到散人池，并收到「移回散人池」的信（等 A 确认后发出）。A 看到的提示是「解散 1 支」，但他什么都没解散。
  2. 编排页开着的时候，一名成员在截止前自己退出了队伍（`leave`）。管理员保存旧页面，这个人又被**悄悄编了回去**，还收到一封「已编入临时队伍」。
- **怎么验证**：复现脚本 `test_05_1a_stale_board_dissolves_a_team_formed_meanwhile`、`test_05_1b_stale_board_puts_back_a_member_who_left`（用 client 向 `/admin/tournaments/<pk>/teams/` POST 旧页面的隐藏字段）。
- **状态**：已复现（两条 test 都绿）
- **备注**：内战拖拽分队页（`scrims/`，06 块）是照这一页写的，可能有同样的问题。

## 05-2 个人报名的赛事取消时，散人池里的人一封信也收不到，取消后也没法用「通知报名的人」补发（中，设计空白）

- **位置**：`tournaments/services.py:88-109`（`cancellation_recipients`）、`core/services.py:235-236`（`announcement_problem`：`is_live` 就是 `status == "published"`）
- **问题**：取消时只通知有效名单的队长，加上临时队伍的成员（设计 10.2 也是这样写的），散人池里的人不在里面。个人报名是赛事的默认方式，而且编队一般在截止之后（赛事页上写着「截止后由赛事管理员编队」），所以截止前或者编队前取消的话，**所有报了名的人都收不到**。取消之后「通知报名的人」又被拦下（「发布之后才能通知报名的人」），只能在取消**之前**手动发。可是 8.1 节（v6.32）和 10.4 节都把散人池算作「报了这项赛事的人」。
- **失败场景**：新生杯有 60 人个人报名，还没编队，场地没了，管理员点了「取消赛事」，发信页一封信都没有。这些人只能自己去看赛事页，个人中心「近期安排」里这项赛事也悄悄没了。
- **怎么验证**：`test_05_2_cancelling_tells_nobody_in_the_pool`：取消后 `cancellation_recipients == []`，`mail.outbox` 为空，`announcement_problem(..., audience=PARTICIPANTS)` 返回「发布之后才能通知报名的人。」
- **状态**：已复现（测试机上 test 绿）；原来写的：已核对代码。是设计 10.2 的空白，修之前要先问用户（收信人加上散人池；整队报名的非队长队员也同样收不到）。

## 05-3 已结束的赛事还能「发布」回已发布，T7 的拦截随之失效；已结束的赛事还能取消（低）

- **位置**：`tournaments/services.py:206-217`（`publish` 只拦已取消）、`229-239`（`cancel` 不拦已结束）、`backoffice/views/events.py:146`（「更多」菜单对已结束的赛事也给「取消赛事」）
- **问题**：设计 9.1 写「状态只能往前走（v7.16，和赛事一致）：发布只对草稿」，内战的 `publish` 也拦了已结束和已发布，赛事这边没拦。菜单里不显示「发布」，但确认页 `GET /admin/tournaments/<pk>/publish/` 直接打开、提交就能用。已结束 → 已发布之后，`_still_open` 不再拦，又能通过和编队了，报名时间窗还没过的话也重新开放报名。另外，已结束的赛事可以「取消」，结果是从列表里消失，队长们收到「你的报名不再有效」（信要管理员确认才发）。
- **怎么验证**：`test_05_3_a_finished_tournament_can_be_published_again`：已结束时 `approve` 报错，`services.publish` 之后状态变成 published，`approve` 也成功了。
- **状态**：已复现（测试机上 test 绿）；原来写的：已核对代码

## 05-4 一支没改动的临时队伍里有人停用（或资料不全、或人数超过新的上限），整张编排页都存不了（低）

- **位置**：`tournaments/registration.py:858-871`（逐人校验）先于 `897-900`（「没变就跳过」）；`799-804`（人数上限对每支有人的队都检查）
- **问题**：`form_teams` 对计划里的**每一支**队都重跑队员校验，包括这次完全没动的队。只要某支已有的队里有一个人停用了、删了联系方式（资料不完整），或者在仅限交大的赛事里改成了校外，又或者管理员调低了 `roster_max`，那么之后任何一次保存（比如只是新建一支别的队）都会整体失败。设计 3.7 写的是停用的人「记录保留……由管理员决定是否驳回或移除」，8.1 写「修改人数上下限不会让已有报名自动失效」，编排页却逼着管理员先把这个人移出去才能做别的事。报错只写「某某 暂时无法参加赛事报名」，不说在哪支队。
- **怎么验证**：`test_05_4_untouched_team_with_deactivated_member_blocks_every_save`
- **状态**：已复现（测试机上 test 绿）；原来写的：已核对代码

## 05-5 在两支临时队伍之间挪人，被挪的人收到「把你移回了散人池」，计数也算成「移回散人池」（低）

- **位置**：`tournaments/registration.py:828-842`、`917-919`、`926-932`
- **问题**：第一阶段把所有「离开某队」的人都记进 `returned`，包括直接挪进另一支队的人。结果被挪的人收到两封信：一封 `adhoc_members_returned`（「赛事管理员把你从临时队伍「甲队」移回了散人池」，这句不对），一封「已编入临时队伍」。成功提示里「移回散人池 N 人」把这些人也算了进去。同一件事给几个人的同一封信会合成一封（10.5），所以管理员没法只去掉写错的那一封。
- **怎么验证**：`test_05_5_moving_between_teams_says_returned_to_pool`
- **状态**：已复现（测试机上 test 绿）；原来写的：已核对代码

## 05-6 队名唯一性拿数据库里的旧名比对：两支队互换队名，或者解散一支队、同时用它的名字建新队，都会被拒（低）

- **位置**：`tournaments/registration.py:698-710`、`805`
- **问题**：`_name_problems` 查的是数据库里现在有效的报名，不看这次计划里同时要改名或解散的队。甲、乙互换队名会报「队名「乙队」在这项赛事里已经有了」。批次内部的同名检查（`810-812`）本来已经够用。
- **怎么验证**：`test_05_6_swapping_two_names_is_refused`
- **状态**：已复现（测试机上 test 绿）；原来写的：已核对代码

## 05-7 编排页编成队伍（直接就是「已通过」）不刷新首页；赛事列表页上「已通过 N 队」的数字在任何审核后都不刷新（低）

- **位置**：`tournaments/registration.py:872-896`、`921`（只调 `_refresh_tournament_page`）；`305-317`（`_refresh_public_pages` 不含 `/tournaments/`）；`tournaments/templates/tournaments/index.html:27,39`；`content/home.py:85`
- **问题**：13.13.4 写「报名变为已通过 → 赛事详情、战队主页、首页」。编排页新建的队直接写成 APPROVED，没走 `_set_status`，首页「近期」大卡上「已通过 N 队」不更新。解散（`_dissolve`）反而会刷新首页，两边不一致。另外列表页 `/tournaments/` 的卡片和表格也显示「已通过 N 队」，可是 13.13.4 的这一行没有列它，代码也不刷新。通过、驳回、撤回之后，列表页的数字要等到下一次全量生成才变（设计空白）。
- **怎么验证**：`test_05_7_forming_a_team_does_not_refresh_the_homepage`（开预渲染，编队后 `PrerenderedPage` 里没有 `/`；解散后有）
- **状态**：已复现（测试机上 test 绿）；原来写的：已核对代码

## 05-8 报名 CSV 导出不防公式注入（低）

- **位置**：`tournaments/review_admin.py:244-261`
- **问题**：昵称（2–16 个任意字符）、队名（队长自己起，16 字以内）原样写进 CSV。昵称写成 `=1+1`、`=cmd|'/C calc'!A`（16 字）这样的，管理员用 Excel 打开就会被当成公式。联系方式那一列前面带着「QQ 」「微信 」这样的类型前缀，不会被当成公式。游戏 ID 必须带 `#`，影响很小。全站其它地方也没有用来转义的辅助函数（`core/activity.py:218` 也是直接用 `csv.writer`，那里归 09 块看）。
- **怎么验证**：`test_05_8_export_writes_a_formula_nickname_verbatim`（队员昵称改成 `=1+1`、同步名单后导出，单元格原样是 `=1+1`）
- **状态**：已复现（测试机上 test 绿）；原来写的：已核对代码。新版 Excel 默认关了 DDE，实际危害主要是显示错乱，或者被诱导点开 `HYPERLINK`

## 05-9 通过和批量通过都不带名单版本：队长同步名单之后，管理员通过的是自己没看过的名单（低）

- **位置**：`tournaments/review_admin.py:160-181`、`186-204`；`tournaments/registration.py:417-428`
- **问题**：管理员看的是第 1 版名单，这期间队长同步成第 2 版（状态回到待审核），管理员在旧的详情页或列表里点「通过」，通过的是第 2 版。人工审核本来要看段位、看有没有小号，这样就被绕过去了。驳回、撤销（`reject`）也一样按当时的状态处理。
- **怎么验证**：`make(PENDING)` → 记下版本 → 换一名队员后 `submit` 同步 → POST `review_action`（action=approve）仍然成功，没有任何提示。脚本里没写这一条
- **状态**：已核对代码

## 05-10 担任多支战队的队长，其中一支报了名以后，赛事页不再给另一支报名的入口（低）

- **位置**：`tournaments/slots.py:42-50`、`tournaments/templates/tournaments/slots/actions.html` 里 `captain_teams` 那一分支
- **问题**：`my_registration` 取的是这个人任何一支队的最近一条报名，有的话就只显示「查看报名」。设计 8.2 写「担任多支战队的队长，先选择战队」。现在只能从报名详情的「同步名单」进报名页，再在下拉框里换战队，截止后或者报名不是有效状态时就找不到了。
- **怎么验证**：同一个人当两支队的队长，A 队报名后渲染 `tournament-actions` 片段，没有「为战队报名」
- **状态**：已核对代码

---

## 查过没问题

- 8.5 状态表逐行对过：通过（管理员 / 系统自动）、驳回、撤销通过 → 已驳回，撤回（只有队长、截止前、只能从有效状态撤），同步（有效状态 → 待审核，自动通过的赛事随即再通过），重新提交（复用原记录、版本加 1）；临时队伍不能驳回、不能撤回。截止判断全部用 `now <= closes_at`（`phase`、`precheck`、`captain_can_change`、`cancel_individual`）。
- T7（已取消、已结束的赛事不能审核或编队）在 approve、reject、form_teams、dissolve 里都拦了；T3 的 `as_id` 在 `_resolve_accounts`、`_own_account`、批量通过、解散里都用上了；T8 的 `battletag` 为 None 的处理两处都有。
- 8 项校验一次性全部列出；写事务是 IMMEDIATE（`settings/base.py:112`），再加上 `one_active_roster_per_user_per_tournament` 唯一约束兜底；个人报名并发时撞到 `IntegrityError` 有处理。
- 自动通过只发一封「已提交（已通过）」（`_after_status_change` 跳过系统操作）；「你已被报名参加」同步时只发给新加进来的人，重新提交时全队都发。
- 「报名方式」「报名自动通过」有报名之后锁住（`TournamentForm.clean`）。
- 选手联系方式：赛事页片段用 `takes_part`（有效名单或个人报名），报名详情页只在报名有效时显示；后台详情和导出要有 `accounts.view_contactmethod`；进后台还要先有 `change_tournament`（`reviewer_required`）。
- 编排页的 POST 只认字符串键（`r<pk>`、`new`），乱填的编号不会出 500；服务端也查本赛事范围、人数上限、队名长度、一人一队、名单冲突。
- 停用、删游戏 ID、注销：个人报名用着的游戏 ID 拦删除；名单快照保留 `battletag`；注销先退出临时队伍（`enforce_deadline=False`），信直接发；停用的人在审核列表和编排卡片上有标记。
- 解散战队会被有效报名拦住（`teams/services.py:532-553`）。
- 开赛提醒任务会重新读赛事，改期后重新排期；没有已通过的报名就不记为已发；散人池只在已经有队的时候才提醒。
- 顺带的信（10.5）都在 on_commit 里 `hold`，事务回滚就不会留下信；给自己的信（队长撤回）设计 10.5 明确允许。
- 模板里没有 `|safe` / `mark_safe`。

## 没来得及看

- `tournament-teams.js` 在真浏览器里的表现（没有跑 `journey.py admin`）
- 赛事表单的时间输入和时区（`DateTimeLocal`、`KeepSeconds`，11 块）；`enqueue_once` 和 `earlier_counts` 的细节（09 块）
- 「通知报名的人」群发页本身（`core/services.py` 的 announce，09 / 11 块）
- 赛事详情页的查询数（034 的守卫还在，没重新量）
