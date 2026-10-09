# 247 实现报告

## 结论

完成。M5（战队、成员展示、分组）一次做完，规则 R083–R108、R236–R237 全部有测试；测试机整组全绿，37 处变异全部变红。

## 逐条结果

| 要求 | 结果 |
|---|---|
| 迁移 00011 | `site_settings`（战队两个上限，导入器会带过来）、`teams`（未解散队名不分大小写唯一的部分唯一索引）、`team_memberships`（每队至多一个队长的部分唯一索引）、`team_applications`（同人同队只能有一条待审的部分唯一索引）、`team_alumni`、`member_groups`、`member_group_memberships`、队标集合 `team_logo` |
| 建队 R083–R086 | `teams.CreateTeam`：队名按字数 2–16、预查重 + 唯一索引兜底；每天 3 次只数「表单合法且没重名」的（服务层调限流，路由声明 `NoLimit` 写明原因）；同时担任队长上限和人数上限读 `site_settings`；事务里把上限再查一遍 |
| 改资料 R087、R106、R107 | `UpdateTeam` 走自动保存协议 v2：按字段校验、合法的存、不合法的留旧值并报在 `fields`、`base_version` 落后 409；只有队长或超管；已解散不能改；队标换掉/删除时连图一起清（只清 `team_logo` 集合里没有战队再用的）；队名/简介变了才送审，送审失败只记日志 |
| 入队申请 R088–R096 | `canApply` 九个条件按现行站顺序；每天 20 次；意向位置至少一个、留言 ≤200 字；通过时在写事务内重查（停用/已是成员：先把申请关掉并提交，再报错；满员拒绝）；通过后建成员关系、删退役记录、发带队内联系方式的信；`RemindCaptains`（7 天、每队一封、只提醒一次）、`CloseStaleApplications`（14 天）接在 worker 的 04:00 `cleanup` 上；管理页待审列表隐藏停用账号的申请 |
| 成员变动 R097–R105 | 退出（队长不能退、写退役记录、信里列报名名单）、移除（不能移除自己/队长，超管也不行）、退役记录删除权限、转让（现有成员、非停用、队长数上限）、超管指定队长（目标不在队先入队，满员拒绝，转让被拒时整体回滚）、解散（拦进行中的报名；置时间、删成员、取消待审、通知全体、不写退役记录） |
| 无队长战队 R108 | `CaptainStopped` 判定；不能收申请；`GET /api/admin/teams` 带 `no_captain` 标志；停用账号时它任队长的战队停招 |
| 成员展示 R236–R237 | `members.Showcase`（可见分组、组内顺序、职务标签、加入序号不随筛选变、按位置/只看没队的筛选）、`Detail`（成员主页）、后台分组全套（空白新组、改名查重、排序、职务 ≤20/≤10 字、搜人 10 条、内容编辑不能按邮箱搜也看不到邮箱） |
| 账号域接线 | 在任队长拦截改查真表（原来查的 `teams.captain_id` 是 M3 的占位）；注销时退队、删退役、撤待审申请、移出分组；停用撤待审申请并停招；导出补战队、申请、退役、分组 |
| 搜索 | 战队改查 `description`（原来是占位的 `bio`），补成员（只有已加入的、只搜昵称） |
| 导入 | `teams.ImportLegacyTeams`、`members.ImportLegacyGroups` 接进 `sjtuow import`；编号沿用、可重复跑、出错不吞；指向不存在图片的队标置空 |
| apigen | `web/packages/api/src/gen/` 重新生成（只加不删） |

接口：`GET /api/teams`、`/api/teams/{id}`、`/api/teams/{id}/manage`、`/api/me/teams`；`POST /api/teams`、`PATCH /api/teams/{id}`、`.../applications`、`.../leave`、`.../disband`、`.../transfer`、`.../members/{user_id}/remove`；`/api/team-applications/{id}/approve|reject|cancel`、`/api/team-alumni/{id}/remove`；`/api/admin/teams`（列表、PATCH、assign-captain、disband，超管）；`GET /api/members`、`/api/members/{id}`；`/api/admin/member-groups…`（`member_groups.manage` 能力）。

