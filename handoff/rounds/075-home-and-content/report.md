# 075 实现报告

## 结论

**完成。** 首页按设计 5.2（v2.0）的五个区块重做；资讯列表、文章页、普通页面、正文块、评论区、搜索结果、投稿入口都换成 074 的设计体系；焦点图脚本重写。赛事、内战、战队、成员、个人中心、登录注册仍是旧模板（076、077）。

## 逐条结果

| 任务 | 结果 |
|---|---|
| 1 首页 | 头条：左边焦点图（16:9、右下切角、编号 `01 / 03`、每张一个标题、索引按钮带进度红线），右边「近期」紧凑票根；01 资讯：列表行（置顶带标签）+ 侧栏分类和投稿框；02 赛事与内战（深色）：14 天日程带 + 赛事票根（带已通过的队数）+ 内战紧凑票根（带名额格）；03 战队：6 个图块（队标或斜纹首字、人数、招募中）；04 参与：四个入口一句话说明 + 成员总数 |
| 2 `content/home.py` | 删 `picture_news`、`scrim_calendar`、`event_cards`；新增 `next_up`（按日期合并、最多 4 条）、`day_strip`（今天起 14 天，公开和已结束的内战、开赛的赛事）、`strip_scrims`、`arena_tournaments`（报名中按截止、即将开放按开放时间，最多 3 个）、`approved_counts`、`signup_counts`、`member_count`；要闻 7 → 6 篇、战队 5 → 6 支。顺手删掉 065 起就没人用的 `home_articles` 上下文和 `HOME_ARTICLE_COUNT` |
| 3 焦点图脚本 | `static/js/carousel.js` 重写：切换幻灯片和标题、索引的 `aria-current`、`data-playing` / `data-paused` 控制 CSS 进度条；悬停、键盘聚焦、切到后台、减少动态效果时停；点索引跳转并重新计时 |
| 4 资讯列表 | 栏目头（带「我要投稿」）、分类标签条（链接，当前项红线）、列表行（日期、分类、作者、标题、摘要、缩略图）、分页；删掉 `_news_side.html` |
| 5 文章页 | 面包屑、分类标签、标题、日期和作者、封面、`c-prose` 正文、文末资料表（作者、栏目、发布）、**关联赛事的票根**（只显示公开的赛事）、评论区；右侧「同栏目 · 最新」4 篇 |
| 6 正文块 | 图片不裁切（`width-1400`）、引用上下两条线、视频 16:9 |
| 7 普通页面 | 栏目头（最后更新日期）+ 左侧「关于本站」+ 正文 |
| 8 评论区 | 方形首字头像、昵称、时间、置顶标签（上沿 2px 墨线）、已隐藏 / 已编辑；赞、回复、编辑、删除、置顶、隐藏用 `c-act`（图标 + 文字，44px 高）；回复串 `<details>` 缩进加竖线；HTMX 的目标、`hx-include`、隐藏排序字段、加载更多全部照旧 |
| 9 搜索 | 栏目头里的大搜索框、结果总数、按类型分组（每组数量）、列表行加摘录；没找到用空状态 |
| 10 投稿入口 | 栏目头 + 警示提示列出原因 + 去登录 / 返回个人中心 |
| 11 样张页 | 加了焦点图（15）和评论（16） |

## 设计偏差

改设计的地方（都在本轮先改了文档）：

- 5.2 首页赛场区块：内战列表写明是「还没开始的」，赛事票根带已通过队数，点日程带的格子去当天第一场
- 13.2.8「刊物列表」：侧栏改成可选（资讯列表把投稿入口放进了栏目头）
- 13.2.7：新增「小操作」`c-act`；评论置顶用墨线不用红线（红线只表示当前位置）
- 附录 C：新增首页「近期」4 条、资讯 6 篇、日程带 14 天、赛场赛事 3 个、战队 6 支、文章页同栏目最新 4 篇

**顺带补上的旧缺口**：设计 5.2 的 ArticlePage 字段表早就写着「关联后文章页底部显示赛事卡片和报名入口」，065 的文章页模板里并没有，本轮加上了（第六处「以后再接」没接上的，STATUS 里记着前五处）。

## 验收输出

```
$ uv run ruff check . && uv run ruff format --check .
All checks passed!
243 files already formatted

$ uv run python manage.py tailwind build --force
Built production stylesheet '/home/user/sjtu-ow/static/css/app.css'.

$ uv run pytest -q
927 passed in 250.46s (0:04:10)

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ （生产配置）uv run python manage.py check --deploy
System check identified no issues (0 silenced).

$ uv run python manage.py render_error_pages   # 然后 git status deploy/：无变化
Wrote /home/user/sjtu-ow/deploy/error_pages/maintenance.html
```

919 → 927。`app.css` 138416 字节，gzip 后 24112 字节。Docker 构建未验证（没有守护进程）。

**改掉的旧测试**（都是断言旧设计的）：

