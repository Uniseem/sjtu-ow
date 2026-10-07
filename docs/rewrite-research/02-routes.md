# 02 · 路由与页面全集

来源：两轮调研合并——第一轮的分组盘点 + 第二轮的逐条枚举。基线 `ec44ae4`。

## 0. 依据文件与权限速查

**URL 挂载**（`sjtu_ow/urls.py`）：`/admin/`(backoffice) → `/wagtail/`(wagtail admin) → `/accounts/`(allauth) → `/documents/`(wagtail docs) → 根下按序 include accounts/core/content/teams/members/tournaments/scrims/search/comments → wagtail 前台 catch-all。错误处理器：403/404/500 = `core.views.permission_denied/page_not_found/server_error`，另有 429 模板（无独立 handler，由各视图直接渲染）。

**后台门槛体系**（`backoffice/nav.py:placed` + `backoffice/access.py`）：所有 `/admin/` 页面先过「登录 + `wagtailadmin.access_admin` 权限」（= `can_enter`，每个验证成员经「投稿者」组都有），再过该页 tab 的 `allowed`。速记：

| 代号 | 实际判断 |
|---|---|
| 门禁 | 登录 + `wagtailadmin.access_admin` |
| 文章tab | 仅门禁（普通成员只看自己的） |
| 分类 | `content.change_articlecategory` |
| 网站页面 | `content.permissions.user_can_edit_author` |
| 图片 | Wagtail 图片集合策略 add/change/choose 任一 |
| 赛事管理 | `tournaments.change_tournament`（或超管） |
| 内战管理 | `scrims.change_scrim`（或超管） |
| 用户/角色/战队/字体/排版/预渲染/全站设置/记录 | 超管 |
| 分组 | `members.change_membergroup`（新建/删除还要 add/delete 权限） |
| 报名审核/编队 | 赛事管理 |
| 内容/头像审核 | `moderation.change_moderationitem` |
| 评论tab | `comments.change_comment` |
| 活动数据 | 超管/内容组/赛事管理/内战管理 |
| 手册 | `admin_manual.parts_for(user)` 非空 |

「自动保存」：所有标注"表单(自动存)"的视图，POST 带头 `X-Autosave: 1` 时返回 JSON（`core/autosave.py`），否则普通提交重定向。

---

## 1. `/admin/` 自建后台 —— 100 条（urls.py 中 105 个 `path(` 含 5 个 include 包装）

### 1.1 首页与发信（backoffice_patterns）

| 路径 | 方法 | 视图 | 功能 | 门槛 | 返回 | 备注 |
|---|---|---|---|---|---|---|
| /admin/ | GET | backoffice.views.home.home | 后台首页（待办+自己的文章） | 门禁 | 完整页 | |
| /admin/letters/ | GET | backoffice.views.letters.letters_waiting | 自己触发、还没发的信 | 门禁 | 完整页 | |
| /admin/letters/<uuid:batch>/ | GET+POST | backoffice.views.letters.letters_confirm | 「发信」确认页（勾选发送） | 门禁 | 完整页/重定向 | POST 后回动作原页 |

### 1.2 内容（文章/分类/页面/图片）

| 路径 | 方法 | 视图 | 功能 | 门槛 | 返回 | 备注 |
|---|---|---|---|---|---|---|
| /admin/articles/ | GET | articles.article_list | 文章列表（含状态/筛选） | 文章tab | 完整页 | 普通成员只见自己的 |
| /admin/articles/new/ | GET+POST | articles.article_new | 新建文章 | 文章tab + 栏目 add_subpage | 完整页/重定向 | 表单(自动存)；POST 可直接发布（需 can_publish） |
| /admin/articles/<pk>/ | GET+POST | articles.article_edit | 编辑文章 | 文章tab + 该页 can_edit | 完整页/重定向 | 表单(自动存)；publish 需 can_publish |
| /admin/articles/<pk>/preview/ | GET | articles.article_preview | 最新草稿前台预览 | 文章tab + can_edit | 完整页 | Wagtail serve_preview |
| /admin/articles/<pk>/unpublish/ | POST | articles.article_unpublish | 撤下文章变草稿 | 该页 can_unpublish | 重定向 | |
| /admin/articles/<pk>/delete/ | POST | articles.article_delete | 删除文章 | 该页 can_delete | 重定向 | |
| /admin/categories/ | GET | categories.category_list | 分类列表 | 分类tab | 完整页 | |
| /admin/categories/new/ | GET+POST | categories.category_edit | 新建分类 | 分类tab | 完整页/重定向 | |
| /admin/categories/<pk>/ | GET+POST | categories.category_edit | 编辑分类 | 分类tab | 完整页/重定向 | |
| /admin/categories/<pk>/delete/ | POST | categories.category_delete | 删除分类 | 分类tab + delete 权限 | 重定向 | |
| /admin/pages/ | GET | pages.page_list | 网站页面列表 | 页面tab | 完整页 | |
| /admin/pages/pins/ | GET+POST | pages.home_pins | 首页置顶文章（草稿→发布） | 页面tab | 完整页/重定向 | 表单(自动存)；防并发 stale 检查 |
| /admin/pages/intro/ | GET+POST | pages.index_intro | 资讯栏目简介 | 页面tab | 完整页/重定向 | 表单(自动存)；无栏目时重定向 |
| /admin/pages/<pk>/ | GET+POST | pages.page_edit | 编辑 StandardPage | 页面tab + can_edit | 完整页/重定向 | 表单(自动存) |
| /admin/pages/<pk>/preview/ | GET | pages.page_preview | 页面草稿预览 | 页面tab + can_edit | 完整页 | |
| /admin/images/ | GET | images.image_list | 图片网格（集合/搜索/分页） | 图片tab | 完整页 | |
| /admin/images/upload/ | GET+POST | images.image_upload | 批量上传（一次≤50张） | 图片tab + 集合 add | 完整页/重定向 | ≤5MB，jpg/jpeg/png/webp |
| /admin/images/chooser/ | GET | images.image_chooser | 选图对话框内容（分页） | 图片tab + choose | HTMX 片段 | 对话框内层 |
| /admin/images/chooser/upload/ | POST | images.image_chooser_upload | 对话框内上传一张 | 图片tab + 集合 add | JSON | {id,title,thumb} |
| /admin/images/collections/ | GET | images.collection_list | 图片集合管理 | 超管 | 完整页 | |
| /admin/images/collections/<pk>/rename/ | POST | images.collection_rename | 重命名集合 | 超管 | 重定向 | |
| /admin/images/collections/<pk>/delete/ | POST | images.collection_delete | 删空集合 | 超管 | 重定向 | |
| /admin/images/<pk>/ | GET+POST | images.image_edit | 改标题/集合 | 图片tab + 该图 change | 完整页/重定向 | 表单(自动存) |
| /admin/images/<pk>/delete/ | POST | images.image_delete | 删除图片 | 该图 delete | 重定向 | |

