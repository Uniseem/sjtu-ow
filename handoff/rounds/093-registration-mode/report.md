# 093 实现报告

## 结论

完成。赛事的「开放个人报名」开关换成「报名方式」：**个人报名**（默认）/ **整队报名**，二选一，有人报名后锁定。整队报名不需要队员确认，名单里的队员收到邮件、在赛事页看到自己在哪支队的名单里。赛事页、卡片、首页大图卡写明报名方式。内战详情页头用占位图。

## 逐条结果

1. **字段和迁移**：`Tournament.registration_mode`（`RegistrationMode`：`individual` / `team`，默认 `individual`），属性 `takes_individuals`、`takes_teams`、`mode_summary`；`tournaments/0008` 先加字段、按旧开关换值（开 → 个人，关 → 整队）、再删旧字段，可以倒回去；「报名自动通过」的说明加了「只对整队报名有效」
2. **互斥**：`precheck()` 第一条「这项赛事是个人报名，不接受战队报名」（`submit()` 也走它）；`individual_problems()` 第一条「这项赛事只接受战队报名」
3. **锁定**：`services.has_entries()`（战队报名或个人报名有一条就算）；后台表单改了报名方式而已经有人报名时报错「已经有人报名了，不能再改「报名方式」」。`has_registrations()` 照旧只管「报名自动通过」
4. **报名入口**（`slots.py`、`slots/actions.html`）：个人报名的赛事所有登录用户（包括队长）走个人报名；整队报名的赛事队长走「为战队报名」（旁边一句「整队报名，提交后全队直接进入名单，不需要队员确认」），不是队长但在有效名单里的显示报名状态、「你在「队名」的名单里」、「查看报名」，其他人「这项赛事是整队报名，需要由队长为战队报名」
5. **赛事页**：横幅标签「个人报名」/「整队报名」；关键事实个人报名是「等待编队 N 人 · 已编成 N 队」，整队报名是「已通过 N 队」；队伍一节「已编成的队伍」/「已通过的战队」；散人名单只在个人报名的赛事，标题「等待编队」，改用 `c-roster` 小卡（092 把 `c-person` 改成大名片后，这里的结构坏了）；侧栏单独一行「报名方式」加一句说明
6. **卡片和首页**：赛事卡「个人报名 · 5–6 人一队 · 已编成 N 队」/「整队报名 · … · 已通过 N 队」；首页大图卡事实行前面加报名方式
7. **战队报名页**：说明改成「整支战队一起报名：提交后全队 N 人直接进入名单，不需要队员确认，队员会收到邮件。游戏 ID 已经默认选好……」（默认选第一个是原来就有的行为，`_resolve_accounts()`）
8. **队员邮件**：`notifications_registration.team_members_entered()`，主题「你已被报名参加赛事」，每人一封（游戏 ID 各不相同）：队长、队名、赛事、游戏 ID、当前状态、「整队报名不需要你确认。不想参加的话请在报名截止前联系队长」。`submit()` 记下上一版有效名单，只给新加进来的非队长成员发；被驳回或撤回后重新提交，上一版不占名额，全队再发一次。自动通过的赛事里状态写「已通过」
9. **后台**：「报名规则」第一项是报名方式；列表筛选换成报名方式；「队伍编排」只在个人报名的赛事出现；编排页对整队报名的赛事提示「这项赛事是整队报名，不收个人报名」
10. **内战详情**：`c-stage` 加 `<img class="c-stage__img">`，图是 `scrim|cover_placeholder`；`KIND_OFFSETS` 加 `scrims.scrim: 26`，同 ID 的内战和赛事不撞同一张
11. **旧说法**：赛事列表页头、「我的报名」空状态、样张页
12. **文档**：design v5.3（4.4、8.1、8.2、8.3、8.4、8.8、10.2、12.8.1、13.2.6 横幅、报名入口一行、附录 D）；design-details 第 8 节；README 赛事、报名
13. **测试**：新文件 `tournaments/tests/test_registration_mode.py`（11 条，含一条真迁移测试：迁到 0007 建两条旧数据再迁到 0008）；`test_individual_signup.py` 改了 6 条，其中一条拆成两条（队长在两种赛事里各看到什么）；建赛事的测试辅助函数凡是要战队报名的都加了 `registration_mode="team"`（9 个文件），`test_arena_pages.py` 的关键事实测试改成两种方式各查一遍；三条模拟「093 以前两种同时开」的测试用 `_enter_team_before_v53()`（先切整队、提交、再切回）
14. **本机演示库**（不进仓库）：跑了 `0008`；「秋季校内杯」（原来两种都开，迁移后成了个人报名）改回整队报名，说明里「没有战队的同学可以个人报名」那句换掉；它的 6 条个人报名挪到「新生杯」，「新生杯」改成个人报名、开放报名，编出「新生一队」（5 人），留 1 人在散人池

