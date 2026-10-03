# 117 后台的文字和菜单（报告）

## 做了什么

1. **后台的英文**（#26）：Wagtail 8 的中文翻译缺的字符串，由项目补在 `locale/zh_Hans/LC_MESSAGES/django.po`（128 条）和 `djangojs.po`（7 条），`LOCALE_PATHS` 指过去。原文是逐页渲染后台、记下查不到译文的 `gettext` 调用得来的（超级管理员打开约 100 个后台网址，加内容编辑、赛事管理员、认证作者、投稿者各看首页和几页），脚本里的从打包后的 JS 里找 `gettext` 调用、对比 `/admin/jsi18n/`。另把 Wagtail 原译的「帐号」两条改成全站统一的「账号」
   - **编译**：新模块 `core/translations.py`（标准库解析 `.po`、写 `.mo`，键排序、不写哈希表，输出稳定）和命令 `compile_translations`；`.po`、`.mo` 都提交，测试检查一致。本机没有 gettext，没法和 `msgfmt` 的输出对比，用 Python 的 `gettext.GNUTranslations` 读回验证（含上下文、复数、多行）
   - **检查工具**：`handoff/rounds/117-admin-wording/find_untranslated.py`，以临时超级管理员在事务里渲染后台、跑完回滚，Wagtail 升级后用它找新缺的
   - 顺带：后台只用简体中文和北京时间（`WAGTAILADMIN_PERMITTED_LANGUAGES`、`WAGTAIL_USER_TIME_ZONES`，账号页不再有语言和时区下拉）；内容语言显示「简体中文」而不是「Simplified Chinese」（`WAGTAIL_CONTENT_LANGUAGES`）；关掉升级提示（`WAGTAIL_ENABLE_UPDATE_CHECK = False`）；标签页标题「… - SJTU OW 后台」、用站点图标（`templates/wagtailadmin/admin_base.html`）
2. **布尔值**（#22）：文章分类「开放投稿」、成员分组「显示」改成勾叉（`BooleanColumn`）；用户功能规则写「单独允许」「单独禁止」
3. **静态页面列表**（#22）：类型写中文（`PrerenderedPage.KIND_LABELS`、`kind_label`）；按状态筛选（全部、等待生成、已生成、生成失败，带数量）；每页 50 条；统计改成数据库聚合，不再整表读进内存
4. **菜单**（#27）：「内战」改「内战活动」；社区下按设计排（赛事、报名审核、内战活动、战队、内容审核、头像审核、评论）；主菜单 页面、图片、社区、成员分组、文章分类、（文档）、用户、报告、设置、帮助；**「用户」单独一个菜单**（用户、用户组、功能权限），用户和用户组的视图集换成本站的子类（`menu_hook`），功能权限的组也挂过去；**报告、帮助只给超级管理员和内容编辑**（`construct_main_menu`）
5. **页面树看到别人的草稿**（查菜单时发现，先复现）：赛事管理员、内战管理员、认证作者打开「资讯」都能看到别人没发布的稿件标题。新函数 `content.permissions.sees_only_own_drafts()`：超级管理员、内容编辑以外的人都只看到已发布的和自己的稿件，页面树的钩子和 `explorable_instances` 两层都换成它
6. **没人能批的工作流**（英文扫描时发现）：Wagtail 迁移自带的「Moderators approval」工作流挂在根页面上，审批组是 `init_site` 删掉的英文 Moderators 组，资讯以外的页面提交审核就没人能批。`content.services.retire_wagtail_stock_workflow()`（审批组为空时停用，有人配了审批组就不动），`init_site` 删组后调用；迁移 `content/0006` 给已有站点做同样的事，并把根页面、根集合从「Root」改名「根目录」
7. **文档**：设计 v6.13（14.1 菜单表按实际重写、14.2 静态页面和全站设置、14.3 过滤放宽、13.4 路由表补 14 行、13.2.7 按钮名、12.4.1 备份字段）；README（后台菜单、后台中文怎么改）；AGENTS（改 `.po` 后编译）；REVIEW-GUIDE 加 115–117 一节

## 命令输出

（见下面各节，均为本机实际运行。）

找原文（`find_untranslated.py`，改完以后跑）：

```
== 服务端缺 4 条（django.po）
  "%s MB"   ← /admin/images/multiple/add/
  "exact"   ← /admin/redirects/
  "SMTP 密码"   ← /admin/settings/core/sitesettings/1/
  "%s KB"   ← /admin/images/1/
== 脚本缺 0 条（djangojs.po）
```

四条都是误报（见脚本开头）。改之前同一方法记下 130 条（含这四条误报）。我照源码顺手多加的「There are no %(model_name)s to display.」其实有译文，核对时删掉了（逐条核对：`.po` 里每条原文在改之前都查不到译文，「帐号」两条是有意覆盖）。

