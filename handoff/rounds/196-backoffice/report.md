# 196 后台推翻重写（报告）

## 做了什么

照用户说的顺序：先调研、写现状文档，再规划新架构、写设计文档，再一次写完代码，最后跑测试和修。

1. **调研**：`docs/admin-inventory.md`，重写前后台的每个页面、网址、权限、「必须保留的规则」，后台以外依赖它的地方，依赖的 Wagtail 内部。写完不再改
2. **新架构**：`docs/admin.md`（设计 14 章指过去，设计 v7.0）。原则、架构、布局、八个大类和每页的字段和权限、`b-*` 组件、测试办法。写代码时有几处照实际做法改了文档（集合放在图片页右上、角色页列出所有用户组、新建页一栏、评论列表显示前 200 字、编辑器图标和样式的出处）
3. **新应用 `backoffice/`，挂在 `/admin/`**：
   - `access.py`：进门（`access_admin`）和每个标签谁能看
   - `nav.py`：八个大类和标签；视图用 `placed(大类, 标签)` 声明位置，它同时是门（没登录跳登录页，没权限 403，`never_cache`）
   - `context.py`：只在后台页面上给模板 `bo`（顶栏、标签、小标签）
   - `forms.py`：文章（照 `ArticlePageForm` 的字段增减、网址片段避开保留字和同级）、普通页面、置顶文章、栏目介绍、分类、图片和集合、赛事（照搬 `TournamentAdminForm` 的锁和人数检查）、内战、用户（角色勾选、自己停用不了、停用要原因）、个人规则和用户组限制（同一项不重复）、战队、成员分组（组内顺序用 Django 的 ORDER 字段）、全站设置（两个密钥不回显、空着不改）、操作记录筛选；`KeepSeconds`：时间框只到分钟，只是秒被截掉时保留原值
   - `widgets.py`：浏览器自带的日期时间框、选图控件（只列能选的图，加上已经选着的那张）
   - `views/`：首页（问候、待办、我的文章、上线清单）、文章（列表、写、改、发布、预览草稿、撤下、删除，全走 Wagtail 的修订和页面动作）、网站页面、分类、图片（网格、多张上传、编辑、删除、集合、选图对话框和对话框里的上传）、赛事和内战（列表、新建、编辑、复制、删除）、用户、角色、战队、成员分组、评论（列表里直接隐藏 / 置顶）、全站设置、操作记录（页面和模型两种记录合在一起分页）
   - `urls.py`：原来的自定义页面网址名和路径不变，赛事、内战、战队、评论沿用命名空间
   - 模板：`backoffice/base.html` 独立骨架（`app.css`、`theme.js`、深浅色），顶栏、页头、标签、消息、选图对话框、编辑器图标；各页模板
   - 样式：`assets/css/input.css` 末尾「后台」一节（`b-*`），原来的分队、编队、头像、排版预览四个单独的 CSS 搬进来改用颜色令牌，四个文件删了
   - 脚本：`static/js/backoffice.js`（选图对话框、全选、筛选自动提交、`data-confirm`、成员分组加一行）