### 1.3 成员（用户/角色/分组）

| 路径 | 方法 | 视图 | 功能 | 门槛 | 返回 | 备注 |
|---|---|---|---|---|---|---|
| /admin/users/ | GET | members.user_list | 用户列表 | 超管 | 完整页 | |
| /admin/users/<pk>/ | GET+POST | members.user_edit | 用户编辑（角色/资料/停用表单） | 超管 | 完整页/重定向 | 表单(自动存) |
| /admin/users/<pk>/active/ | POST | members.user_active | 停用/启用账号 | 超管 | 重定向 | 不能停自己；停用需备注 |
| /admin/users/<pk>/rules/ | POST | members.user_rule_add | 加个人功能规则 | 超管 | 重定向 | |
| /admin/users/rules/<pk>/delete/ | POST | members.user_rule_delete | 删个人规则 | 超管 | 重定向 | |
| /admin/roles/ | GET | members.role_list | 角色列表+功能限制 | 超管 | 完整页 | |
| /admin/roles/<pk>/restrictions/ | POST | members.role_restriction_add | 给角色加功能限制 | 超管 | 重定向 | |
| /admin/roles/restrictions/<pk>/delete/ | POST | members.role_restriction_delete | 删角色限制 | 超管 | 重定向 | |
| /admin/member-groups/ | GET | members.group_list | 成员分组列表 | 分组tab | 完整页 | |
| /admin/member-groups/new/ | GET+POST | members.group_edit | 新建分组 | 分组tab + add 权限 | 完整页/重定向 | 表单(自动存)；首改即建组 |
| /admin/member-groups/<pk>/ | GET+POST | members.group_edit | 编辑分组 | 分组tab + change | 完整页/重定向 | 表单(自动存) |
| /admin/member-groups/<pk>/delete/ | POST | members.group_delete | 删除分组 | 分组tab + delete | 重定向 | |
| /admin/member-groups/<pk>/people/ | GET | members.group_people | 组内搜人（?q=） | 分组tab | JSON | results 数组 |
| /admin/member-groups/<pk>/people/add/ | POST | members.group_member_add | 加人入组 | 分组tab | JSON/重定向 | Accept: application/json 时返回替换块 |
| /admin/member-groups/people/<pk>/remove/ | POST | members.group_member_remove | 移出分组 | 分组tab | JSON/重定向 | 同上 |
| /admin/member-groups/people/<pk>/move/ | POST | members.group_member_move | 组内排序 | 分组tab | JSON/重定向 | |
| /admin/member-groups/people/<pk>/title/ | POST | members.group_member_title | 改组内头衔 | 分组tab | JSON/重定向 | |
| /admin/settings/site/ | GET+POST | settings.site_settings | 全站设置（SMTP/AI 审核/环境） | 超管 | 完整页/重定向 | 表单(自动存)；密钥回显置空 |
| /admin/log/ | GET | settings.action_log | 操作记录（页+模型日志合并） | 超管 | 完整页 | 50/页，可筛选 |

### 1.4 活动（include 的四个命名空间 + 独立路由）

