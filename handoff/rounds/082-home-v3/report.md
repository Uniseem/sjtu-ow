# 082 实现报告

## 结论

完成。首页按 v3.0 的 M 版落地；焦点图删除；全站设置新增社区成立日期和 QQ 群链接；13.13.4 新补的首页刷新事件全部接上。

## 逐条结果

### 1. 两个新字段

`SiteSettings.founded_on`（可空日期）、`qq_group_url`（可空网址，校验器 `https_only` 只放 `https://`），放在后台「全站设置 → 站点信息」。迁移 `core/0012`。测试：`http://`、`javascript:` 被拦，`https://` 通过；两项空着时首页不出现对应的块。

### 2. 删除焦点图

`HomePageCarouselItem` 模型和首页编辑页的面板删除，迁移 `content/0005` 删表；`static/js/carousel.js`、`c-feature`、`c-daystrip` 样式、样张页两段、7 条焦点图 / 日程带 / 赛场区块的测试删除。`git grep -i carousel` 只剩断言它已删除的两条测试和迁移。

### 3. 首页数据（`content/home.py`）

- `community_age()`：按上海时区的日期算整年，再算从最近一个周年起的天数；2 月 29 日成立的在平年按 2 月 28 日算周年；没填或填了未来日期返回 None（首页不显示这一项）。6 组日期参数化测试
- `agenda()`：沿用 `next_up()` 的合并规则，再一次查询取出赛事的已通过队数、内战的报名人数；内战的上限是 `players_needed`
- `notices()`：「公告」「赛事通知」最新 5 篇
- `activity_stats()`：已结束的内战场数、已结束的赛事届数
- `homepage()`：把以上和成员数、战队数、资讯、战队、QQ 链接一起交给模板

**设计照实修正**：赛事表没有队伍名额字段，近期安排里赛事只写「已通过 N 队」、不画进度条（设计 5.2 原写「已通过队数 / 名额」）。

### 4. 模板和样式

`home_page.html` 重写：首屏（色彩渐变底四团色块 + 点阵、校徽水印和扫光、眉标、标题、简介、两个按钮、关键数字条、近期安排卡、六个快捷入口磁贴、「向下」）、资讯卡（分类标签条、头条、5 行列表）、通知公告、活动统计、战队条。首屏用负外边距伸到磨砂顶栏下面。数字带 `data-count-to`，服务端先写好真实值，脚本再从 0 递增；资讯、快捷入口、战队条用 `data-reveal`。进度用 `<progress>`（内容安全策略不允许行内样式）。新增 `chat` 图标。

`input.css` 新增 `c-hero`、`c-figures`、`c-agenda`、`c-quick`、`c-news`、`c-notices`、`c-stats`、`c-teamstrip`，设计 13.2.7 组件表同步。

### 5. 刷新事件（设计 13.13.4）

| 事件 | 改了哪里 |
|---|---|
| 内战报名、改报名、取消 | `scrims/services.py` `_refresh_detail` 也请求 `/` |
| 报名变为 / 离开「已通过」 | `tournaments/registration.py` `_refresh_public_pages` 也请求 `/` |
| 邮箱验证、账号停用恢复 | `members/signals.py` 新增 `refresh_member_count()`（成员页 + 首页）；分组变化仍只刷新成员页 |
| 全站设置的成立日期、QQ 链接修改 | 新文件 `core/signals.py`：保存前记下两项旧值，变了才请求 `/`，改别的设置不刷新 |

### 6. 文档

- `README.md`「视觉风格与首页」的首页维护一段重写（两个设置、置顶文章、自动取的内容）
- `docs/design.md`：5.2 赛事进度的说法、13.2.7 组件表加四行

## 验收输出

```
== ruff
All checks passed!
245 files already formatted
== tailwind
Built production stylesheet 'C:\Users\fyc12\Desktop\Claudee\sjtu-ow\static\css\app.css'.
== pytest
970 passed in 136.93s (0:02:16)
== makemigrations
No changes detected
== check --deploy
System check identified no issues (0 silenced).
```

变异（`handoff/rounds/082-home-v3/mutate.py`）：