4. **原来写在 Wagtail 钩子里的视图**搬到 `tournaments/admin_views.py`、`scrims/admin_views.py`、`teams/admin_views.py`；其余自定义页面（报名审核、编队、分队、巡查记录、头像、群发、活动数据、手册、字体库、排版、静态页面、测试邮件、测试对象存储）视图不动，模板全部换成新骨架
5. **Wagtail 那边**：管理界面挪到 `/wagtail/`，`core.middleware` 把非超管送回 `/admin/`，两处都用后台的内容安全策略。各应用 `wagtail_hooks.py` 只留底层后台还要的：后台外观、操作记录的动作名、页面树过滤、账号页两个面板和用户批量操作的收紧。删了：菜单整理和八个大类的标签条（`core/admin_sections.py` 和它的模板标签）、首页面板、群发按钮、赛事 / 内战 / 战队 / 评论 / 功能规则的视图集、分类和成员分组的 snippet、文章编辑页的 AI 面板和投稿须知面板、`content.panels`
6. **资讯栏目介绍改存 Markdown**：迁移 `content/0009`（线上那行和每个修订都转），模板用 `|markdown`
7. **链接**：前台账号菜单和页脚的「管理后台」、我要投稿、要求作者修改的信、上线清单、手册、群发后的返回、测试邮件后的返回都指到新后台；手册按新后台改写
8. 顶层网址保留字加上 `wagtail`；robots 和预加载规则挡住 `/wagtail/`；Caddyfile 把 `/wagtail/` 和 `/admin/` 一样直接交给 Django
9. Markdown 编辑器的样式从 `admin.css` 拆到 `static/css/markdown-editor.css`，由控件带上；工具栏图标原来借 Wagtail 页面里的图标集，新后台自己画了一套（`backoffice/parts/editor_icons.html`）
10. 浏览器走查脚本：`journey.py pages` 也看 `backoffice` 的地址和 `/wagtail/`；`journey.py admin` 多走一段「写文章、用对话框选封面、发布」；`screens.py` 的种子加了文章、分组和一张图，截图加了 11 个后台页
11. 文档：README（新一节「后台（196 起自己写的）」、用户管理、手册、图片集合、评论、定时发布、网址前缀）、AGENTS（读什么、目录表、坑）、REVIEW-GUIDE 新一节

## 测试

- 原来测 Wagtail 界面的约 100 条改成测新后台，规则不变。没权限的人原来被 Wagtail「跳回后台首页」，现在是 403，测试跟着断言 403
- 新增 `backoffice/tests/test_backoffice.py` 30 条：门、底层后台只给超管、两处都用后台策略、文章（写、存草稿、发布、草稿压在线上版本上、预览草稿、只看自己的、只能选开放投稿的分类、撤下和删除、按状态筛）、网站页面、置顶、栏目介绍和它的迁移、分类、图片上传和集合、对话框、图片字段、赛事保存的副作用、秒数保留、删除只限草稿、内战、角色勾选、自己停用不了、个人规则和用户组限制、人员页只给超管、密钥、操作记录、入口、Caddy
- `test_admin_wording.py` 新增：每个页面声明的大类和标签、`/admin/` 下每个网址都经过 `placed`
- 改测试时顺手修的三处代码：顶层网址保留字 `wagtail`；操作记录的联合查询（SQLite 不许子查询带排序）；成员分组表单用了不可编辑的 `sort_order`

## 命令输出

测试机整组检查（最后一次）：

```
== pytest (19:38:33)
分片 1：445 passed in 48.02s
分片 2：444 passed in 47.29s
分片 3：444 passed in 52.86s
分片 4：444 passed in 55.15s
== 迁移 (19:39:34)
No changes detected
== 生产配置 (19:39:36)
System check identified no issues (0 silenced).
== 错误页和模板一致 (19:39:37)
== Docker 镜像 (19:39:38)
构建成功：0933c063befd
== 全部通过 (19:39:38)
```

变异（测试机，`handoff/rounds/196-backoffice/mutate.py`，59 处、61 次检查，全部被抓到）：

