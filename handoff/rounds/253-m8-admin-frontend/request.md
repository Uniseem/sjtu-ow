# 253 M8 后台管理前端页面全面排版与前后端联调

## 背景

在 M8 上半（252 轮，后台管理 API、平台上传服务与旧库导入）完成后，进入 M8 下半。
根据 `docs/admin.md`、`docs/rewrite-research/12-architecture.md` 6.8 节与 M8 里程碑完成标准：
1. 后台八个大类（首页、内容、活动、成员、审核、数据、设置、手册）页面需全部补齐；
2. 后台为独立的 SPA 页面骨架（不套用前台页头页脚），遵循 `docs/admin.md` 的 `b-*` 布局规范（`b-top`, `b-head`, `b-tabs`, `b-subtabs`, `b-main`, `b-split` 等）；
3. 后台进门与标签展示由角色能力驱动（未登录跳登录页，无 `admin.enter` 权限显示 403 页面，没有权限的标签不显示）；
4. 与 252 轮补齐的后端 API 完整联调（待办、全站设置、图片库与上传、头像审核、评论管理、审计日志、活动数据、赛事/内战/战队/分组/用户）；
5. 保持与现有 `input.css` 的严格 CSP 与体积预算兼容。

## 本轮范围

做：
1. 增强 `/api/session`：
   - `SessionUser` 增加 `superuser: bool` 与 `caps: []string`，便于前端精准判断后台能力与展示对应标签。
   - `sjtuow apigen` 同步更新前端 API 客户端定义。
2. 后台骨架与通用组件：
   - `web/apps/site/src/admin/nav.ts`：定义 8 个大类、各标签路径、所需能力权限判断。
   - `web/apps/site/src/admin/AdminLayout.vue`：后台整体布局（深色顶栏 `b-top`、页头 `b-head`、一级标签 `b-tabs`、二级小标签 `b-subtabs`、内容区 `b-main`、未登录与 403 状态处理）。
   - `web/apps/site/src/viewer.ts`：同步增加 `superuser?: boolean` 与 `caps?: string[]`。
3. 后台全量页面组件实现：
   - 首页：`AdminHome.vue`（干部问候、快捷操作、待办事项、待发信通道、上线清单）、`AdminLetters.vue`（待发信批次确认）。
   - 内容：`AdminArticles.vue`（文章列表与状态筛选）、`AdminArticleEdit.vue`（文章草稿自动保存与发布/撤下）、`AdminCategories.vue`（文章分类）、`AdminHomePins.vue`（首页置顶）、`AdminImages.vue`（图片库检索与文件上传）。
   - 活动：`AdminTournaments.vue`（赛事管理）、`AdminTournamentEdit.vue`（赛事编辑）、`AdminTournamentBoard.vue`（队伍编排）、`AdminTournamentReview.vue`（报名审核）、`AdminScrims.vue`（内战管理）、`AdminScrimEdit.vue`（内战编辑）、`AdminScrimBoard.vue`（内战分队板与上场名单）。
   - 成员：`AdminUsers.vue`（用户列表）、`AdminUserDetail.vue`（用户详情、角色与功能规则）、`AdminRoles.vue`（角色限制）、`AdminTeams.vue`（战队管理）、`AdminMemberGroups.vue`（分组管理与成员搜人添加）。
   - 审核：`AdminRegistrations.vue`（报名审核列表）、`AdminModeration.vue`（内容巡查记录与复核处置）、`AdminAvatars.vue`（头像审核与下架）、`AdminComments.vue`（评论管理与置顶/隐藏）。
   - 数据：`AdminActivity.vue`（活动统计与学年数据导出 CSV）。
   - 设置：`AdminSettings.vue`（全站设置表单与测试邮件）、`AdminAuditLog.vue`（审计操作记录查询）。
   - 手册：`AdminManual.vue`（干部手册与分角色指引展示）。
4. 路由注册与测试联调：
   - `web/apps/site/src/routes.ts` 注册所有 `/admin/*` 路径路由。
   - `web/apps/site/src/App.vue` 区分前台页面与后台独立布局。
   - 编写后台页面与路由解析单元测试，验证所有后台页面均可正确解析与过门。

不做：
- 富文本 CodeMirror 6 深度定制包（留在 M8 后续或 M10 加固完善）。
- 离线切片工具链打包（D4 工具脚本已存在，不阻碍后台排版与功能）。

## 验收

- `server` 静态检查（`gofmt`, `go vet`, `staticcheck`, `govulncheck`）与测试全部通过。
- `web` 端测试（`pnpm test`）全绿，打包体积符合规范（BUDGET-OK）。
- 后台各个大类与页面地址均能正确注册与渲染。
- 测试机整组检查 `scripts/remote-check.sh` 退出码 0。
