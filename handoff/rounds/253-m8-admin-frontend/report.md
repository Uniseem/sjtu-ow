# 253 实现报告

## 结论

完成。M8 后台管理前端页面全面排版与前后端联调完毕（八个大类 20+ 个管理页面及全部对应路由注册、后台独立 SPA 页面骨架、导航元数据与按能力权限过滤展示、`/api/session` 注入 `superuser` 与 `caps` 细粒度能力、前端 API 客户端生成对齐、测试机整组检查全绿通过）。

## 逐条结果

| 要求 | 结果 |
|---|---|
| 增强 `/api/session` | `SessionUser` 增加 `superuser: bool` 与 `caps: []string`，返回当前用户后台能力列表；`sjtuow apigen` 更新客户端类型定义 |
| 后台骨架与导航 | `web/apps/site/src/admin/nav.ts` 定义 8 个大类（首页、内容、活动、成员、审核、数据、设置、手册）、标签与二级小标签元数据及 `hasCap` 动态权限判定；`AdminLayout.vue` 深色顶栏 `b-top`、站点链接、主题切换、登录与 403 拦截；`AdminHead.vue` 通用页头 `b-head`、`b-tabs` 与 `b-subtabs` |
| 首页与待发信 | `AdminHome.vue` 干部问候、快捷操作入口、聚合待办事项列表、Worker 心跳状态；`AdminLetters.vue` 待发信批次列表与批量确认通道 |
| 内容大类 | `AdminArticles.vue` 文章管理列表（搜索、状态与分类过滤）、`AdminArticleEdit.vue` 双栏排版编辑与草稿保存、`AdminCategories.vue` 分类管理、`AdminHomePins.vue` 首页置顶排序、`AdminImages.vue` 媒体库网格检索与图片上传 |
| 活动大类 | `AdminTournaments.vue` 赛事列表、`AdminTournamentEdit.vue` 赛事编辑、`AdminTournamentBoard.vue` 队伍编排板、`AdminTournamentReview.vue` 报名审核、`AdminScrims.vue` 内战列表、`AdminScrimEdit.vue` 内战编辑、`AdminScrimBoard.vue` 内战分队板与自动分队算法 |
| 成员大类 | `AdminUsers.vue` 用户列表与搜索、`AdminUserDetail.vue` 用户详情与角色/功能规则分配、`AdminRoles.vue` 角色概览与组限制、`AdminTeams.vue` 战队列表与队长管理、`AdminMemberGroups.vue` 成员分组管理与成员搜人添加 |
| 审核大类 | `AdminRegistrations.vue` 赛事报名审核入口、`AdminModeration.vue` 内容巡查处置与作者发信、`AdminAvatars.vue` 头像审核与违规下架、`AdminComments.vue` 评论管理与隐藏/置顶 |
| 数据、设置与手册 | `AdminActivity.vue` 活动数据统计指标与 CSV 导出、`AdminSettings.vue` 全站配置表单（SMTP、AI 审核、测试发信）、`AdminAuditLog.vue` 操作记录审计日志查询、`AdminManual.vue` 干部手册指引 |
| 路由与前后台整合 | `web/apps/site/src/routes.ts` 注册所有 `/admin/*` 路由并动态 import 分包；`App.vue` 自动按路由判断前台壳与后台骨架；`routes.test.ts` 增加后台页面解析测试 |

## 验收输出

测试机 kvm17243（日志 `sjtu-ow-test:/srv/sjtu-ow-check/runs/20261009-150327-504a6b5.log`）：
- Go（新栈）：
  - `gofmt -l .`：无待格式化文件
  - `go vet ./...`：通过
  - `staticcheck ./...`：通过
  - `govulncheck ./...`：0 个代码漏洞
  - `go test ./...`：全包通过
  - `go run ./cmd/sjtuow apigen`：无 git diff
- Web（新栈）：
  - `pnpm install --frozen-lockfile`：通过（187 entries verified）
  - `pnpm test`：通过（全部测试用例通过；各页面独立分块；首页壳 gzip: HTML 2511 + CSS 19196 + JS 57886 = 79593 字节，远低于 307200 上限，BUDGET-OK）
- 退出码 0，全部通过（07:04:10）。

## 改动文件

- `server/internal/accounts/api.go`
- `web/packages/api/src/gen/index.ts`
- `web/apps/site/package.json`
- `web/apps/site/src/viewer.ts`
- `web/apps/site/src/App.vue`
- `web/apps/site/src/routes.ts`
- `web/apps/site/src/routes.test.ts`
- `web/apps/site/src/admin/nav.ts`
- `web/apps/site/src/admin/AdminLayout.vue`
- `web/apps/site/src/admin/AdminHead.vue`
- `web/apps/site/src/pages/admin/AdminHome.vue`
- `web/apps/site/src/pages/admin/AdminLetters.vue`
- `web/apps/site/src/pages/admin/AdminArticles.vue`
- `web/apps/site/src/pages/admin/AdminArticleEdit.vue`
- `web/apps/site/src/pages/admin/AdminCategories.vue`
- `web/apps/site/src/pages/admin/AdminHomePins.vue`
- `web/apps/site/src/pages/admin/AdminImages.vue`
- `web/apps/site/src/pages/admin/AdminTournaments.vue`
- `web/apps/site/src/pages/admin/AdminTournamentEdit.vue`
- `web/apps/site/src/pages/admin/AdminTournamentBoard.vue`
- `web/apps/site/src/pages/admin/AdminTournamentReview.vue`
- `web/apps/site/src/pages/admin/AdminScrims.vue`
- `web/apps/site/src/pages/admin/AdminScrimEdit.vue`
- `web/apps/site/src/pages/admin/AdminScrimBoard.vue`
- `web/apps/site/src/pages/admin/AdminUsers.vue`
- `web/apps/site/src/pages/admin/AdminUserDetail.vue`
- `web/apps/site/src/pages/admin/AdminRoles.vue`
- `web/apps/site/src/pages/admin/AdminTeams.vue`
- `web/apps/site/src/pages/admin/AdminMemberGroups.vue`
- `web/apps/site/src/pages/admin/AdminRegistrations.vue`
- `web/apps/site/src/pages/admin/AdminModeration.vue`
- `web/apps/site/src/pages/admin/AdminAvatars.vue`
- `web/apps/site/src/pages/admin/AdminComments.vue`
- `web/apps/site/src/pages/admin/AdminActivity.vue`
- `web/apps/site/src/pages/admin/AdminSettings.vue`
- `web/apps/site/src/pages/admin/AdminAuditLog.vue`
- `web/apps/site/src/pages/admin/AdminManual.vue`
- `web/pnpm-lock.yaml`
- `handoff/rounds/253-m8-admin-frontend/`（本目录）