```
baseline green, 45 tests
caught signed-out visitors are not sent to sign in -> test_the_door
caught anyone signed in gets in -> test_the_door
caught a view without placed -> test_every_back_office_address_goes_through_the_door
caught wagtail's admin open to every member -> test_wagtails_own_admin_is_for_superusers
caught wagtail's admin without the admin policy -> test_both_admins_get_the_admin_policy
caught every section shown -> test_each_role_sees_only_its_sections_and_tabs
caught a strip for one page -> test_each_section_has_its_tabs_in_order
caught no count on 报名 -> test_review_tabs_count_what_waits
caught members see every article -> test_a_member_only_chooses_open_categories_and_sees_their_own
caught anyone edits any article -> test_a_member_only_chooses_open_categories_and_sees_their_own
caught publishing on the edit page saves only -> test_a_member_writes_saves_and_publishes
caught the preview shows the live page -> test_a_member_writes_saves_and_publishes
caught members choose any category -> test_submitter_category_and_author_fields
caught members choose any category -> test_a_member_only_chooses_open_categories_and_sees_their_own
caught members get the address and schedule -> test_only_editors_and_authors_get_the_promote_fields
caught members set the author -> test_submitter_category_and_author_fields
caught a reserved word becomes the address -> test_reserved_and_taken_addresses_step_aside
caught a taken address goes through -> test_an_editor_s_taken_address_is_refused_on_the_field
caught the writer's save resets the address -> test_the_address_comes_from_the_title_and_survives_the_writer
caught site pages for everyone inside -> test_site_pages_are_for_editors
caught the same article pinned twice -> test_pins_are_three_published_articles_at_most_once_each
caught drafts can be pinned -> test_pins_are_three_published_articles_at_most_once_each
caught pins saved as a draft only -> test_pins_are_three_published_articles_at_most_once_each
caught the introduction printed as written -> test_the_news_introduction_is_markdown
caught the migration leaves the HTML -> test_the_migration_turns_the_introduction_and_its_drafts_into_markdown
caught the migration leaves the drafts -> test_the_migration_turns_the_introduction_and_its_drafts_into_markdown
caught a used category deleted -> test_a_used_category_says_why_and_stays
caught delete offered on a used category -> test_only_empty_categories_offer_delete
caught the dialog shows every picture -> test_the_dialog_offers_what_one_may_choose_and_takes_an_upload
caught the dialog uploads anywhere -> test_the_dialog_offers_what_one_may_choose_and_takes_an_upload
caught a picture field takes any picture -> test_a_picture_field_refuses_a_picture_one_may_not_choose
caught collections for everyone -> test_members_upload_into_the_submission_collection_only
caught auto approval unlocked -> test_auto_approve_is_locked_once_anyone_has_registered
caught the creator not filled in -> test_saving_a_tournament_does_what_the_admin_did
caught the start before the save forgotten -> test_saving_a_tournament_does_what_the_admin_did
caught the start before the save forgotten -> test_saving_in_the_admin_sends_it
caught no after_change -> test_saving_a_tournament_does_what_the_admin_did
caught a published tournament deleted -> test_only_a_draft_never_published_is_deleted
caught seconds cut off -> test_an_untouched_time_with_seconds_is_kept
caught a scrim without its creator -> test_a_scrim_is_saved_and_only_an_empty_draft_deleted
caught a scrim with signups deleted -> test_a_scrim_is_saved_and_only_an_empty_draft_deleted
caught system groups ticked here too -> test_roles_are_ticked_and_system_groups_left_alone
caught one's own account switched off -> test_nobody_switches_their_own_account_off
caught stopped without a reason -> test_stopping_an_account_needs_a_reason_and_cancels_its_applications
caught applications left after stopping -> test_stopping_an_account_needs_a_reason_and_cancels_its_applications
caught a second rule for the same feature -> test_rules_for_one_person_and_for_a_role
caught rules without who set them -> test_rules_for_one_person_and_for_a_role
caught people pages for editors -> test_people_pages_are_for_superusers
caught a team edit regenerates nothing -> test_an_admin_edit_of_a_team_regenerates_its_pages
caught group members saved out of order -> test_an_admin_creates_a_group_with_members
caught any action on a comment -> test_comments_are_hidden_or_pinned_not_added_or_deleted
caught the comment list for everyone inside -> test_content_editors_open_the_admin_list_and_others_do_not
caught a blank secret clears it -> test_the_secrets_are_never_shown_and_blank_keeps_them
caught the log without page entries -> test_the_log_shows_page_and_model_entries_with_their_names
caught the log's action filter ignored -> test_the_log_shows_page_and_model_entries_with_their_names
caught the account menu still points at Wagtail -> test_the_site_owner_is_shown_the_way_in
caught a fix-it letter points at Wagtail -> test_each_kind_of_content_has_somewhere_to_fix_it
caught 我要投稿 opens Wagtail's editor -> test_the_ways_in_lead_to_the_back_office
caught robots let /wagtail/ in -> test_the_ways_in_lead_to_the_back_office
caught a page may take the slug wagtail -> test_every_fixed_top_level_route_is_reserved
caught the editor without its styles -> test_what_the_renderer_emits_has_its_styles
restored and green; missed: none
```

最后加的 Caddy 测试不在这个脚本里，本机单独改坏过一次：