变异（`mutate.py`，30 处）。第一次漏了两处：页面树的钩子和 `explorable_instances` 各自改坏都没被抓到。一是两层互相兜底，只改一层页面上照样看不到；二是测试用户没验证邮箱，本站会把他们移出「投稿者」组，他们其实打不开页面树，「看不到草稿」是白看。改成测试用户都验证邮箱、断言页面打开是 200，另加一条分别直接调用两层过滤的测试。格式化后重跑：

```
baseline green, 15 tests
caught the project's translations are not loaded -> test_the_admin_has_no_wagtail_english_left
caught a .po edited without recompiling -> test_the_committed_mo_files_match_the_po_files
caught the compiler drops contexts -> test_the_compiler_writes_what_python_gettext_reads
caught the compiler keeps untranslated entries -> test_the_compiler_writes_what_python_gettext_reads
caught the compiler output depends on order -> test_the_compiler_writes_what_python_gettext_reads
caught tabs say Wagtail again -> test_admin_tabs_name_the_site_not_wagtail
caught every language offered -> test_one_language_one_time_zone_and_no_upgrade_notice
caught every time zone offered -> test_one_language_one_time_zone_and_no_upgrade_notice
caught the upgrade notice is back -> test_one_language_one_time_zone_and_no_upgrade_notice
caught the locale is Simplified Chinese again -> test_the_locale_shows_in_chinese
caught categories say True and False -> test_yes_no_columns_are_ticks_not_true_and_false
caught member groups say True and False -> test_yes_no_columns_are_ticks_not_true_and_false
caught user rules say True and False -> test_yes_no_columns_are_ticks_not_true_and_false
caught static pages show kind codes -> test_the_static_pages_list_speaks_chinese_filters_and_pages
caught static pages ignore the status filter -> test_the_static_pages_list_speaks_chinese_filters_and_pages
caught static pages on one long page -> test_the_static_pages_list_speaks_chinese_filters_and_pages
caught the scrim menu says 内战 -> test_the_menu_follows_the_design_order
caught tournaments drop down the community menu -> test_the_menu_follows_the_design_order
caught users go back under settings -> test_the_menu_follows_the_design_order
caught groups are called 组 -> test_the_menu_follows_the_design_order
caught feature permissions go back under settings -> test_the_menu_follows_the_design_order
caught the users menu after reports -> test_the_menu_follows_the_design_order
caught reports and help for everyone -> test_reports_and_help_are_for_superusers_and_content_editors
caught only pure submitters are filtered in the tree -> test_both_page_tree_filters_hide_others_drafts
caught only pure submitters are filtered in explorable pages -> test_both_page_tree_filters_hide_others_drafts
caught both tree filters miss tournament managers -> test_staff_who_are_also_submitters_do_not_see_others_drafts
caught a stock workflow with approvers is retired too -> test_a_stock_workflow_with_approvers_is_left_alone
caught init_site leaves the stock workflow on -> test_init_site_retires_the_workflow_nobody_can_approve
caught the migration keeps 「Root」 -> test_the_migration_retires_it_on_existing_sites
caught the migration retires workflows with approvers -> test_the_migration_retires_it_on_existing_sites
restored and green; missed: none
```

整组检查（开发服务器停着）：

```
All checks passed!
288 files already formatted
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
No changes detected
System check identified no issues (0 silenced).
1394 passed in 299.30s (0:04:59)
```

本机开发库迁移：

```
Applying content.0006_retire_stock_workflow... OK
[('Moderators approval', False, 0), ('内容审核', True, 1)]
根目录 根目录
```

本机截图（超级管理员，1440 宽）：首页「26 个页面」「478 张图片」「搜索全部页面…」，侧栏 页面、图片、社区、成员分组、文章分类、文档、用户、报告、设置、帮助；账号页只有主题偏好和快捷键开关，没有语言、时区；静态页面列表有四个状态按钮。

演示站（镜像时间 `2026-10-03 16:47:54 +0200`，`.mo` 两边 MD5 一致）：

```
Applying content.0006_retire_stock_workflow... OK
全量生成完成：成功 46，失败 0，删除 0；目录占用 1604 KB
{"status": "ok", ...}
快捷键 账号
[('Moderators approval', False, 0), ('内容审核', True, 1)]
根目录 根目录
```

## 没做 / 未验证

- 报告网址按角色拒绝（见复核「建议修」）
- 演示站的后台要等 HTTPS 配好才能登录，后台页面在演示站上没有截图（本机截过）
- 无法和 GNU `msgfmt` 的输出逐字节对比（本机没有 gettext）；Linux 上 Django 读 `.mo` 用的同样是 Python 的 `gettext` 模块，演示站上 `gettext("Shortcuts")` 返回「快捷键」
