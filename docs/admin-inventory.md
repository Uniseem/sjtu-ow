# 重写前的后台：结构和逻辑（196 调研）

196 轮重写后台前的调研记录。**这份写的是 2026-10-05、195 轮之后的样子**，重写后不再更新；新后台的设计在 `docs/admin.md`。用途：重写时逐条对照，保证每个页面原来管的规则在新后台里都还在。

## 1. 总体

- 整个后台是 Wagtail 8 的管理界面，挂在 `/admin/`（`sjtu_ow/urls.py` 里 `path("admin/", include(wagtailadmin_urls))`）。Django 自带的 admin 应用装了但没有网址
- 自定义页面全部通过 Wagtail 的 `register_admin_urls` 钩子挂在 `/admin/` 下面，模板继承 `wagtailadmin/generic/base.html`，用 Wagtail 的样式类（`button`、`help-block`、`listing`……）
- 外观：`static/css/admin.css` 用 `insert_global_admin_css` 注入，把前台的颜色令牌对到 Wagtail 的变量上（189、191）
- 菜单：`construct_main_menu` 三个钩子（order 900 整理、1000 投稿者过滤、1100 拼成八个大类），`core/admin_sections.py` 按网址前缀决定页面属于哪个大类和标签，`templates/wagtailadmin/base.html` 用 `{% section_tabs %}` 往 Wagtail 的内容栏里插标签条（193）
- 编号一律用 `<id:pk>` 转换器（`core/apps.py` 注册）
- 操作记录：`wagtail.log_actions.log`，`core/admin_log.py` 定义了 14 个自定义动作，另有导出名单、复核处理、要求作者修改各一个
- 进后台的权限：Wagtail 的 `wagtailadmin.access_admin`。验证过邮箱的成员都在「投稿者」组，都能进

## 2. 各页面

### 2.1 首页

| 内容 | 实现 | 规则 |
|---|---|---|
| 问候和快捷按钮 | `core/admin_home.py` `WelcomePanel`、`actions()` | 「写文章」看文章栏目能不能加子页面；「新建赛事」「新建内战」看各自的 `can_manage`；「打开网站」所有人 |
| 待办 | `core/admin_todo.py` `TodoPanel`、`todo_rows()`，`has_duties()` 决定显不显示 | 待审核的报名、等待编队的人数、开赛 3 天没标结束的赛事、报名截止还没分队的内战；超级管理员另有：静态页生成失败、worker 没在运行、队长停用的战队、AI 调用失败、备份太旧或异地上传失败、重试后仍没发出的邮件 |
| 上线清单 | `core/admin_setup.py` `SetupPanel`，只给超级管理员 | 邮件、协议有没有【】、AI、异地备份、内容编辑组有没有人、关于我们、站点信息、默认封面和头像图库等，每项链到去改的地方 |
| 我的投稿 | `content/wagtail_hooks.py` `SubmitterHomePanel`，纯投稿者才有 | 自己的文章，状态「已发布 / 草稿」，新建投稿按钮 |

### 2.2 内容