```
1 passed in 0.08s
0
1 failed in 0.29s
1
1 passed in 0.07s
```

（中间两行是 Caddyfile 里 `/wagtail` 出现的次数：去掉以后 0、改回 1。）

浏览器（测试机，无头 Chromium）：

```
看了 163 个地址，0 处有问题
```

```
ok  勾满 10 人后「生成分队」能点了
ok  生成了两队各 5 人 5/5
ok  卡片按钮移到缓冲区再移回 4/5
ok  保存分队
ok  三个散人移进新队伍 3
ok  保存编队
ok  新队伍出现在页面上
ok  编辑器起来了，工具栏有图标 17
ok  工具栏图标画得出来
ok  对话框里选了封面 1
ok  文章发布了
ok  封面留在文章上
ok  浏览器没有报错
```

```
ok  注册表单提交
ok  验证码邮件发出
ok  验证后到了个人中心
ok  加了游戏 ID
ok  加了联系方式
ok  报了内战
ok  申请了战队
ok  首页「我的安排」里有这场内战
ok  浏览器没有报错
```

截图：`screens.py 1280`、`screens.py 375` 拍了 11 个后台页。看图后改了：新建页没有右栏时表单只占左边三分之二（加 `b-single`）、标题下面挂着 Wagtail 的「你想让公众看到的页面标题」、下拉框空选项「---------」、侧栏按钮被拉成整行宽、编辑器工具栏图标空白（见上面第 9 条）。

## 部署（正式站 169.58.217.180）

先备份，这轮有迁移：

```
已备份到 /app/backups/sjtu-ow-20261005-034051.tar.gz（210.2 MB）
```

部署脚本不处理删掉的文件，这次先把 22 个删掉的文件挪到服务器的 `/root/gone196/`（保留路径），再跑 `deploy_ship.sh 196`：

```
 Image sjtu-ow-web Built 
 Image sjtu-ow-worker Built 
sjtu-ow-web 2026-10-04 21:41:29 +0200 CEST
  Applying content.0009_markdown_intro... OK
 Container sjtu-ow-worker-1 Starting 
 Container sjtu-ow-worker-1 Started 
全量生成完成：成功 12，失败 0，删除 0；目录占用 280 KB
{"status": "ok", "checks": {"database": {"ok": true, "detail": "ok"},
```

镜像里确认旧文件不在：

```
ls: cannot access 'scrims/wagtail_hooks.py': No such file or directory
ls: cannot access 'core/admin_sections.py': No such file or directory
ls: cannot access 'templates/wagtailadmin/home.html': No such file or directory
backoffice/urls.py
```

`Caddyfile.vps` 照仓库的改了 `@always_django` 一行（改前备份 `/root/Caddyfile.vps.bak-196`），和仓库那份只差反代那一块，`caddy validate` 通过，重启 proxy：

```
Valid configuration
 Container sjtu-ow-proxy-1 Started 
/admin/ 302 http://127.0.0.1:22887/accounts/login/?next=/admin/
/wagtail/ 302 http://127.0.0.1:22887/accounts/login/?next=/wagtail/
/ 200 
/news/ 200 
```

外网：

```
302 https://sjtu.ow-shanghaiuniversity.com/accounts/login/?next=/admin/
User-agent: *
Disallow: /admin/
Disallow: /wagtail/
Disallow: /me/
```

在正式站的真实数据上以第一个超级管理员渲染 32 个后台页面（`/root/smoke196.py`：请求工厂直接调视图，不建会话、不记登录时间，只读）：

```
pages: 32 not 200: 0
```

## 没做 / 没验证

- 没在真人浏览器里登录正式站后台看（生产 Cookie 只走 HTTPS，测试账号也不该在正式站上建）；正式站只有上面的 32 页渲染和外网 302
- 浏览器没走过：成员分组「再加一个人」、图片页一次传多张、对话框翻页和上传失败的提示、排版设置的实时预览在新骨架里的样子
- `deploy_ship.sh` 不处理删除的文件，这次手工挪的；脚本在服务器上、不在仓库里，没改
- `content.forms.ArticlePageForm` 还在，只服务 `/wagtail/` 里的超管；和新后台的 `ArticleForm` 是两份规则