| 路径 | 方法 | 视图 | 功能 | 门槛 | 返回 | 备注 |
|---|---|---|---|---|---|---|
| /admin/tournaments/ | GET | events.tournament_list | 赛事列表（状态/模式筛选） | 赛事管理 | 完整页 | |
| /admin/tournaments/new/ | GET+POST | events.tournament_add | 新建赛事 | 赛事管理 | 完整页/重定向 | 表单(自动存) |
| /admin/tournaments/edit/<pk>/ | GET+POST | events.tournament_edit | 编辑赛事 | 赛事管理 | 完整页/重定向 | 表单(自动存) |
| /admin/tournaments/copy/<pk>/ | GET+POST | events.tournament_copy | 复制赛事（时间整体后移） | 赛事管理 | 完整页/重定向 | 表单(自动存) |
| /admin/tournaments/delete/<pk>/ | GET+POST | events.tournament_delete | 删除未发布草稿 | 赛事管理 + can_delete | 确认页/重定向 | 发布过的只能取消 |
| /admin/scrims/ | GET | events.scrim_list | 内战列表 | 内战管理 | 完整页 | |
| /admin/scrims/new/ | GET+POST | events.scrim_add | 新建内战 | 内战管理 | 完整页/重定向 | 表单(自动存) |
| /admin/scrims/edit/<pk>/ | GET+POST | events.scrim_edit | 编辑内战 | 内战管理 | 完整页/重定向 | 表单(自动存) |
| /admin/scrims/copy/<pk>/ | GET+POST | events.scrim_copy | 复制内战 | 内战管理 | 完整页/重定向 | 表单(自动存) |
| /admin/scrims/delete/<pk>/ | GET+POST | events.scrim_delete | 删除内战草稿 | 内战管理 + can_delete | 确认页/重定向 | |
| /admin/teams/ | GET | members.team_list | 战队列表（含卡壳状态） | 超管 | 完整页 | |
| /admin/teams/edit/<pk>/ | GET+POST | members.team_edit | 后台编辑战队资料 | 超管 | 完整页/重定向 | 表单(自动存)；触发页面/AI 巡查 |
| /admin/comments/ | GET | comments.comment_list | 评论巡查列表 | 评论tab | 完整页 | |
| /admin/comments/<pk>/<str:action>/ | POST | comments.comment_action | 评论处理（删除/恢复等） | 评论tab | 重定向 | action 由视图校验 |
| /admin/announce/<kind>/<pk>/ | GET+POST | events.announce → core.announce_admin.announce_view | 「通知全体/报名的人」确认+发送 | 按 kind：article=发布权限、tournament/scrim=相应管理 | 确认页/重定向 | ?to=participants 第二种受众 |

### 1.5 活动动作与编队

| 路径 | 方法 | 视图 | 功能 | 门槛 | 返回 | 备注 |
|---|---|---|---|---|---|---|
| /admin/markdown/preview/ | POST | content.markdown_views.preview | Markdown 渲染预览 | 内容tab 文章 | HTML 片段 | 文本上限截断 |
| /admin/markdown/image/ | POST | content.markdown_views.upload_image | 编辑器里传图 | 上传图片权限 | JSON | {url} 或 403/400 |
| /admin/tournaments/<pk>/teams/ | GET+POST | tournaments.teams_admin.board_view | 报名编队板（散人池组队） | 赛事管理 | 完整页/重定向 | POST action=save/dissolve |
| /admin/tournaments/<pk>/action/<str:action>/ | GET+POST | tournaments.admin_views.tournament_action | 发布/结束等确认动作 | 赛事管理 | 确认页/重定向 | publish 可勾选顺带群发通知 |
| /admin/tournaments/<pk>/cancel/ | GET+POST | tournaments.admin_views.tournament_cancel | 取消赛事（填原因） | 赛事管理 | 确认页/重定向 | 原因≤300字 |
| /admin/scrims/<pk>/cancel/ | GET+POST | scrims.admin_views.scrim_cancel | 取消内战 | 内战管理 | 确认页/重定向 | |
| /admin/scrims/<pk>/split/ | GET+POST | scrims.split_admin.split_view | 分队页（选人/生成/保存） | 内战管理 | 完整页/重定向 | 表单(自动存)；action=select/generate/save |
| /admin/scrims/<pk>/split/text/ | GET | scrims.split_admin.copy_view | 分队结果纯文本 | 内战管理 | text/plain | 供复制/脚本抓取 |
| /admin/scrims/<pk>/<str:action>/ | GET+POST | scrims.admin_views.scrim_action | 发布/结束等确认动作 | 内战管理 | 确认页/重定向 | |
| /admin/teams/<pk>/assign-captain/ | GET+POST | teams.admin_views.admin_assign_captain | 指定新队长（搜人） | 超管 | 完整页/重定向 | |
| /admin/teams/<pk>/disband/ | GET+POST | teams.admin_views.admin_disband | 解散战队 | 超管 | 确认页/重定向 | |

### 1.6 审核（报名/内容/头像）

| 路径 | 方法 | 视图 | 功能 | 门槛 | 返回 | 备注 |
|---|---|---|---|---|---|---|
| /admin/registrations/ | GET | tournaments.review_admin.review_index | 报名审核列表（筛选） | 赛事管理 | 完整页 | |
| /admin/registrations/bulk-approve/ | POST | review_admin.review_bulk_approve | 批量通过 | 赛事管理 | 重定向 | 尊重 next |
| /admin/registrations/export.csv | GET | review_admin.review_export | 导出当前筛选 CSV | 赛事管理 | CSV 文件 | 带BOM；联系方式列需额外权限；导出记日志 |
| /admin/registrations/<pk>/ | GET | review_admin.review_detail | 报名详情（通过/驳回） | 赛事管理 | 完整页 | |
| /admin/registrations/<pk>/action/ | POST | review_admin.review_action | approve/reject/revoke | 赛事管理 | 重定向 | |
| /admin/moderation/ | GET | moderation.admin_views.moderation_index | AI 巡查记录列表 | 内容审核 | 完整页 | 含今日用量 |
| /admin/moderation/try/ | POST | moderation.admin_views.moderation_try | 「试一下」AI 连通 | 内容审核 | 重定向 | 可回设置页 |
| /admin/moderation/<pk>/ | GET | moderation.admin_views.moderation_detail | 待复核内容详情 | 内容审核 | 完整页 | 含作者历史 |
| /admin/moderation/<pk>/action/ | POST | moderation.admin_views.moderation_action | 处置（记录结果） | 内容审核 | 重定向 | |
| /admin/moderation/<pk>/ask-author/ | POST | moderation.admin_views.moderation_ask_author | 发信要求作者修改 | 内容审核 | 重定向 | 信走 held letters |
| /admin/avatars/ | GET | moderation.avatar_admin.avatar_review | 头像审核（三状态页签） | 内容审核 | 完整页 | |
| /admin/avatars/<pk>/action/ | POST | moderation.avatar_admin.avatar_review_action | 撤下头像 | 内容审核 | 重定向 | 尊重 next |