| 页面 | 网址 / 实现 | 权限 | 必须保留的规则 |
|---|---|---|---|
| 文章列表、编辑、新建 | Wagtail 页面树和页面编辑器（`/admin/pages/<资讯栏目>/`、`wagtailadmin_pages:add/edit`）；修订、预览、定时上线下线、锁定都是 Wagtail 自带 | 页面权限：内容编辑在首页下有改、发布、锁定；认证作者和投稿者在文章栏目有新建、发布；`OwnArticlesPermissionTester` 让内容编辑和超管以外的人只能发布、撤下自己的（195）；页面树对超管、内容编辑以外的人只显示已发布的和自己的（`construct_explorer_page_queryset` 加上改写 `PagePermissionPolicy.explorable_instances`） | `ArticlePageForm`：作者字段只有内容编辑和超管能改；开放评论开关投稿者看不到；投稿者只能选开放投稿的分类；普通成员（`plain_writer`）没有「推荐」页（网址、SEO、显示在菜单、定时上下线）；没有网址片段时按标题生成、避开保留字（`RESERVED_CHILD_SLUGS`）和同名；作者默认是创建人。面板：AI 审核结果（只给能复核的人）、投稿须知（普通成员）、不带 slug 同步的标题面板。正文是 Markdown 编辑器（192）。发布、撤下、改网址、移动、删除由信号触发预渲染、AI 送审和「上线时通知」 |
| 网站页面 | Wagtail 页面树根 `/admin/pages/` | 超管、内容编辑 | 首页的置顶文章（子表，最多 3 篇）；关于我们、用户协议、隐私政策（普通页面，正文 Markdown）；资讯栏目的介绍（富文本） |
| 群发文章 | `announce/article/<id>/`，页面列表和页头的按钮 | 能改作者的人（内容编辑、超管），每篇一次，已发布或已定时 | 先看信再发；定时的叫「上线时通知全体成员」 |
| Markdown 预览、上传图片 | `markdown/preview/`、`markdown/image/` | 进后台的人；上传要「投稿图片」集合的加图权限 | 上传走 Wagtail 的图片表单，记 `wagtail.create`，返回最长边 1600 的缩略图 |
| 文章分类 | `SnippetViewSet`，`/admin/snippets/content/articlecategory/` | 模型权限（内容编辑） | 还有文章在用的分类不能删（按钮不出现，直接访问删除地址跳回并提示）；保存后重新生成栏目页 |
| 图片 | Wagtail 图片库 `/admin/images/`，带集合 | 集合权限：投稿者、认证作者、赛事、内战管理员在「投稿图片」能加和选；内容编辑在根集合全权 | 5 MB、JPG/PNG/WebP、转 WebP；默认封面、默认头像集合变动时重新生成相关页面 |
| 图片集合 | Wagtail `/admin/collections/` | 超管 | 默认封面、默认头像的子文件夹在这里建 |

### 2.3 活动

| 页面 | 网址 / 实现 | 权限 | 必须保留的规则 |
|---|---|---|---|
| 赛事列表、新建、编辑、复制、查看、删除 | `ModelViewSet`（`tournaments:*`，`/admin/tournaments/…`） | `tournaments.services.can_manage`；删除只能是从没发布过的草稿（`TournamentPermissionPolicy`，删除页也拦） | `TournamentAdminForm`：有报名后「报名自动通过」「报名方式」不能改；整队报名的人数下限不能超过全站战队人数上限（只在相关字段改了时报在字段上）。保存后：比赛时间改了通知报名的人（`time_changed`，用保存前的开始时间）、补 `created_by`、人数警告、`after_change`（预渲染、提醒、AI 送审）。复制：只照抄列出的字段，时间按整周挪到将来（`copy_for_new`）。列表：待审核一列；「更多」按状态出现发布、通知全体成员、标记结束、队伍编排、审核报名、取消 |
| 发布、标记结束 | `tournaments/<id>/action/<publish|finish>/` | `manager_required` | 确认页；发布时可以勾「同时通知全体成员」；记 `tournaments.publish` / `.finish` |
| 取消赛事 | `tournaments/<id>/cancel/` | 同上 | 要写原因，发信给报了名的人，记 `tournaments.cancel` |
| 队伍编排 | `tournaments/<id>/teams/`，`tournaments/teams_admin.py`，拖拽（SortableJS，`static/js/tournament-teams.js`） | `can_manage` | 普通表单提交，服务器重新校验；保存、解散；记 `tournaments.arrange` |
| 内战列表、新建、编辑、复制、查看、删除 | `ModelViewSet`（`scrims:*`） | `scrims.services.can_manage`；删除只能是没人报名的草稿 | 保存后同赛事（时间改了、`created_by`、`after_change`）；「更多」有发布、通知、标记结束、分队、取消 |
| 发布、结束、取消内战 | `scrims/<id>/<action>/`、`scrims/<id>/cancel/` | `manager_required` | 记 `scrims.*`；取消发信给报名的人；发布时可通知全体 |
| 分队 | `scrims/<id>/split/`、`…/split/text/`，`scrims/split_admin.py`，拖拽（`static/js/scrim-split.js`） | `can_manage` | 勾选上场、生成分队（`teaming.py`）、拖拽调整、保存、复制结果；排序参数保留；有联系方式权限才显示联系方式；记 `scrims.select` / `.generate` / `.save_teams` |
| 通知全体成员 | `announce/<kind>/<id>/`，`core/announce_admin.py` | `entry.can_send` | 先看信、显示人数，每场一次 |