## 验收输出

整组检查（Windows 本机，`PYTHONUTF8=1`）：

```
All checks passed!
262 files already formatted
```

```
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
1109 passed in 208.24s (0:03:28)
No changes detected
System check identified no issues (0 silenced).
```

（最后一行是 `check --deploy`，CI 那组环境变量。1109 = 092 的 1097 + 新文件 11 条 + 拆出的 1 条。）

变异（`handoff/rounds/093-registration-mode/mutate.py`，先跑基线）：

```
baseline green, 14 tests
caught teams by default -> test_a_new_tournament_takes_individuals
caught the migration makes everyone individual -> test_the_old_switch_becomes_the_mode
caught teams enter an individual tournament -> test_an_individual_tournament_refuses_a_team_entry
caught individuals enter a team tournament -> test_a_team_tournament_takes_no_individuals
caught a pool entry does not lock the mode -> test_the_mode_locks_once_anyone_has_signed_up
caught the mode never locks -> test_the_mode_locks_once_anyone_has_signed_up
caught captains lose the individual entry -> test_a_captain_signs_up_alone_when_people_sign_up_alone
caught captains get no team entry -> test_a_captain_enters_the_team_when_teams_enter
caught a member on the roster is not told -> test_a_member_entered_by_the_captain_sees_the_team
caught a withdrawn roster still shows -> test_a_member_entered_by_the_captain_sees_the_team
caught members are not told by mail -> test_members_hear_when_entered_and_a_sync_tells_only_the_new
caught a sync tells everyone again -> test_members_hear_when_entered_and_a_sync_tells_only_the_new
caught the captain is mailed too -> test_members_hear_when_entered_and_a_sync_tells_only_the_new
caught the page hides the mode -> test_the_page_says_how_people_sign_up
caught a team tournament shows a pool -> test_the_page_says_how_people_sign_up
caught cards hide the mode -> test_the_cards_lead_with_the_mode
caught the form hides that nobody confirms -> test_the_entry_form_says_nobody_confirms
caught the board on team tournaments -> test_the_team_board_is_offered_only_where_people_sign_up_alone
caught the scrim banner plain again -> test_a_scrim_banner_is_its_placeholder_picture
restored and green; missed: none
```

19 处变异、19 项检查全部被抓到。

截图（无头 Edge，1440 宽，未登录）：整队报名的「秋季校内杯」（浅色）、个人报名的「新生杯」（浅色、深色，改短说明后重拍了深色）、赛事列表、内战详情（浅色、深色）。

## 设计偏差

无。中途一处改了文档：侧栏说明从「每人自己报名，管理员编队」改短成「每人报名，管理员编队」（截图里折成三行）。

## 未完成 / 顺带发现 / 需要确认

- **需要确认**：报名方式锁在「有人报名之后」，不是「发布之后」；队员邮件是我加的（理由见 review）
- **未验证**：登录后各种身份看到的报名入口只有测试覆盖，没截图
- **顺带发现**：Bash 工具的 heredoc 又吃了一次反斜杠（写变异脚本时），断言拦住了，改用编辑工具。AGENTS 里已有这条
- **顺带发现**：开发服务器在改 Python 文件后又卡死一次（用户发现进不去），重启好了；重启时 `tailwind runserver` 把 `app.css` 换成不压缩版，跑全量测试前要 `tailwind build --force`（两条都是 AGENTS 里已有的坑）

## 改动文件

- 文档：`docs/design.md`、`docs/design-details.md`、`README.md`、`handoff/STATUS.md`、本目录
- 模型和迁移：`tournaments/models.py`、`tournaments/migrations/0008_registration_mode.py`
- 代码：`tournaments/registration.py`、`tournaments/notifications_registration.py`、`tournaments/services.py`、`tournaments/slots.py`、`tournaments/views.py`、`tournaments/wagtail_hooks.py`、`core/placeholders.py`
- 模板：`tournaments/templates/tournaments/{detail,index,register}.html`、`tournaments/templates/tournaments/slots/actions.html`、`tournaments/templates/tournaments/admin/teams.html`、`templates/components/tournament_card.html`、`templates/me/registrations.html`、`content/templates/content/home_page.html`、`scrims/templates/scrims/detail.html`、`core/templates/core/styleguide.html`
- 测试：`tournaments/tests/test_registration_mode.py`（新）；`tournaments/tests/{test_adhoc_teams,test_concurrency,test_disband_blockers,test_individual_signup,test_public_pages,test_registration,test_review_admin,test_state_table,test_tournaments}.py`、`accounts/tests/test_account_deletion.py`、`content/tests/test_home_sections.py`、`core/tests/test_arena_pages.py`