### 1.7 数据、手册、设置

| 路径 | 方法 | 视图 | 功能 | 门槛 | 返回 | 备注 |
|---|---|---|---|---|---|---|
| /admin/activity/ | GET | core.activity.activity_view | 活动数据汇总 | 活动数据权限 | 完整页/CSV | ?format=csv 下载；周期参数 |
| /admin/manual/ | GET | core.admin_manual.manual_view | 后台手册 | 手册权限（按角色出部分） | 完整页 | |
| /admin/settings/core/send-test-email/ | POST | core.views.send_site_test_email | 发测试邮件给自己 | `core.change_sitesettings` | 重定向 | |
| /admin/settings/core/try-offsite/ | POST | core.views.try_offsite_backup | 测试对象存储备份 | `core.change_sitesettings` | 重定向 | |
| /admin/settings/fonts/ | GET | core.fonts.admin_views.font_index | 字体库列表 | 超管 | 完整页 | |
| /admin/settings/fonts/add/ | GET+POST | fonts.font_add | 添加字体（上传/URL/Google 三表单） | 超管 | 完整页/重定向 | |
| /admin/settings/fonts/faces.css | GET | fonts.font_faces_css | 全部 @font-face 规则 | 超管 | CSS 文件 | 供后台预览 |
| /admin/settings/fonts/<pk>/ | GET+POST | fonts.font_detail | 字体详情（加字重） | 超管 | 完整页/重定向 | |
| /admin/settings/fonts/<pk>/reprocess/ | POST | fonts.font_reprocess | 重新切片排队 | 超管 | 重定向 | |
| /admin/settings/fonts/<pk>/delete/ | GET+POST | fonts.font_delete | 删字体（确认） | 超管 | 确认页/重定向 | 使用中会拒绝 |
| /admin/settings/fonts/weights/<pk>/download/ | GET | fonts.font_face_download | 下载字重文件（zip） | 超管 | 文件下载 | zip 或原始文件 |
| /admin/settings/fonts/weights/<pk>/delete/ | POST | fonts.font_face_delete | 删字重 | 超管 | 重定向 | 排版占用时拒绝 |
| /admin/settings/typography/ | GET+POST | fonts.typography | 排版设置（区域×字重表单集） | 超管 | 完整页/重定向 | 表单(自动存)；保存后重生成站点 CSS |
| /admin/settings/prerender/ | GET | core.prerender_admin.prerender_index | 静态页面记录列表 | 超管 | 完整页 | |
| /admin/settings/prerender/rebuild/ | POST | prerender_admin.prerender_rebuild | 全量重建预渲染 | 超管 | 重定向 | |
| /admin/settings/prerender/clear/ | POST | prerender_admin.prerender_clear | 清空预渲染 | 超管 | 重定向 | |

---

## 2. 前台路由 —— 72 条

### 2.1 core（13 条）

| 路径 | 方法 | 视图 | 功能 | 门槛 | 返回 | 备注 |
|---|---|---|---|---|---|---|
| / | GET | core.views.home | 首页（转 HomePage.serve） | 公开 | 完整页 | 预渲染目标（kind=home）；无站点时降级模板 |
| /healthz | GET | core.views.healthz | 存活/就绪探针 | 公开（详情仅超管） | JSON | csrf_exempt；503/200 |
| /favicon.ico | GET | core.views.site_icon | 转发静态图标 | 公开 | 301 重定向 | → /static/img/favicon.ico |
| /apple-touch-icon.png | GET | core.views.site_icon | 同上 | 公开 | 301 重定向 | |
| /_fragments/state/ | GET | core.views.state_fragment | 预渲染页个性化槽位填充 | 公开 | HTMX 片段 | 限流 120/分/IP；no-store；补 CSRF cookie |
| /unsubscribe/<token>/ | GET+POST | core.views.announcements_unsubscribe | 退订活动通知 | 签名 token（免登录） | 完整页 | POST 免 CSRF（RFC 8058 一键退订） |
| /calendar/<token>.ics | GET | core.views.calendar_feed | 个人日历订阅 | 签名 token（免登录） | ICS 文件 | 限流 30/分/IP；max-age=900；noindex |
| /letters/ | GET | core.held_views.letters_waiting | 我的待发信 | 登录 | 完整页 | never_cache |
| /letters/<uuid:batch>/ | GET+POST | core.held_views.letters_confirm | 发信确认页 | 登录 | 完整页/重定向 | POST 决定发哪些 |
| /letters/<uuid:batch>/<pk>/ | GET | core.held_views.letters_preview | 单封信预览（iframe） | 登录 + 本人 | 完整页(邮件HTML) | X-Frame sameorigin；未登录 404 |
| /_styleguide/ | GET | core.styleguide.styleguide | 样式指南 | `wagtailadmin.access_admin`（否则404） | 完整页 | |
| /_styleguide/emails/ | GET | core.styleguide.styleguide_emails | 邮件模板列表 | 同上 | 完整页 | |
| /_styleguide/emails/<slug:key>/ | GET | core.styleguide.styleguide_email | 单个邮件预览 | 同上 | 完整页(邮件HTML) | 独立 CSP 允许 inline style |

### 2.2 accounts「我的」（13 条）