### 2.4 成员

| 页面 | 网址 / 实现 | 权限 | 必须保留的规则 |
|---|---|---|---|
| 用户 | Wagtail 用户视图的子类（`accounts/users_app.py`、`accounts/admin_users.py`），`wagtailusers_users:*` | 超管 | 不能新建、不能删除（403）；去掉 Wagtail 的批量删除和批量停用；停用必须写原因，停用后 `after_deactivation`（取消入队申请、暂停招募、提示他当队长的队）；编辑页旁边只读显示邮箱是否验证、位置、游戏 ID 和段位、联系方式（要权限）、战队、功能规则；列表行有「功能规则」按钮 |
| 用户组 | Wagtail 自带 | 超管 | 页面、集合、模型权限的勾选界面 |
| 功能权限（用户组限制、单个用户规则） | 两个 `ModelViewSet` | 超管（`SuperuserOnlyPolicy`） | 记 `updated_by`；`?user=` 预填和筛选 |
| 战队 | `ModelViewSet`（不能新建、删除、复制） | 超管 | `?captain=gone` 筛出队长停用的；位置用勾选框；保存后 `on_team_changed`（预渲染、AI 送审） |
| 指定队长、解散 | `teams/<id>/assign-captain/`、`teams/<id>/disband/` | 超管 | 按昵称或邮箱搜人；不能给解散的队、不能超人数上限；记 `teams.assign_captain` / `teams.disband` |
| 成员分组 | `SnippetViewSet`，成员用内联表单 | 模型权限（内容编辑） | 保存后重新生成成员页 |

### 2.5 审核

| 页面 | 网址 / 实现 | 权限 | 必须保留的规则 |
|---|---|---|---|
| 报名审核 | `registrations/`、`registrations/<id>/`、`…/action/`、`bulk-approve/`、`export.csv`，`tournaments/review_admin.py` | `can_manage`；联系方式要 `accounts.view_contactmethod` | 默认看待审核；通过、驳回（要备注）、撤销通过；临时队伍不能在这里审；批量通过（`next` 只接受站内）；导出 CSV 带 BOM，每项赛事记一条导出日志，联系方式列看权限 |
| 巡查记录 | `moderation/`、`moderation/<id>/`、`…/action/`、`…/ask-author/`、`moderation/try/`，`moderation/admin_views.py` | `can_review`（超管或 `moderation.change_moderationitem`） | 按状态、风险、类型、时间筛选；显示用量和额度；标记无问题、已处置、忽略（记 `moderation.handle`，详情页从操作记录读全部历史）；个人宣言可以顺手清空；要求作者修改（发信）；「试一下」 |
| 头像 | `avatars/`、`avatars/<id>/action/`，`moderation/avatar_admin.py` | `can_review` | 在用、已撤下、未通过三个标签带件数；撤下要原因、发信 |
| 评论 | `ModelViewSet`（只编辑、查看） | `comments` 的 `can_moderate`；不能新建、删除 | 只能改隐藏和置顶；`pin_problem` 校验、`release_pin`；保存后重新生成文章页 |

### 2.6 数据、设置、手册