```
KILLED   成立时长不看今年的周年到没到  | 1 failed, 54 passed in 21.54s
KILLED   闰年 2 月 29 日的周年算错  | 1 failed, 57 passed in 22.19s
KILLED   未来的成立日期也显示  | 1 failed, 59 passed in 13.88s
KILLED   QQ 群链接允许 http://  | 1 failed, 60 passed in 14.34s
KILLED   没填 QQ 群链接也显示那块  | 1 failed, 4 passed in 4.01s
KILLED   没填成立日期也显示「社区已成立」  | 1 failed, 2 passed in 4.04s
KILLED   通知公告混进攻略  | 1 failed, 10 passed in 7.49s
KILLED   累计内战把还没办的也算上  | 1 failed, 11 passed in 5.22s
KILLED   进度条的上限写死  | 1 failed, 6 passed in 2.76s
KILLED   资讯头条后面只列四篇  | 1 failed, 9 passed in 3.65s
KILLED   战队数把解散的也算上  | 1 failed, 1 passed in 1.65s
KILLED   内战报名不刷新首页  | 1 failed, 12 passed in 3.79s
KILLED   报名通过不刷新首页  | 1 failed, 48 passed in 13.65s
KILLED   邮箱验证只刷新成员页  | 1 failed, 13 passed in 5.23s
KILLED   账号停用只刷新成员页  | 1 failed, 14 passed in 4.93s
KILLED   QQ 群链接改了不刷新首页  | 1 failed, 15 passed in 4.48s
KILLED   改任何设置都刷新首页  | 1 failed, 15 passed in 6.83s
KILLED   减少动态效果时还留着动画延迟  | 1 failed, 84 passed in 19.91s
KILLED   首页网格的列能被内容撑宽  | 1 failed, 85 passed in 14.61s
19/19 killed
```

第一遍「通知公告混进攻略」没被抓到：测试里那篇攻略最早发布，本来就挤不进最新 5 篇。改成最后发布后抓到。

浏览器：1280×800、1440×900 截图与样稿 M 对照一致（首屏、近期安排卡、快捷入口；首屏以下的资讯、通知公告、活动统计、战队）。手机 375×812 下 `scrollWidth` 375，近期安排卡排在文字下面，快捷入口两列。

## 设计偏差

- 5.2 原写「赛事是已通过队数 / 名额」，但赛事表没有名额字段。改设计（只写「已通过 N 队」），没有加字段

## 未完成 / 顺带发现 / 需要确认

- **截图时发现的两个真问题，当场修了**：
  - 「减少动态效果」只把动画时长缩到接近 0，没去掉延迟，近期安排卡 300ms 的入场延迟期间是透明的（无头浏览器截图时整张卡不见）。全局规则加上 `animation-delay: 0s`、`transition-delay: 0s`，测试
  - 手机上资讯卡被分类标签条撑到 493px 宽（网格的默认列不会比内容窄），首页网格改 `minmax(0, 1fr)`，测试。081 的样稿 H 也踩过同一个坑
- 「近期安排」里赛事的已通过队数，未通过审核前总是 0，看起来冷清。要不要换成「已报名 N 队」（含待审核）？现在按设计 8.2「只有已通过的队伍公开」写的
- 本地开发库里填了示例的社区成立日期（2023-05-24）和 QQ 群链接，只在本地
- 其他页面的版式：083 起

## 改动文件

- 模型与迁移：`core/models.py`、`core/migrations/0012_*`、`content/models.py`、`content/migrations/0005_*`
- 逻辑：`content/home.py`（重写）、`core/signals.py`（新）、`core/apps.py`、`scrims/services.py`、`tournaments/registration.py`、`members/signals.py`
- 模板与样式：`content/templates/content/home_page.html`（重写）、`assets/css/input.css`、`templates/components/icon.html`、样张页（`core/templates/core/styleguide.html`、`core/styleguide.py`）
- 删除：`static/js/carousel.js`
- 测试：`content/tests/test_home_sections.py`、`content/tests/test_content.py`、`core/tests/test_design_system.py`、`tournaments/tests/test_public_pages.py`、`scrims/tests/test_home_listing.py`
- 文档：`docs/design.md`、`README.md`