| 路径 | 方法 | 视图 | 功能 | 门槛 | 返回 | 备注 |
|---|---|---|---|---|---|---|
| /me/ | GET+POST | accounts.views.me_profile | 资料页（昵称等） | 登录 | 完整页 | |
| /me/avatar/ | POST | accounts.views.me_avatar_upload | 上传头像（进审核） | 登录 | 重定向/完整页 | 失败重渲染资料页 |
| /me/avatar/remove/ | POST | accounts.views.me_avatar_remove | 撤回头像用默认 | 登录 | 重定向 | |
| /me/game-accounts/ | GET+POST | accounts.views.me_game_accounts | 游戏 ID 管理 | 登录 | 完整页/HTMX 片段 | 表单成功替换 #account_list |
| /me/game-accounts/<pk>/ | GET+POST | accounts.views.me_game_account_edit | 编辑单个游戏 ID | 登录+本人 | 完整页/HTMX 片段 | |
| /me/game-accounts/<pk>/delete/ | POST | accounts.views.me_game_account_delete | 删除游戏 ID | 登录+本人 | HTMX 片段/重定向 | |
| /me/contacts/ | GET+POST | accounts.views.me_contacts | 联系方式管理 | 登录 | 完整页/HTMX 片段 | |
| /me/contacts/<pk>/ | GET+POST | accounts.views.me_contact_edit | 编辑联系方式 | 登录+本人 | 完整页/HTMX 片段 | |
| /me/contacts/<pk>/delete/ | POST | accounts.views.me_contact_delete | 删除联系方式 | 登录+本人 | HTMX 片段/重定向 | |
| /me/security/ | GET | accounts.views.me_security | 账号安全（改邮箱/密码入口、通知开关、导出/注销） | 登录 | 完整页 | |
| /me/notifications/ | POST | accounts.views.me_notifications | 活动通知开关 | 登录 | 重定向 | |
| /me/export/ | GET | accounts.views.me_export | 导出个人数据 | 登录 | JSON 文件下载 | 限流 5 次/小时/人 |
| /me/delete/ | GET+POST | accounts.views.me_delete | 注销账号（验密码） | 登录 | 完整页/重定向 | 限流 5 次/小时；有阻碍时拒绝 |

### 2.3 content（3 条）

| 路径 | 方法 | 视图 | 功能 | 门槛 | 返回 | 备注 |
|---|---|---|---|---|---|---|
| /submit/ | GET | content.views.submit_entry | 前台投稿入口（跳后台或说明原因） | 公开（有权限才跳转） | 完整页/重定向 | 需登录+邮箱验证+ARTICLE_SUBMIT 功能 |
| /sitemap.xml | GET | content.views.sitemap_xml | 站点地图 | 公开 | XML 文件 | |
| /robots.txt | GET | content.views.robots_txt | 爬虫规则 | 公开 | text/plain | 测试环境额外 Disallow |

### 2.4 teams（14 条）

| 路径 | 方法 | 视图 | 功能 | 门槛 | 返回 | 备注 |
|---|---|---|---|---|---|---|
| /teams/ | GET | teams.views.team_index | 战队列表 | 公开 | 完整页 | 预渲染目标 |
| /teams/new/ | GET+POST | teams.views.team_create | 创建战队 | 登录 | 完整页/重定向 | 限流 3 次/天；队长数上限 |
| /teams/<pk>/ | GET | teams.views.team_detail | 战队详情 | 公开 | 完整页 | 预渲染目标 |
| /teams/<pk>/apply/ | GET+POST | teams.views.team_apply | 申请入队 | 登录 | 完整页/重定向 | 限流（APPLY_LIMIT/天） |
| /teams/<pk>/manage/ | GET+POST | teams.views.team_manage | 队长管理页（资料+申请+成员） | 队长或超管（否则404） | 完整页/重定向 | profile 表单支持自动存 |
| /teams/<pk>/leave/ | POST | teams.views.team_leave | 退出战队 | 登录+成员 | 重定向 | |
| /teams/<pk>/members/remove/ | POST | teams.views.member_remove | 移出成员 | 队长 | 重定向 | |
| /teams/<pk>/alumni/<alumnus_pk>/remove/ | POST | teams.views.alumnus_remove | 删校友记录 | 队长 | 重定向 | |
| /teams/<pk>/members/transfer/ | POST | teams.views.captain_transfer | 转让队长 | 队长 | 重定向 | |
| /teams/<pk>/disband/ | POST | teams.views.team_disband | 解散战队 | 队长 | 重定向 | 有进行中报名时受阻 |
| /teams/applications/<pk>/approve/ | POST | teams.views.application_approve | 批准入队 | 队长 | 重定向 | |
| /teams/applications/<pk>/reject/ | POST | teams.views.application_reject | 拒绝申请 | 队长 | 重定向 | |
| /teams/applications/<pk>/cancel/ | POST | teams.views.application_cancel | 撤回自己的申请 | 申请人 | 重定向 | |
| /me/teams/ | GET | teams.views.me_teams | 我的战队 | 登录 | 完整页 | |

### 2.5 members（2 条）

| 路径 | 方法 | 视图 | 功能 | 门槛 | 返回 | 备注 |
|---|---|---|---|---|---|---|
| /members/ | GET | members.views.members_index | 成员展示墙（按位置/空闲筛选） | 公开 | 完整页 | 预渲染目标；筛选走动态查询 |
| /members/<pk>/ | GET | members.views.member_detail | 成员主页 | 公开 | 完整页 | |

### 2.6 tournaments（10 条）