| 页面 | 网址 / 实现 | 权限 | 必须保留的规则 |
|---|---|---|---|
| 活动数据 | `activity/`，`core/activity.py` | `can_view`（超管、内容编辑、赛事、内战管理员） | 时间段快捷选项；`?format=csv` 下载（带 BOM） |
| 全站设置 | Wagtail 设置（`BaseGenericSetting`），`core/models.py`、`core/forms.py` 的 `SiteSettingsAdminForm` | `core.change_sitesettings`（超管） | 密钥字段不回显、空着就是不改；「发送测试邮件」「测试对象存储」两个按钮；保存后重新生成首页和横幅页 |
| 字体库 | `settings/fonts/…`，`core/fonts/admin_views.py` | 超管 | 上传、网址、Google 三种添加；后台处理；在用的不能删；打包下载 |
| 排版设置 | `settings/typography/` | 超管 | 9 个区域；实时预览（`static/js/typography-preview.js`）；保存后生成字体样式表 |
| 静态页面 | `settings/prerender/`（`rebuild/`、`clear/`），`core/prerender_admin.py` | 超管 | 按状态筛选、分页；重新生成单页或全部；清空 |
| 操作记录 | Wagtail 的网站历史 `reports/site-history/` | 超管（菜单） | 显示自定义动作 |
| 后台手册 | `manual/`，`core/admin_manual.py` | `parts_for(user)` 不为空 | 按身份分部分，每步链到真实入口 |
| 账号 | Wagtail `/admin/account/` | 进后台的人 | 不能改名字、邮箱、头像、密码 |

## 3. 后台以外依赖它的地方

- 前台账号菜单、页脚的「管理后台」：`{% url 'wagtailadmin_home' %}`（`templates/components/account_area.html`、`templates/slots/footer_account.html`），只给 `runs_admin` 的人
- 「我要投稿」：`content.services.article_create_admin_url()` → `wagtailadmin_pages:add`
- 邮件里的后台链接：巡查提醒、要求作者修改（`wagtailadmin_pages:edit`、`tournaments:edit`、`scrims:edit`）、各种待办链接
- 上线清单、后台手册、待办里的链接都用网址名
- `core.services.copy_ahead` 的复制页跳转用 `wagtailadmin_explore`
- 很多自定义视图的面包屑写死 `wagtailadmin_home`
- 测试：45 个测试文件、约 200 处直接用后台网址或网址名

## 4. 依赖的 Wagtail 内部

- 钩子：`register_admin_urls`、`register_admin_viewset`、`register_admin_menu_item`、`register_settings_menu_item`、自定义的社区菜单和用户菜单、`construct_main_menu`、`construct_settings_menu`、`construct_homepage_panels`、`construct_homepage_summary_items`、`construct_explorer_page_queryset`、`register_page_listing_more_buttons`、`register_page_header_buttons`、`register_user_listing_buttons`、`register_log_actions`、`insert_global_admin_css`
- 权限策略：功能规则两个、文章分类、赛事、内战、战队、评论各自注册了 `register_permission_policy`
- 改写：`PagePermissionPolicy.explorable_instances`、账号页两个面板的 `is_active`、用户批量操作的注册表
- 面板：投稿须知、AI 审核结果两个自定义 `BoundPanel`，标题面板改了 `get_attrs`
- 信号：`page_published`、`page_unpublished`、`page_slug_changed`、`post_page_move`、`workflow_submitted`
- 模板：`templates/wagtailadmin/notifications/base.txt`（Wagtail 自带通知信的称呼和结尾）

## 5. 不依赖后台界面、重写时原样保留的

模型（页面、修订、图片和集合、全站设置、操作记录）、各应用的 `services.py`、信号、预渲染、邮件、AI 巡查、权限判断函数（`can_manage`、`can_review`、`can_moderate`、`can_view`、`parts_for`、`plain_writer`、`OwnArticlesPermissionTester`……）。
