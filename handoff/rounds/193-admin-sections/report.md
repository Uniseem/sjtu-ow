# 193 后台按事情分组（报告）

## 做了什么

1. **`core/admin_sections.py`**（新）：
   - 八个大类和各自的标签：`SECTIONS`、`TAB_LABELS`
   - `build()` 把这个人原来能看到的菜单项（含「用户」「设置」两个子菜单里的）按网址归到标签上，拼出他的大类；对不上任何标签的菜单项原样留在侧栏最后
   - 「用户与权限」是一个带子标签的标签（用户、用户组、用户组功能限制、用户功能规则）
   - 「稿件」原来不是菜单项（Wagtail 的报告不进菜单），能审稿的人（超级管理员、投稿审批组里的人）才加
   - `arrange()` 由新的 `construct_main_menu` 钩子（order 1100，排在 189 的整理和投稿者过滤后面）调用，侧栏换成八个 `SectionMenuItem`，每个都带 `data-section`
   - `locate()` 按网址前缀（`PREFIXES`）找当前页属于哪个标签；页面树里的页面看它在不在「资讯」下面，在就是「文章」
   - `count_review_tabs()` 只在审核页给标签数件数
2. **标签条**：`core/templatetags/admin_sections.py` 的 `{% section_tabs %}` 包住 Wagtail 的 `furniture` 块，在 `<div class="content">` 后面插入 `core/admin/section_tabs.html`。一个标签的类和不属于任何类的页面只放一个隐藏的 `data-admin-section` 标记
3. **侧栏高亮**：`admin.css` 里，页面上有 `data-admin-section` 时关掉 Wagtail 自己的高亮（它取网址前缀最长的菜单项，合并后多半落到 `/admin/` 的「首页」），按标记点亮对应的大类。另有标签条、件数、子标签的样式，手机上标签条横向滚动、左边让出 Wagtail 的菜单按钮
4. **赛事里直接审报名**：赛事列表的查询加上待审核报名的数量，加一列「待审核」（有就写「N 份」，链到 `registration_review_index?tournament=…&status=pending`），「更多」里加「审核报名」
5. `core/admin_todo.py` 把待复核内容、待审核头像、等审的稿件、待审核报名四个计数提成函数，首页待办和审核标签共用
6. 旧菜单路径改掉：
   - 后台手册：「活动 → 赛事」右上的「添加」、「活动 → 内战」、「审核 → 稿件」、「数据」、「成员 → 用户与权限」，审核报名一步加了「待审核」一列的说法
   - 停用队长的提示改成「到「成员 → 战队」」，上线清单改成「审核 → 内容」页
   - README 里十几处「社区 → …」「用户 → 用户」（这些从 189 起就过时了）
7. 设计 14.1（菜单表整个换掉，加标签条和高亮、和示意不同的两处、标签条外观）、14.2、14.3，附录 D v6.71；README 新一节「后台的菜单」；AGENTS.md 加一条坑
8. 测试：`core/tests/test_admin_wording.py` 原来三条菜单测试换成八条，`tournaments/tests/test_review_admin.py` 加一条

## 验证

截图（无头 Edge）：

- 1440 宽浅色：审核（报名标签带「2」）、用户（子标签）、文章编辑页、首页、赛事列表（「待审核 2 份」）
- 1440 宽深色：字体库
- 390 宽：内战列表。第一次截图 Wagtail 的菜单按钮盖住了第一个标签，加了左边距后重截，不再遮挡

侧栏高亮在这些截图里都对：审核、成员、内容（编辑文章时也是）、首页、设置、活动。

## 命令输出

变异（本机，16 处，全部被抓到）：

```
baseline green, 8 tests
caught menu left flat -> test_the_sidebar_is_eight_sections_without_submenus
caught a tab dropped -> test_each_section_has_its_tabs_in_order
caught articles count as site pages -> test_every_page_lights_its_own_section
caught scrim notices belong nowhere -> test_every_page_lights_its_own_section
caught the first page belongs nowhere -> test_each_section_has_its_tabs_in_order
caught no 稿件 tab -> test_each_section_has_its_tabs_in_order
caught people not under one tab -> test_each_section_has_its_tabs_in_order
caught review tabs uncounted -> test_review_tabs_count_what_waits
caught the strip lands nowhere -> test_the_strip_opens_the_content_column
caught the strip lands nowhere -> test_each_section_has_its_tabs_in_order
caught grouped before the submitters' filter -> test_each_role_sees_only_its_sections_and_tabs
caught no current tab -> test_each_section_has_its_tabs_in_order
caught no current tab -> test_every_page_lights_its_own_section
caught a strip for a single page -> test_each_section_has_its_tabs_in_order
caught Wagtail's own light left on -> test_the_sidebar_light_follows_the_marker_for_every_section
caught 审核 never lit -> test_the_sidebar_light_follows_the_marker_for_every_section
caught no 待审核 column -> test_the_tournament_list_leads_straight_to_its_waiting_registrations
caught nothing counted per tournament -> test_the_tournament_list_leads_straight_to_its_waiting_registrations
restored and green; missed: none
```

整组检查（本机；测试机仍连不上）：

```
All checks passed!
365 files already formatted
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
No changes detected
1760 passed, 1 skipped in 305.19s (0:05:05)
```

`check --deploy` 这一轮没有动设置，沿用 192 最后一次的结果（`System check identified no issues (0 silenced).`），本轮未重跑。

### 正式站

`deploy_ship.sh 193` 的输出（没有迁移）：

```
 Image sjtu-ow-web Built
 Image sjtu-ow-worker Built
sjtu-ow-web 2026-10-04 18:29:20 +0200 CEST
  No migrations to apply.
 Container sjtu-ow-worker-1 Starting
 Container sjtu-ow-worker-1 Started
全量生成完成：成功 12，失败 0，删除 0；目录占用 280 KB
{"status": "ok", "checks": {"database": {"ok": true, "detail": "ok"},
```

服务器上用测试客户端给超级管理员建临时会话看了一遍（最后 `logout()` 删掉）：

```
sidebar: ['首页', '内容', '活动', '成员', '审核', '数据', '设置', '手册', '账号', '注销']
/admin/tournaments/ events ['赛事', '内战']
/admin/registrations/ review ['报名', '稿件', '内容', '头像', '评论']
/admin/users/ members ['用户与权限', '战队', '成员分组']
/admin/settings/fonts/ settings ['全站设置', '字体库', '排版设置', '静态页面', '图片集合', '操作记录']
```

## 没做 / 顺带发现

- 列表页、编辑页本身的版式（用户 189 后说的「眼花缭乱」里还有这一块），下一轮
- 「稿件」标签指到 Wagtail 的工作流报告，那一页是通用列表，以后可以换成自己的
- 「内战」的页面标题还是「内战活动」（`ScrimViewSet` 的模型名），和标签「内战」不一样
- 标签条在不支持 `:has()` 的老浏览器上高亮会退回 Wagtail 的（见复核）