| 路径 | 方法 | 视图 | 功能 | 门槛 | 返回 | 备注 |
|---|---|---|---|---|---|---|
| /tournaments/ | GET | tournaments.views.tournament_index | 赛事列表（按阶段分组） | 公开 | 完整页 | 预渲染目标 |
| /tournaments/<pk>/ | GET | tournaments.views.tournament_detail | 赛事详情 | 公开（未发布404） | 完整页 | 预渲染目标；个性化动作走 slot 片段 |
| /tournaments/<pk>/register/ | GET+POST | tournaments.registration_views.register | 战队报名（选名单提交） | 登录+队长 | 完整页/重定向 | 非队长重定向回详情 |
| /tournaments/<pk>/signup/ | GET+POST | registration_views.individual_signup | 个人报名（散人池） | 登录 | 完整页/重定向 | |
| /tournaments/<pk>/signup/cancel/ | POST | registration_views.individual_cancel | 取消个人报名 | 登录+本人 | 重定向 | |
| /registrations/<pk>/ | GET | registration_views.registration_detail | 报名单详情 | 登录 + 可见性（队长/名单成员/管理） | 完整页 | 队长可改/重提 |
| /registrations/<pk>/withdraw/ | POST | registration_views.registration_withdraw | 队长撤回报名 | 登录+队长 | 重定向 | |
| /registrations/<pk>/leave/ | POST | registration_views.registration_leave | 散人退出报名 | 登录+名单内 | 重定向 | |
| /me/registrations/ | GET | registration_views.me_registrations | 我的报名 | 登录 | 完整页 | |
| /me/registrations/calendar/new-address/ | POST | registration_views.me_calendar_reset | 重置日历订阅地址 | 登录 | 重定向 | 旧地址作废 |

### 2.7 scrims（6 条）

| 路径 | 方法 | 视图 | 功能 | 门槛 | 返回 | 备注 |
|---|---|---|---|---|---|---|
| /scrims/ | GET | scrims.views.scrim_index | 内战列表（进行中/已结束） | 公开 | 完整页 | 预渲染目标 |
| /scrims/<pk>/ | GET | scrims.views.scrim_detail | 内战详情+报名区 | 公开 | 完整页 | 预渲染目标；报名人数变化会刷新静态页 |
| /scrims/<pk>/signup/ | POST | scrims.views.scrim_signup | 报名内战（选 ID+位置） | 登录 | 重定向 | 未登录 → /accounts/login/?next= |
| /scrims/<pk>/cancel/ | POST | scrims.views.scrim_cancel_signup | 取消报名 | 登录+本人 | 重定向 | 注意与后台 /admin/scrims/<pk>/cancel/ 不同视图 |
| /me/scrims/ | GET | scrims.views.me_scrims | 我的内战（含分队去向） | 登录 | 完整页 | |
| /_fragments/scrims/<pk>/actions/ | GET | scrims.views.scrim_actions_fragment | 详情页个性化动作槽 | 公开 | HTMX 片段 | OOB swap；no-store |

### 2.8 search（1 条）与 comments（10 条）

| 路径 | 方法 | 视图 | 功能 | 门槛 | 返回 | 备注 |
|---|---|---|---|---|---|---|
| /search/ | GET | search.views.search | 全站搜索（文章/赛事/内战/战队/成员） | 公开 | 完整页 | 限流 30/分/IP，超限渲染 429 页 |
| /comments/<page_pk>/new/ | POST | comments.views.create | 发表评论 | 登录（服务层再查评论资格） | HTMX 片段/重定向 | 限流 3/分 + 100/天 |
| /comments/<page_pk>/more/ | GET | comments.views.more | 「加载更多」评论 | 公开 | HTMX 片段 | ?page=&sort= |
| /comments/<pk>/reply/ | POST | comments.views.reply | 回复评论 | 登录 | HTMX 片段/重定向 | 与发表同限流 |
| /comments/<pk>/hide/ | POST | comments.views.hide | 隐藏评论 | `comments.change_comment` | HTMX 片段/重定向 | |
| /comments/<pk>/unhide/ | POST | comments.views.unhide | 恢复评论 | 同上 | HTMX 片段/重定向 | |
| /comments/<pk>/like/ | POST | comments.views.like | 点赞切换 | 登录 | HTMX 片段/重定向 | 限流 60/分/人 |
| /comments/<pk>/edit/ | POST | comments.views.edit | 编辑自己的评论 | 登录+作者 | HTMX 片段/重定向 | 与发帖共用限流 |
| /comments/<pk>/delete/ | POST | comments.views.delete | 删评论（作者/管理） | 登录 | HTMX 片段/重定向 | |
| /comments/<pk>/pin/ | POST | comments.views.pin | 置顶 | `comments.change_comment` | HTMX 片段/重定向 | |
| /comments/<pk>/unpin/ | POST | comments.views.unpin | 取消置顶 | 同上 | HTMX 片段/重定向 | |

---

## 3. allauth `/accounts/` —— 实际生效 14 条

settings（`sjtu_ow/settings/base.py`）：`ACCOUNT_LOGIN_METHODS={"email"}`、`ACCOUNT_SIGNUP_FIELDS=["email*","password1*","password2*"]`（无 username、无 phone）、`ACCOUNT_EMAIL_VERIFICATION="mandatory"`、`ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED=True`（6位数字码，3次/15分钟）、`ACCOUNT_PASSWORD_RESET_BY_CODE_ENABLED=True`（3次/3分钟）、`ACCOUNT_CHANGE_EMAIL=True`、`ACCOUNT_REAUTHENTICATION_REQUIRED=True`。未安装 `allauth.socialaccount/mfa/usersessions`，`LOGIN_BY_CODE_ENABLED` 默认 False。表单全部换成 `accounts.allauth_forms.*`。

