# 189 后台重做（一）：外观、菜单、首页（报告）

## 做了什么

1. **外观** `static/css/admin.css`（`core/wagtail_hooks.py` 的 `insert_global_admin_css` 挂到每个后台页）：
   - 前台的颜色令牌抄成 `--sj-*`，浅色、深色（`.w-theme-dark`）、跟随系统（`@media (prefers-color-scheme: dark) .w-theme-system`）三份
   - Wagtail 的 49 个语义变量和几个合成色（`--w-color-primary` 换成前台的深夜蓝，`--w-color-secondary` 及浅深几档换成交大红）指到令牌上；字体换前台的字体栈；按钮和输入框 8px 圆角、面板 12px
   - 侧栏是白底加一条边线，当前项浅红底
2. **左上角** `templates/wagtailadmin/base.html` 的 `branding_logo`：站点标志（红底白色折角）和「管理后台」，不再是 Wagtail 的鸟
3. **菜单** `core/admin_home.arrange_main_menu`、`arrange_settings_menu`（挂在 `construct_main_menu` order 900、`construct_settings_menu`）：
   - 「社区」子菜单拆开放到第一层；加「首页」「文章」（资讯栏目的文章列表）；页面树改名「网站页面」，只给超级管理员和内容编辑
   - 文档、报告、帮助不进菜单；设置里只留全站设置、字体库、排版设置、静态页面、图片集合（原「集合」）、操作记录（原「报告 → 网站历史」）
   - 按设计 14.1 的顺序排好后**重新编号**：Wagtail 画侧栏时还会按 `order` 再排一次，第一版没改编号，「首页」被排到了最后
   - 内战的菜单项从「内战活动」改成「内战」；`accounts` 里「报告、帮助只给站长和内容编辑」那个钩子删了（现在对谁都不显示）
4. **后台首页** `templates/wagtailadmin/home.html` 整个换掉：只画面板，不要 Wagtail 的站点摘要、页面搜索框、账号小卡
   - `core.admin_home.WelcomePanel`：「你好，昵称」、身份、快捷按钮（写文章 / 新建赛事 / 新建内战 / 打开网站，按权限）
   - 首页只留本站的面板（问候、待办、上线清单），Wagtail 自带的面板去掉
   - 待办每件一张卡（文字 +「去处理 →」），上线清单必做的列出、建议的和已完成的折叠
5. 后台手册里的「社区 → 赛事 → 添加」等路径改成新菜单的说法；停用队长时的提示「到「社区 → 战队」」改成「到「战队」」
6. 设计 14.1（v6.67），推翻 v6.13 起「后台用 Wagtail 默认的配色」
7. 测试：`core/tests/test_admin_look.py`（5 条：令牌值和前台一致、Wagtail 变量指向令牌、每个后台页加载样式和站点标志、首页问候和按钮、各角色的按钮）；`test_admin_wording.py` 菜单相关 3 条按新设计重写（站长的完整顺序和设置子菜单、各角色只看到自己的、用不上的入口对谁都不显示）

## 看过的样子

本机开发站，用本机开发库里建的一个本地超级管理员（`devroot@localhost.test`，没有密码，直接生成会话），无头 Edge 1440×900 截图：

- 首页浅色、深色：左侧白底（深色是深夜蓝）侧栏、站点标志，菜单 首页 / 文章 / 文章分类 / 评论 / 赛事 / 报名审核 / 内战 / 战队 / 成员分组 / 内容审核 / 头像审核 / 图片 / 活动数据 / 网站页面 / 用户 / 设置 / 后台手册；右边「你好，本机站长」、四个按钮、四张待办卡、上线清单
- 赛事列表、赛事编辑页：交大红按钮和分页、圆角输入框

截图过程中踩到两个本机的坑：Git Bash 会把命令行参数里的 `/admin/` 改写成 Windows 路径（加 `MSYS_NO_PATHCONV=1`）；本机开发服务器的静态文件不带版本号，截图用的 Edge 会缓存旧的 `admin.css`（截图时关掉缓存）。

## 命令输出

测试机仍连不上（本机 IPv6 不通），在本机跑。

变异（本机，14 处）。第一次漏了「Wagtail 自带面板没去掉」：测试库里没有编辑记录，Wagtail 的「最近的编辑」面板不出现；测试里让站长保存一次草稿并记日志（`save_revision(..., log_action=True)`）后再跑：

```
baseline green, 8 tests
caught look not loaded -> test_every_admin_page_loads_the_look_and_the_sites_mark
caught light red drifts -> test_the_admin_uses_the_sites_colour_values_light_and_dark
caught dark ground drifts -> test_the_admin_uses_the_sites_colour_values_light_and_dark
caught sidebar stays purple -> test_wagtails_colours_point_at_the_tokens
caught bird stays -> test_every_admin_page_loads_the_look_and_the_sites_mark
caught sidebar re-sorts -> test_the_menu_follows_the_design_order
caught 社区 kept whole -> test_the_menu_follows_the_design_order
caught 社区 kept whole -> test_wagtails_unused_entries_stay_out_of_every_menu
caught reports back -> test_wagtails_unused_entries_stay_out_of_every_menu
caught settings unsorted -> test_the_menu_follows_the_design_order
caught settings unsorted -> test_wagtails_unused_entries_stay_out_of_every_menu
caught page tree for everyone -> test_each_role_sees_only_its_own_work
caught no 文章 -> test_the_menu_follows_the_design_order
caught no 文章 -> test_each_role_sees_only_its_own_work
caught no tournament button -> test_the_first_page_greets_and_offers_the_usual_work
caught no tournament button -> test_each_role_gets_its_own_buttons
caught Wagtail panels kept -> test_the_first_page_greets_and_offers_the_usual_work
caught no greeting -> test_the_first_page_greets_and_offers_the_usual_work
caught no greeting -> test_each_role_gets_its_own_buttons
restored and green; missed: none
```

整组检查（本机，测试补强前跑的；之后只改了测试，变异的基线是绿的）：

```
1726 passed, 1 skipped in 272.67s (0:04:32)
No changes detected
System check identified no issues (0 silenced).
```

`docker build` 本机没跑，看 CI。

## 没做（下一轮）

- 列表页：表格还是 Wagtail 的样子（行直接铺在页面底色上），可以放进白色面板
- 编辑页：文章编辑页的「推广」「设置」标签里很多项用不上；赛事、内战表单字段多，没分组
- 手机上的后台没专门看
- 157 轮日历订阅地址带时间戳、每次都变（188 报告提到的偶发测试），还没改
