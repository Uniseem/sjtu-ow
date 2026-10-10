# SJTU-OW 接口注册表与权限全景手册

> **注意**：本文档由 `sjtuow apigen` 从 Go 服务端注册表自动生成，单向派生，保证代码实现与架构文档 100% 同步。**严禁手动编辑**。

## 1. 架构概览与指标

- **注册接口总数**：163 个
- **公开访问接口 (Public)**：25 个
- **登录会员接口 (Member / Verified / Feature)**：60 个
- **干部管理接口 (Cap / Superuser)**：78 个
- **限流保护**：全量写接口均显式声明 `ratelimit.Decl` 集中限流规则，杜绝内联魔法数字；
- **查询预算**：关键列表接口显式声明 `api.Budget(n)` 查询上限，防范 N+1 慢查询。

## 2. 全量接口清单与准入门禁

| 方法 | 路径 | 准入门禁 (Gate) | 限流规则 (Rate Limits) | 查询预算 | 后台分类/标签 |
|---|---|---|---|---|---|
| `DELETE` | `/api/admin/categories/{id}` | Cap(article_categories.manage) | 不限流 (删除分类无需限流) | - | - |
| `DELETE` | `/api/admin/member-group-people/{id}` | Cap(member_groups.manage) | 不限流 (后台，有能力的门) | - | members/groups |
| `DELETE` | `/api/admin/member-groups/{id}` | Cap(member_groups.manage) | 不限流 (后台，有能力的门) | - | members/groups |
| `DELETE` | `/api/admin/scrims/{id}` | Cap(scrims.manage) | 不限流 (后台，有能力的门) | - | scrims/list |
| `DELETE` | `/api/admin/tournaments/{id}` | Cap(tournaments.manage) | 不限流 (后台，有能力的门) | - | tournaments/list |
| `DELETE` | `/api/articles/{id}` | Member（登录成员） | 不限流 (删除文章无需限流) | - | - |
| `DELETE` | `/api/comments/{id}` | Member（登录成员） | 不限流 (删除评论无需限流) | - | - |
| `DELETE` | `/api/images/{id}` | Cap(images.manage) | 不限流 (管理员删除图片无需限流) | - | - |
| `DELETE` | `/api/me/avatar` | Member（登录成员） | 不限流 (移除头像无需限流) | - | - |
| `DELETE` | `/api/me/contacts/{id}` | Member（登录成员） | 不限流 (删除联系方式无需限流) | - | - |
| `DELETE` | `/api/me/game-accounts/{id}` | Member（登录成员） | 不限流 (删除游戏ID无需限流) | - | - |
| `DELETE` | `/api/scrims/{id}/signup` | Member（登录成员） | 不限流 (只能取消自己的) | - | - |
| `DELETE` | `/api/tournaments/{id}/signup` | Member（登录成员） | 不限流 (只能取消自己的) | - | - |
| `GET` | `/api/admin/activity` | Cap(activity.view) | 默认 | - | data/activity |
| `GET` | `/api/admin/announce/{kind}/{id}` | Member（登录成员） | 默认 | - | - |
| `GET` | `/api/admin/articles` | Cap(admin.enter) | 默认 | - | content/articles |
| `GET` | `/api/admin/articles/{id}` | Cap(admin.enter) | 默认 | - | content/article_edit |
| `GET` | `/api/admin/avatars` | Cap(moderation.review) | 默认 | - | review/avatars |
| `GET` | `/api/admin/categories` | Cap(admin.enter) | 默认 | - | content/categories |
| `GET` | `/api/admin/comments` | Cap(comments.moderate) | 默认 | - | review/comments |
| `GET` | `/api/admin/feature-role-restrictions` | Superuser（超级管理员） | 默认 | - | roles/restrictions |
| `GET` | `/api/admin/home-pins` | Cap(admin.enter) | 默认 | - | content/home_pins |
| `GET` | `/api/admin/image-collections` | Cap(images.manage) | 默认 | - | content/images |
| `GET` | `/api/admin/images` | Cap(images.manage) | 默认 | - | content/images |
| `GET` | `/api/admin/log` | Superuser（超级管理员） | 默认 | - | settings/log |
| `GET` | `/api/admin/manual` | Member（登录成员） | 默认 | - | manual/manual |
| `GET` | `/api/admin/member-groups` | Cap(member_groups.manage) | 默认 | - | members/groups |
| `GET` | `/api/admin/member-groups/{id}` | Cap(member_groups.manage) | 默认 | - | members/groups |
| `GET` | `/api/admin/member-groups/{id}/people` | Cap(member_groups.manage) | 默认 | - | members/groups |
| `GET` | `/api/admin/moderation` | Cap(moderation.review) | 默认 | - | moderation/queue |
| `GET` | `/api/admin/moderation/{id}` | Cap(moderation.review) | 默认 | - | moderation/queue |
| `GET` | `/api/admin/scrims` | Cap(scrims.manage) | 默认 | - | scrims/list |
| `GET` | `/api/admin/scrims/{id}` | Cap(scrims.manage) | 默认 | - | scrims/list |
| `GET` | `/api/admin/scrims/{id}/board` | Cap(scrims.manage) | 默认 | - | scrims/board |
| `GET` | `/api/admin/settings` | Superuser（超级管理员） | 默认 | - | settings/site |
| `GET` | `/api/admin/teams` | Superuser（超级管理员） | 默认 | - | members/teams |
| `GET` | `/api/admin/todo` | Member（登录成员） | 默认 | - | home/todo |
| `GET` | `/api/admin/tournaments` | Cap(tournaments.manage) | 默认 | - | tournaments/list |
| `GET` | `/api/admin/tournaments/{id}` | Cap(tournaments.manage) | 默认 | - | tournaments/list |
| `GET` | `/api/admin/tournaments/{id}/board` | Cap(tournaments.manage) | 默认 | - | tournaments/board |
| `GET` | `/api/admin/tournaments/{id}/registrations` | Cap(tournaments.manage) | 默认 | - | tournaments/review |
| `GET` | `/api/admin/users` | Superuser（超级管理员） | 默认 | - | users/list |
| `GET` | `/api/admin/users/{id}` | Superuser（超级管理员） | 默认 | - | users/detail |
| `GET` | `/api/announcements/unsubscribe/{token}` | Public（公开） | unsubscribe (30/1m0s) | - | - |
| `GET` | `/api/articles/{id}/comments` | Public（公开） | 默认 | - | - |
| `GET` | `/api/home-pins` | Public（公开） | 默认 | - | - |
| `GET` | `/api/images/{id}` | Public（公开） | 默认 | - | - |
| `GET` | `/api/letters` | Member（登录成员） | 默认 | - | - |
| `GET` | `/api/letters/{batch}` | Member（登录成员） | 默认 | - | - |
| `GET` | `/api/me/agenda` | Member（登录成员） | 默认 | - | - |
| `GET` | `/api/me/announcements` | Member（登录成员） | 默认 | - | - |
| `GET` | `/api/me/calendar` | Member（登录成员） | 默认 | - | - |
| `GET` | `/api/me/export` | Member（登录成员） | account_export (5/1h0m0s) | - | - |
| `GET` | `/api/me/profile` | Member（登录成员） | 默认 | - | - |
| `GET` | `/api/me/registrations` | Member（登录成员） | 默认 | - | - |
| `GET` | `/api/me/teams` | Member（登录成员） | 默认 | - | - |
| `GET` | `/api/members` | Public（公开） | 默认 | - | - |
| `GET` | `/api/members/{id}` | Public（公开） | 默认 | - | - |
| `GET` | `/api/page/home` | Public（公开） | 默认 | - | - |
| `GET` | `/api/page/news` | Public（公开） | 默认 | - | - |
| `GET` | `/api/page/news/{slug}` | Public（公开） | 默认 | - | - |
| `GET` | `/api/page/{slug}` | Public（公开） | 默认 | - | - |
| `GET` | `/api/registrations/{id}` | Member（登录成员） | 默认 | - | - |
| `GET` | `/api/scrims` | Public（公开） | 默认 | - | - |
| `GET` | `/api/scrims/{id}` | Public（公开） | 默认 | - | - |
| `GET` | `/api/search` | Public（公开） | search (30/1m0s) | - | - |
| `GET` | `/api/session` | Public（公开） | 默认 | - | - |
| `GET` | `/api/teams` | Public（公开） | 默认 | - | - |
| `GET` | `/api/teams/{id}` | Public（公开） | 默认 | - | - |
| `GET` | `/api/teams/{id}/manage` | Member（登录成员） | 默认 | - | - |
| `GET` | `/api/tournaments` | Public（公开） | 默认 | - | - |
| `GET` | `/api/tournaments/{id}` | Public（公开） | 默认 | - | - |
| `PATCH` | `/api/admin/categories/{id}` | Cap(article_categories.manage) | 不限流 (修改分类无需限流) | - | - |
| `PATCH` | `/api/admin/member-groups/{id}` | Cap(member_groups.manage) | 不限流 (后台自动保存) | - | members/groups |
| `PATCH` | `/api/admin/scrims/{id}` | Cap(scrims.manage) | 不限流 (后台自动保存) | - | scrims/list |
| `PATCH` | `/api/admin/settings` | Superuser（超级管理员） | 不限流 (超管修改设置) | - | settings/site |
| `PATCH` | `/api/admin/teams/{id}` | Superuser（超级管理员） | 不限流 (超管后台的自动保存) | - | members/teams |
| `PATCH` | `/api/admin/tournaments/{id}` | Cap(tournaments.manage) | 不限流 (后台自动保存) | - | tournaments/list |
| `PATCH` | `/api/admin/users/{id}/roles` | Superuser（超级管理员） | 不限流 (管理员分配角色) | - | - |
| `PATCH` | `/api/admin/users/{id}/rules` | Superuser（超级管理员） | 不限流 (管理员修改单人规则) | - | - |
| `PATCH` | `/api/articles/{id}` | Member（登录成员） | 不限流 (自动保存由防抖控制) | - | - |
| `PATCH` | `/api/comments/{id}` | Member（登录成员） | comment_create_minute (3/1m0s) | - | - |
| `PATCH` | `/api/me/game-accounts/{id}` | Member（登录成员） | 不限流 (更新段位无需限流) | - | - |
| `PATCH` | `/api/me/profile` | Member（登录成员） | 不限流 (修改个人资料无需限流) | - | - |
| `PATCH` | `/api/teams/{id}` | Member（登录成员） | 不限流 (自动保存，按字段校验；改的人要是队长) | - | - |
| `POST` | `/api/admin/announce/{kind}/{id}` | Member（登录成员） | 不限流 (同一件事 30 分钟冷却，服务里数) | - | - |
| `POST` | `/api/admin/avatars/{id}/take-down` | Cap(moderation.review) | 不限流 (下架头像) | - | review/avatars |
| `POST` | `/api/admin/categories` | Cap(article_categories.manage) | 不限流 (创建分类无需限流) | - | - |
| `POST` | `/api/admin/images/upload` | Cap(images.contribute) | 不限流 (上传图片) | - | content/images |
| `POST` | `/api/admin/member-group-people/{id}/move` | Cap(member_groups.manage) | 不限流 (后台，有能力的门) | - | members/groups |
| `POST` | `/api/admin/member-group-people/{id}/title` | Cap(member_groups.manage) | 不限流 (后台，有能力的门) | - | members/groups |
| `POST` | `/api/admin/member-groups` | Cap(member_groups.manage) | 不限流 (后台，有能力的门) | - | members/groups |
| `POST` | `/api/admin/member-groups/{id}/people` | Cap(member_groups.manage) | 不限流 (后台，有能力的门) | - | members/groups |
| `POST` | `/api/admin/moderation/{id}/ask-author` | Cap(moderation.review) | 不限流 (后台，有能力的门) | - | moderation/queue |
| `POST` | `/api/admin/moderation/{id}/handle` | Cap(moderation.review) | 不限流 (后台，有能力的门) | - | moderation/queue |
| `POST` | `/api/admin/registrations/{id}/approve` | Cap(tournaments.manage) | 不限流 (后台，有能力的门) | - | tournaments/review |
| `POST` | `/api/admin/registrations/{id}/dissolve` | Cap(tournaments.manage) | 不限流 (后台，有能力的门) | - | tournaments/board |
| `POST` | `/api/admin/registrations/{id}/reject` | Cap(tournaments.manage) | 不限流 (后台，有能力的门) | - | tournaments/review |
| `POST` | `/api/admin/scrims` | Cap(scrims.manage) | 不限流 (后台，有能力的门) | - | scrims/list |
| `POST` | `/api/admin/scrims/{id}/board/generate` | Cap(scrims.manage) | 不限流 (后台，有能力的门) | - | scrims/board |
| `POST` | `/api/admin/scrims/{id}/board/selection` | Cap(scrims.manage) | 不限流 (后台，有能力的门) | - | scrims/board |
| `POST` | `/api/admin/scrims/{id}/board/teams` | Cap(scrims.manage) | 不限流 (后台，有能力的门) | - | scrims/board |
| `POST` | `/api/admin/scrims/{id}/cancel` | Cap(scrims.manage) | 不限流 (后台，有能力的门) | - | scrims/list |
| `POST` | `/api/admin/scrims/{id}/copy` | Cap(scrims.manage) | 不限流 (后台，有能力的门) | - | scrims/list |
| `POST` | `/api/admin/scrims/{id}/finish` | Cap(scrims.manage) | 不限流 (后台，有能力的门) | - | scrims/list |
| `POST` | `/api/admin/scrims/{id}/notify` | Cap(scrims.manage) | 不限流 (后台，有能力的门) | - | scrims/list |
| `POST` | `/api/admin/scrims/{id}/publish` | Cap(scrims.manage) | 不限流 (后台，有能力的门) | - | scrims/list |
| `POST` | `/api/admin/settings/test-email` | Superuser（超级管理员） | 不限流 (超管测试发信) | - | settings/site |
| `POST` | `/api/admin/teams/{id}/assign-captain` | Superuser（超级管理员） | 不限流 (超管救援动作) | - | members/teams |
| `POST` | `/api/admin/teams/{id}/disband` | Superuser（超级管理员） | 不限流 (超管动作) | - | members/teams |
| `POST` | `/api/admin/tournaments` | Cap(tournaments.manage) | 不限流 (后台，有能力的门) | - | tournaments/list |
| `POST` | `/api/admin/tournaments/{id}/board` | Cap(tournaments.manage) | 不限流 (后台，有能力的门) | - | tournaments/board |
| `POST` | `/api/admin/tournaments/{id}/cancel` | Cap(tournaments.manage) | 不限流 (后台，有能力的门) | - | tournaments/list |
| `POST` | `/api/admin/tournaments/{id}/copy` | Cap(tournaments.manage) | 不限流 (后台，有能力的门) | - | tournaments/list |
| `POST` | `/api/admin/tournaments/{id}/finish` | Cap(tournaments.manage) | 不限流 (后台，有能力的门) | - | tournaments/list |
| `POST` | `/api/admin/tournaments/{id}/notify` | Cap(tournaments.manage) | 不限流 (后台，有能力的门) | - | tournaments/list |
| `POST` | `/api/admin/tournaments/{id}/publish` | Cap(tournaments.manage) | 不限流 (后台，有能力的门) | - | tournaments/list |
| `POST` | `/api/admin/users/{id}/activate` | Superuser（超级管理员） | 不限流 (管理员启用用户) | - | - |
| `POST` | `/api/admin/users/{id}/deactivate` | Superuser（超级管理员） | 不限流 (管理员停用用户) | - | - |
| `POST` | `/api/announcements/unsubscribe/{token}` | Public（公开） | unsubscribe (30/1m0s) | - | - |
| `POST` | `/api/articles` | Member（登录成员） | 不限流 (创建草稿无需限流) | - | - |
| `POST` | `/api/articles/{id}/comments` | Member（登录成员） | comment_create_minute (3/1m0s)<br>comment_create_daily (100/24h0m0s) | - | - |
| `POST` | `/api/articles/{id}/publish` | Member（登录成员） | 不限流 (发布文章无需限流) | - | - |
| `POST` | `/api/articles/{id}/unpublish` | Member（登录成员） | 不限流 (撤下文章无需限流) | - | - |
| `POST` | `/api/auth/change-password` | Member（登录成员） | auth_change_password (5/1m0s) | - | - |
| `POST` | `/api/auth/delete-account` | Member（登录成员） | account_delete_try (5/1h0m0s) | - | - |
| `POST` | `/api/auth/email/change` | Member（登录成员） | auth_manage_email (10/1m0s) | - | - |
| `POST` | `/api/auth/email/change/confirm` | Member（登录成员） | auth_manage_email (10/1m0s) | - | - |
| `POST` | `/api/auth/login` | Public（公开） | auth_login (30/1m0s) | - | - |
| `POST` | `/api/auth/logout` | Member（登录成员） | 不限流 (退出登录无需限流) | - | - |
| `POST` | `/api/auth/reauthenticate` | Member（登录成员） | auth_reauthenticate (10/1m0s) | - | - |
| `POST` | `/api/auth/register` | Public（公开） | auth_signup (20/1m0s) | - | - |
| `POST` | `/api/auth/resend-code` | Public（公开） | auth_resend_email_code (10/1m0s) | - | - |
| `POST` | `/api/auth/reset-password` | Public（公开） | auth_reset_password (20/1m0s) | - | - |
| `POST` | `/api/auth/reset-password/confirm` | Public（公开） | auth_reset_password_confirm (20/1m0s) | - | - |
| `POST` | `/api/auth/verify-email` | Public（公开） | auth_verify_email (10/1m0s) | - | - |
| `POST` | `/api/comments/{id}/hide` | Cap(comments.moderate) | 不限流 (管理员隐藏评论无需限流) | - | - |
| `POST` | `/api/comments/{id}/like` | Member（登录成员） | comment_vote (60/1m0s) | - | - |
| `POST` | `/api/comments/{id}/pin` | Cap(comments.moderate) | 不限流 (管理员置顶评论无需限流) | - | - |
| `POST` | `/api/letters/{batch}` | Member（登录成员） | 不限流 (只处理自己的批次，每封只认领一次) | - | - |
| `POST` | `/api/me/announcements` | Member（登录成员） | 不限流 (改自己的一个开关，幂等) | - | - |
| `POST` | `/api/me/avatar` | Member（登录成员） | avatar_upload (5/24h0m0s) | - | - |
| `POST` | `/api/me/calendar/renew` | Member（登录成员） | 不限流 (换一个地址，只改自己一个数) | - | - |
| `POST` | `/api/me/contacts` | Member（登录成员） | 不限流 (添加联系方式由类型唯一约束控制) | - | - |
| `POST` | `/api/me/game-accounts` | Member（登录成员） | 不限流 (绑定游戏ID由上限5个控制) | - | - |
| `POST` | `/api/registrations/{id}/leave` | Member（登录成员） | 不限流 (只有名单上的人，只在截止前) | - | - |
| `POST` | `/api/registrations/{id}/withdraw` | Member（登录成员） | 不限流 (只有队长，只在截止前) | - | - |
| `POST` | `/api/scrims/{id}/signup` | Feature(scrim_signup) | 不限流 (每人每场一条，更新同一条) | - | - |
| `POST` | `/api/team-alumni/{id}/remove` | Member（登录成员） | 不限流 (去掉退役记录有本人、队长、超管的门) | - | - |
| `POST` | `/api/team-applications/{id}/approve` | Member（登录成员） | 不限流 (审批有队长或超管的门) | - | - |
| `POST` | `/api/team-applications/{id}/cancel` | Member（登录成员） | 不限流 (只能撤回自己的申请) | - | - |
| `POST` | `/api/team-applications/{id}/reject` | Member（登录成员） | 不限流 (审批有队长或超管的门) | - | - |
| `POST` | `/api/teams` | Feature(team_create) | 不限流 (服务层只对通过校验的那几次计数（规则 84）) | - | - |
| `POST` | `/api/teams/{id}/applications` | Feature(team_apply) | 不限流 (服务层按人每天 20 次（规则 89）) | - | - |
| `POST` | `/api/teams/{id}/disband` | Member（登录成员） | 不限流 (解散有队长或超管的门) | - | - |
| `POST` | `/api/teams/{id}/leave` | Member（登录成员） | 不限流 (退队没有滥用面) | - | - |
| `POST` | `/api/teams/{id}/logo` | Member（登录成员） | 不限流 (队长上传队标) | - | - |
| `POST` | `/api/teams/{id}/members/{user_id}/remove` | Member（登录成员） | 不限流 (移除有队长或超管的门) | - | - |
| `POST` | `/api/teams/{id}/transfer` | Member（登录成员） | 不限流 (转让有队长或超管的门) | - | - |
| `POST` | `/api/tournaments/{id}/registrations` | Feature(tournament_register) | 不限流 (队长提交，预检拦住重复，名单唯一约束兜底) | - | - |
| `POST` | `/api/tournaments/{id}/signup` | Feature(tournament_register) | 不限流 (每人每项赛事一条，更新同一条) | - | - |
| `PUT` | `/api/admin/feature-role-restrictions` | Superuser（超级管理员） | 不限流 (管理员修改角色限制) | - | - |
| `PUT` | `/api/admin/home-pins` | Cap(articles.edit_any) | 不限流 (设置置顶无需限流) | - | - |

## 3. 干部角色能力对照表 (Who Can Do What)

依据系统设计，后台功能实行细粒度能力权限控制，超级管理员与具备特定能力的角色可进入对应后台标签：

| 干部角色 | 对应后台能力 (Capabilities) | 负责后台大类/标签 |
|---|---|---|
| **超级管理员 (Superuser)** | 全量所有能力 (`*`) | 全站后台所有八大分类与所有页面 |
| **赛事总监 (Tournament Director)** | `tournament:manage`<br>`tournament:rosters`<br>`tournament:review`<br>`tournament:export` | 活动（赛事管理、报名审核、队伍编排板、数据导出） |
| **内战裁判 (Scrim Manager)** | `scrim:manage`<br>`scrim:teaming` | 活动（内战管理、内战分队板与自动分队） |
| **资讯编辑 (Editor)** | `article:manage`<br>`article:publish`<br>`home:pins`<br>`categories` | 内容（文章列表、双栏编辑器、首页置顶排序、分类设置、媒体库） |
| **普通会员 (Member)** | 基础身份权限 | 个人中心资料、组队、报名活动、文章评论、头像上传 |
| **访客 (Visitor)** | 公开访问 | 首页、公开资讯阅读、赛事内战公开展示、成员墙浏览 |