| 路径 | URL name | 方法 | 功能 | 门槛 | 返回 | 备注 |
|---|---|---|---|---|---|---|
| /accounts/login/ | account_login | GET+POST | 邮箱+密码登录 | 公开 | 完整页 | 限流 30/m/ip + 失败 10/m/ip,5/300s/key；LOGIN_URL 指向这里 |
| /accounts/logout/ | account_logout | GET(确认页)+POST | 登出 | 登录 | 完整页/重定向 | POST 才真正登出；回 / |
| /accounts/inactive/ | account_inactive | GET | 「账号已停用」提示页 | 公开 | 完整页 | |
| /accounts/signup/ | account_signup | GET+POST | 注册（邮箱+两次密码，附加表单） | 公开 | 完整页/重定向 | 限流 20/m/ip；注册后强制验证邮箱 |
| /accounts/reauthenticate/ | account_reauthenticate | GET+POST | 重新输密码（改邮箱前） | 登录 | 完整页/重定向 | 限流 10/m/user；5分钟窗口 |
| /accounts/email/ | account_email | GET+POST | 邮箱管理（换登录邮箱，by-code 验证） | 登录（变更需 reauth） | 完整页/重定向 | 限流 manage_email 10/m/user；换邮箱=全流程 |
| /accounts/confirm-email/ | account_email_verification_sent | GET+POST | 输入验证码页（含重发） | 半登录态（signup 中间态） | 完整页 | by-code 模式；重发限 1/10s/key |
| /accounts/password/change/ | account_change_password | GET+POST | 改密码（要旧密码） | 登录 | 完整页/重定向 | 限流 5/m/user |
| /accounts/password/set/ | account_set_password | GET+POST | 首次设密码（无密码用户） | 登录 | 完整页/重定向 | 常规用户不出现 |
| /accounts/password/reset/ | account_reset_password | GET+POST | 忘记密码：输邮箱收码 | 公开 | 完整页/重定向 | 限流 20/m/ip,5/m/key |
| /accounts/password/reset/confirm/ | account_confirm_password_reset_code | GET+POST | 输入 6 位重置码 | 公开（持码会话） | 完整页/重定向 | 限流 reset_password_from_key 20/m/ip；错 3 次作废 |
| /accounts/password/reset/complete/ | account_complete_password_reset | GET+POST | 码验证后设新密码 | 公开（持码会话） | 完整页/重定向 | 未确认码会重定向回 confirm |
| /accounts/password/reset/done/ | account_password_reset_completed | GET | 重置完成页 | 公开 | 完整页 | |
| /accounts/login/code/confirm/ | account_confirm_login_code | GET+POST | （登录码确认） | — | 重定向 | **已注册但本配置下不可用**：无 code 流程时直接弹回 /accounts/login/ |

**本配置下不存在的默认 URL**（重构可忽略）：`/accounts/confirm-email/<key>/`（链接验证被 by-code 取代）、`/accounts/password/reset/key/<uidb36>-<key>/`、`/accounts/password/reset/key/done/`、`/accounts/phone/*`、`/accounts/2fa/*`、`/accounts/sessions/*`、`/accounts/3rdparty/*`、`/accounts/social/*`、`/accounts/signup/passkey/`。另：不存在"用户名登录"的独立 URL——`/accounts/login/` 只按邮箱认证。

---

## 4. Wagtail 侧

### 4.1 `/wagtail/` 管理入口（超管后备；所有条目经 require_admin_access + never_cache）