- `test_home_sections.py`：删掉图片新闻、赛事卡片、月历三条（那三个函数随设计删除），换成近期、日程带、赛场赛事、首页区块、图块人数、文章页正文 / 封面 / 同栏目 / 关联赛事、分类标签共 11 条
- `scrims/tests/test_home_listing.py::test_the_homepage_lists_the_next_seven_days`、`tournaments/tests/test_public_pages.py::test_the_homepage_lists_tournaments_open_for_registration`：原来断言整个首页只出现 7 天内的内战、只出现报名中的赛事。新设计里「近期」仍是这个规则，但赛场区块本来就要列 14 天内的内战和即将开放的赛事。改成：「近期」一栏里按老规则断言；整页里草稿、取消、已截止、已开始的仍然不出现

## 变异

`handoff/rounds/075-home-and-content/mutate.py`，跑上面三个测试文件：

```
KILLED   近期不按日期合并  | 1 failed, 46 passed in 11.77s
KILLED   近期不限 4 条  | 1 failed, 46 passed in 11.72s
KILLED   近期的标签对调  | 1 failed, 46 passed in 11.95s
KILLED   日程带多一天  | 1 failed, 7 passed in 4.22s
KILLED   日程带数进草稿和取消的内战  | 1 failed, 7 passed in 4.21s
KILLED   日程带不数赛事  | 1 failed, 7 passed in 4.19s
KILLED   日程带数进草稿赛事  | 1 failed, 7 passed in 4.32s
KILLED   今天标错一天  | 1 failed, 7 passed in 4.34s
KILLED   内战列表留着已结束的  | 1 failed, 8 passed in 4.60s
KILLED   即将开放的排在报名中前面  | 1 failed, 9 passed in 4.45s
KILLED   赛场赛事不限 3 个  | 1 failed, 6 passed in 4.32s
KILLED   同栏目最新含本篇  | 1 failed, 16 passed in 7.50s
KILLED   同栏目最新混进别的栏目  | 1 failed, 16 passed in 7.36s
KILLED   同栏目最新取 6 篇  | 1 failed, 16 passed in 7.25s
KILLED   正文不包 c-prose  | 1 failed, 15 passed in 6.60s
KILLED   文章页不显示封面  | 1 failed, 15 passed in 6.42s
KILLED   草稿赛事也挂在文章下面  | 1 failed, 17 passed in 7.43s
KILLED   分类标签不标当前项  | 1 failed, 18 passed in 8.42s
KILLED   没有焦点图也加载脚本  | 1 failed, 4 passed in 3.01s
KILLED   焦点图索引不编号  | 1 failed, 5 passed in 3.55s
KILLED   赛场票根不显示通过的队数  | 1 failed, 10 passed in 4.69s
KILLED   战队图块不写人数  | 1 failed, 12 passed in 5.37s
KILLED   近期混进 7 天后的内战  | 1 failed, 21 passed in 9.39s
23/23 killed
```

## 真浏览器里的焦点图

Playwright 打开首页（3 张焦点图）：

```
start 0 0
after 5.4s 1 1
hovered 5.4s 1 paused=
clicked 3rd 2 2
errors []
```

5 秒后换到第 2 张（索引和标题一起换）；悬停 5.4 秒不动；点第 3 个索引跳过去；没有脚本错误。

## 截图

1280 和 390：首页（三段）、资讯、文章（未登录、登录后含评论）、隐私政策（先跑了 `load_legal_pages`）、搜索。发现并修掉：

- 日程带在手机上「10月1」挤成竖排：月份单独一行（第一格和每月 1 号）
- 搜索框里浏览器自带的蓝色清除按钮：隐藏
- 评论的小操作原来 32px 高：改成 44px（设计 13.2.2 的点击区域），用负边距保持视觉紧凑
- 置顶评论原来用了红线：改成墨线，红线只留给「当前位置」

## 未完成 / 顺带发现

- 本会话推分支 `claude/nifty-planck-i1qe4u`，CI 没跑；测试机没部署（没有 SSH 密钥）
- 首页的「近期」和赛场区块都靠每晚全量重新生成来推进日期（日程带的「今天」、7 天窗口）；已有的「进入 7 天窗口时刷新首页」任务仍然有效。进入 14 天窗口没有单独的刷新，最晚第二天夜里补上。影响小，没加
- 演示数据脚本里文章分类用了 `report`、`essay` 这种不存在的网址片段，落到了别的分类上，只影响本地截图

## 改动文件

```
docs/design.md（5.2、13.2.7、13.2.8、附录 C）、README.md
assets/css/input.css                               评论、日程带月份、搜索框
content/home.py、content/models.py
content/templates/content/{home_page,article_index_page,article_page,standard_page,submit}.html
content/templates/content/blocks/{image,quote,video}.html
content/templates/content/_news_side.html           删除
comments/templates/comments/{section,_item,_reply,_like,_own,_composer,_more}.html
search/templates/search/results.html
templates/components/{article_row,tournament_ticket,scrim_ticket,team_tile}.html   新建
core/templatetags/ow.py                             lookup 过滤器
core/templates/core/styleguide.html                 焦点图、评论
static/js/carousel.js
content/tests/test_home_sections.py、scrims/tests/test_home_listing.py、tournaments/tests/test_public_pages.py
handoff/STATUS.md、handoff/rounds/075-home-and-content/
```