## 验收输出

测试机（`bash scripts/remote-check.sh`，日志 `20261009-103622-7c66d55`）：

```
== Go（新栈） …  gofmt / vet / staticcheck / govulncheck / go test ./... 全部 ok（teams、members、accounts、search 都在内）
== Web（新栈） …  Tests 12 passed；BUDGET-OK 首页壳 gzip 73530 字节
== 全部通过 (02:36:50)   full-exit=0
```

第一次整组（日志 `20261009-103549-2c0e884`）staticcheck 报三条：`members/api.go` 的 S1016（结构体字面量改转换）、`members.isJoined` 与 `teams.formatOpt` 未使用（U1000）；已修，重跑全绿。

变异（`handoff/rounds/247-m5-teams-members/mutate.py`，测试机，日志 `20261009-103453-09e453a`）：基线绿；37 处里 35 处第一次就红。第 2 处「预查重不分大小写」没红——它与唯一索引兜底是等价变异（预查重改坏后，插入时由索引拦下，报同样的提示），改成变异索引本身（`lower(name)` → `name`）后红。第 23 处「非超管能指定队长」第一次红是因为变异让变量没用到、编译失败，不算数；改成 `if v == nil {` 后因断言红（测试里 `TestAssignCaptain` 的 403）。这两处单独重跑：「全部 2 处变异抓到并已恢复代码」。

本机只做了编译反馈（`go build`、`go vet`、`gofmt`）和 apigen 生成（`go run ./cmd/sjtuow apigen`）；所有 `go test`、整组、变异都在测试机上跑。

## 设计偏差

- 现行站队标上传走表单文件；新栈注册表只收 JSON、请求体 1 MB，没有 multipart。服务函数 `UploadLogo` 与规则 106 的限制已有并有测试，传输入口留给 M8 与图片上传一起补（记在 13 号文档 C 节）。
- 现行站 `team_apply` 的限流在表单校验之前数；新栈在「能申请」检查之后、写库之前数，意向位置或留言不合法的请求不消耗额度（和建队的口径一致）。
- 自动保存按 12 号文档 5.5 改成按字段补丁，原来整张表单提交的 `TeamForm` 不再有；`base_version` 必填，落后 409。
- 现行站 `Team.captain` 是方法，新栈没有 `captain_id` 列，队长就是 `team_memberships.role='captain'` 的那一行（有部分唯一索引保证至多一个）。

## 未完成 / 顺带发现 / 需要确认

- **M6 要接的两个接口**：`teams.RosterGuard`（规则 104 解散拦进行中的报名；规则 99 退队信列报名名单）和 `teams.ModerationSink`（规则 90、107 送审）。没接时解散不受拦、不送审。已写进 13 号文档 C 节。测试里的桩验证了接了之后的行为。
- 队长管理页和战队页的「报名」栏（`tournament_services.team_entries`）也是 M6。
- 战队页没有头像：Go 栈的 `users` 表目前没有头像列（M3 没做头像上传），等头像落地再补进 `Person`。
- 夜任务挂在 `SchedCleanup` 上，一个名字只能注册一个处理函数；后面的里程碑要往同一个函数里加，已在 `main.go` 的注释里写明。
- 现行站是否也应改：不涉及。

## 改动文件

`server/db/migrations/00011_teams_members.sql`；`server/internal/teams/`（model、store、service、applications、members、views、notify、api、import 及测试）；`server/internal/members/`（service、api、import 及测试）；`server/internal/accounts/`（`positions.go`、`gameaccounts_bulk.go`、`export_teams.go`、`service.go`、`store.go`、`m5_hooks_test.go`）；`server/internal/search/service.go` 及测试；`server/cmd/sjtuow/main.go`；`web/packages/api/src/gen/index.ts`、`nav.ts`；`docs/rewrite-research/13-ideas-and-followups.md`；`handoff/STATUS.md` 与本目录。