| 入口 | 说明 | 本项目备注 |
|---|---|---|
| /wagtail/ | 后台首页 dashboard | 项目配色；日常用 /admin/，这里仅超管后备 |
| /wagtail/login/ | Wagtail 自带登录页 | 未认证访问 /wagtail/* 会被弹到 /accounts/login/；该页本身仍可渲染（**217-04-1：绕过 allauth 且不限次**） |
| /wagtail/logout/ | 登出 | |
| /wagtail/pages/、/wagtail/pages/<id>/、.../results/ | 页面树浏览 | 投稿者只见已发布+自己的草稿（construct_explorer_page_queryset 钩子） |
| /wagtail/pages/<id>/edit/、add/、copy/、delete/、move/、publish/ 等整组 | 页面编辑动作 | 编辑主要走 /admin/，这里是后备 |
| /wagtail/images/、/wagtail/images/<id>/、/wagtail/images/chooser/* | Wagtail 图片库+选图器 | 主用 /admin/images/ |
| /wagtail/documents/（管理）| Wagtail 文档库 | 基本未用（217-04-7 直链风险） |
| /wagtail/users/、/wagtail/users/<id>/、/wagtail/groups/* | 用户/用户组 | 新建与删除用户被禁用；编辑用项目自己的表单 |
| /wagtail/snippets/ | 片段索引 | 项目未注册任何 snippet |
| /wagtail/redirects/ | 重定向管理 | RedirectMiddleware 前台生效 |
| /wagtail/settings/core/sitesettings/ | 全站设置（Wagtail 侧） | 与 /admin/settings/site/ 同一数据 |
| /wagtail/reports/* | 报表 | |
| /wagtail/account/ | 账号页 | 改密码/改邮箱入口被禁（走 allauth） |
| /wagtail/collections/、workflows/、bulk/、api/、tag-autocomplete/、choose-page/*、editing-sessions/ 等 | 其余内部机制 | 重构时整体可弃 |

### 4.2 `/documents/`（2 条）

| 路径 | 方法 | 功能 | 门槛 | 返回 |
|---|---|---|---|---|
| /documents/<id>/<filename> | GET | 文档文件下发 | 公开（有密码限制时验证 cookie） | 文件（或重定向） |
| /documents/authenticate_with_password/<restriction_id>/ | GET+POST | 文档密码验证表单 | 公开 | 完整页/重定向 |

### 4.3 前台 catch-all（3 条，wagtail/urls.py）

| 路径 | 方法 | 功能 | 备注 |
|---|---|---|---|
| /_util/authenticate_with_password/<id>/<page_id>/ | GET+POST | 页面级密码限制验证 | 未用 |
| /_util/login/ | GET+POST | 私有页登录（Django LoginView） | **217-04-1：第二侧门** |
| 任意 `([\w\-]+/)*` | GET | wagtail_serve 按 URL 落位 | 吃它的页面：ArticleIndexPage(/news/)、ArticlePage(/news/<slug>/)、StandardPage(任意顶级 slug)；HomePage 名义上可但根路径已被 core.views.home 接管。全部为预渲染目标 |

媒体文件：DEBUG 下 /media/ 由 static() 服务（生产由 Caddy 直出）。

---

## 5. 汇总数字

| 区域 | 条数 | 页面级（完整 HTML） | 动作/接口级 |
|---|---|---|---|
| /admin/ 自建后台 | **100**（105 个 path() 含 5 个 include） | 62 | 38（POST 动作 25、JSON 7、HTMX 片段 2、CSV 1、CSS 1、纯文本 1、文件下载 1） |
| 前台九应用 | **72**（core 13、accounts 13、content 3、teams 14、members 2、tournaments 10、scrims 6、search 1、comments 10） | 34 | 38 |
| allauth /accounts/ | **14**（实际可用 13） | 13 | 1 条惰性 |
| /documents/ | 2 | 1 | 1 |
| Wagtail 前台 catch-all | 3 | 3 | — |
| **合计（不含 /wagtail/ 内部）** | **191** | **113** | **78** |

给 Vue Router / Go 路由器的两条总体提示：① 大量"表单页"同时承担 GET（渲染）、POST（提交）、POST+`X-Autosave:1`（JSON 自动保存）三种行为，迁移时按内容协商拆分；② 预渲染覆盖 `/`、`/news/**`、StandardPage、`/members/`、`/teams/**`、`/tournaments/**`、`/scrims/**`，个性化部分由 `/_fragments/state/` 与 `/_fragments/scrims/<pk>/actions/` 两个片段端点回填——SPA 重构对应"页面壳 + 客户端补数据"模式。

---

## 6. 预渲染机制摘要（第一轮调研）

**目标声明**：各应用在 `AppConfig.ready()` 里注册 provider（`core/prerender.py:84-100`，结果缓存 60s）：
- `content/prerender_targets.py:6`：所有 live+public 的 HomePage、ArticleIndexPage、ArticlePage、StandardPage
- `members/prerender_targets.py:6`：`/members/`；`teams/`: `/teams/` + 未解散战队详情；`tournaments/`: 列表 + 列出的赛事；`scrims/`: 列表 + 公开内战
- `/` 恒为目标。**不预渲染**：`/members/<pk>/`、`/search/`、带查询参数的页面

**生成方式**（prerender.py:151-261）：Django test Client 匿名请求 + `x-prerender:1` 头；拒绝非 200、非 HTML、带任何 Set-Cookie、含 `csrfmiddlewaretoken/csrf_token/sessionid` 的页面（安全红线，prerender.py:29-33,174-181）；原子写 `prerendered/<path>/index.html` + `.br`(q11) + `.gz` 三个孪生文件；DB 记 `PrerenderedPage`；404/410 → 直接删文件。

**触发**：① 信号与服务层 `request_page(path)`（30 秒去抖，on_commit 入队）；`request_removal(path)` 内容转私密时**同步立即删**；`request_all_soon()` 全量重建。② `PrerenderMissMiddleware`：匿名 GET 命中目标但文件缺失时排队生成。③ crontab 每日 04:15 全量重建。④ 后台人工 `/admin/settings/prerender/`。

**失败处理**：status=FAILED + error，进后台待办；删除失败由 worker 重试。

**Caddy**：`@prerendered` 用 try_files 探测 `/srv/prerendered`，命中直出 + page_security 头组 + `max-age=0, must-revalidate`；`/admin/* /wagtail/* /accounts/* /me/* /_fragments/* /healthz`、非 GET/HEAD、带 query 一律回源 Django。

**登录态补齐（state.js）**：`LoggedInHintCookieMiddleware` 给登录用户发非 HttpOnly 提示 cookie `ow_logged_in`/`ow_flash`；`state.js` 无 cookie 零请求，有则收集 `[data-slot]` 名请求 `/_fragments/state/?slots=…`，OOB 填回（8 秒超时兜底）；动态渲染页 body 带 `data-state-filled="1"` 跳过。详见 `08-contracts.md`。

## 7. 模板组织摘要（第一轮调研；逐文件清单见 08）

根 `templates/`：`base.html`（前台骨架）、`components/`（22 个共享组件）、`account/`（覆盖 allauth 全套 + 邮件文案 + toast 文案）、`allauth/layouts/`、`me/`（个人中心）、`slots/`（个性化插槽片段）、`email/`（信纸框架）、`errors/`（403/404/429/500/maintenance）、`wagtailadmin/wagtailusers/`（覆盖 Wagtail）。各应用 `templates/`：content（CMS 页 + sitemap + 编辑器 widget）、backoffice（后台全套 + parts + widgets）、core（styleguide、letters、fonts、admin、prerender）、scrims/teams/tournaments（前台页 + slots + admin 板）、comments（HTMX 局部）、members、moderation、search、accounts。
