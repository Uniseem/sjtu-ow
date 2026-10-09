# 248 实现报告

## 结论

完成。M6 的赛事半边（规则 R109–R141、R143；R142 管理员待办属 M8 后台）一次做完；测试机整组全绿，49 处变异全部变红。内战半边在 249。

## 逐条结果

| 要求 | 结果 |
|---|---|
| 迁移 00012 | `tournaments`、`registrations`（`team_id` 空 = 临时队伍，`UNIQUE(tournament_id, team_id)`）、`registration_members`（一人一活跃名单的部分唯一索引）、`registration_status_logs`、`individual_signups`（至少一个位置的 CHECK）；`site_settings` 加提醒小时数 |
| 生命周期 R109–R114、R136、R137、R141、R143 | 空白草稿；`PATCH` 走自动保存协议 v2（报名开始/截止是一组、人数下限/上限是一组，组里任一出错整组不存；`base_version` 落后 409）；发布门槛、已取消不能发布、只有已发布能标结束、没填好的草稿不能取消、发布过的不能删；报名方式有任何报名（含散人池）后锁死、自动通过有队报名后锁死；整队模式下限不能超过全站战队人数上限；改期记 `moved_from`（保留最早、改回清空、只对已发布且新时间在未来）并清提醒标记；「通知报名的人」；取消通知；复制（整周平移、至少一周）；说明变更送审接口 |
| 整队报名 R115–R127 | 预检所有问题一次列出（422 `__all__`）；成员检查对队长隐藏原因；一人一活跃名单；所选游戏 ID 必须是本人的、没选回落到第一个；名单快照；提交→待审，自动通过在同一事务里由系统完成且不另发状态信；新进名单的队员各收一封；状态机与日志；队长收到每次管理员变更的信；撤回只有队长、只在截止前；驳回必填备注（≤300 字，超出截断）、临时队伍不能在审核页驳回；赛事取消/结束后不能审核或编队；报名详情只给队长和名单上的人 |
| 个人报名与编队 R128–R135 | `SignUpIndividual`/`CancelIndividual`；编队板 `GetBoard`/`FormTeams`（先全部校验后写入，两阶段写，布局里缺席的队全员回池并解散，空的新队忽略，base_version 防并发覆盖）；`DissolveTeam`；`LeaveAdhoc`（成员行硬删除，最后一人退出自动解散并通知赛事管理员）；编入/回池的信 |
| 提醒 R138–R140 | `SendDueReminders` 每 30 秒一轮（挂在 worker 的 `publish` 上）：提前 24 小时（全站设置可配），一场一次，窗口内刚保存的至少再等 10 分钟，没有已通过的报名不标记，散人池要有人通过后才收到 |
| 战队接线 | `main.go` 里 `rosterGuard` 把 `LiveRegistrations`/`EntriesStillListing` 接到 `teams.RosterGuard`：战队有进行中的报名不能解散（R104），退队信列出还留着他的名单（R99）。**M5 留的第一个接口接上了** |
| 账号域 | 注销时退出进行中的临时队、删个人报名，没人的临时队自动解散并记 SYSTEM 日志（R031） |
| worker | `publish` 上同时接了 M4 写好却没接的 `content.CheckScheduledWorker`（文章定时上线、到期撤下） |
| 导入 | `ImportLegacyTournaments` 五张表，编号沿用、可重复跑、指向不存在行的引用置空；接进 `sjtuow import` |
| 接口 | 公开：`GET /api/tournaments`、`/{id}`；登录：`/api/registrations/{id}`、`/api/me/registrations`、整队报名、撤回、个人报名、退出临时队；后台（`tournaments.manage`）：赛事列表/新建/读/保存/删/发布/结束/取消/复制/通知、审核列表/通过/驳回、编队板读写、解散临时队 |

## 验收输出

测试机：

- `go vet ./... && go test ./internal/tournaments/ ./internal/accounts/`：日志 `20261009-105747-7e52240`，两个包 ok。
- 变异（`handoff/rounds/248-m6-tournaments/mutate.py`，49 处）：基线绿，「全部 49 处变异抓到并已恢复代码」，`mut-exit=0`。
- 整组 `bash scripts/remote-check.sh`：见 STATUS 的日志名（第一次整组 staticcheck 报 `notSignedIn` 未使用，已删；重跑全绿）。

## 设计偏差

- **编队板的「换队」不再发回池信**：现行站把一个人从一队移到另一队时，先当「离开」记下、再当「新编入」，两封信都发（「移回散人池」加「已编入」）。新栈只发真正回到散人池的人。
- **编队板加 `base_version`**（每支队的 `roster_version`）：落后 409，对应 12 号文档里修 05-1 的要求。
- 提醒的「窗口内刚保存至少再等 10 分钟」：现行站靠任务入队时算 `run_after`；新栈没有逐个排任务，改成每 30 秒的扫描加 `updated_at + 10 分钟` 的条件，效果一样。
- 现行站的 `Registration.team` 是 PROTECT；这里 `ON DELETE RESTRICT`，等价。

## 未完成 / 顺带发现 / 需要确认

- **AI 审核**：`tournaments.ModerationSink` 接口已有，审核域落地后在 `main` 里接上（M6 后面或 M7）。
- **R142 管理员待办**、**「新赛事通知全体成员」的群发**：M8 / M7。
- M4 的 `CheckScheduledWorker` 用 `RFC3339Nano` 写和比较时间，而导入器和其他域用 `db.FormatUTC`（固定 6 位微秒）。两种写法混在同一列里做字符串比较，差在秒的小数位上，最多错 1 秒；要统一，留给 M4 的复核。
- 前端页面不在本轮。

## 改动文件

`server/db/migrations/00012_tournaments.sql`；`server/internal/tournaments/`（model、store、service、registration、individual、reminder、views、notify、api、import 及五组测试）；`server/internal/accounts/`（`store.go` 加 `LeaveTournamentsTx`、`service.go`、`m5_hooks_test.go`）；`server/cmd/sjtuow/main.go`；`web/packages/api/src/gen/`；本目录。
