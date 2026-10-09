# 247 M5：战队、成员展示、分组

## 背景

M4（246）完成后，STATUS 写「下一步可进入 M5 或检查点 A」。用户说「继续开发」，按 12 号文档 11.2 的顺序做 M5：战队全部、成员展示、分组，对应导入，规则 R083–R108、R236–R237。和 245、246 一样一次做完，后端为主（前端页面不在本轮，页面先只显示标题的状态不变）。

## 本轮范围

做：
- 迁移 00011：`site_settings`（战队两个上限）、`teams`、`team_memberships`、`team_applications`、`team_alumni`、`member_groups`、`member_group_memberships`，队标图片集合 `team_logo`。
- `internal/teams`：建队、改资料（自动保存协议 v2）、申请/通过/拒绝/撤回、退队/移除/转让/指定队长/解散、退役记录、夜任务（提醒队长、自动关闭）、列表/详情/管理页/我的战队/后台列表、信件、导入。
- `internal/members`：成员墙（分组、筛选、加入序号）、成员主页、后台分组（建/改/删、搜人、加人、排序、职务）、导入。
- `internal/accounts`：注销时退队、删退役记录、撤回申请、移出分组，在任队长拦截改查真表；停用时撤回申请并停招；导出补战队、申请、退役、分组；导出 `ParseRoles`/`PublicPositions`/`LoadGameAccounts`。
- 搜索补成员、战队改查 `description`。
- `sjtuow import` 接上战队与分组；worker 的夜任务接上提醒与关闭。
- apigen 重新生成。

不做：
- 赛事报名（M6）：解散拦截和退队信里的报名名单留成 `RosterGuard` 接口，M6 接上。
- AI 审核（M6）：留成 `ModerationSink` 接口，M6 接上。
- 队标上传的 HTTP 传输（multipart）：和图片上传一样是平台缺口，服务函数 `UploadLogo` 已有，规则 106 的限制在里面。
- 前端页面；预渲染（新栈没有）。

## 验收

`gofmt -l .` 空、`go vet ./...`、`go test ./...` 在测试机上全绿；每条新规则有「拆掉就红」的测试，做变异确认；apigen 生成物已提交。
