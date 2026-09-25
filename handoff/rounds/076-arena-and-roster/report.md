# 076 实现报告

## 结论

**完成。** 赛事、内战、战队、成员展示的公开页面换成设计体系的「赛场列表」「赛场详情」「名册」骨架。报名、个人中心、登录注册这些表单页在 077。

**顺带修了一个真问题**：设计 13.13.4 的事件表写着「报名开始、报名截止、活动开始等时间点到达 → 对应的详情页、列表页、首页，发布时就按这些时间点排好延时任务」。赛事是这么做的，**内战只在「进入 7 天窗口」和「开始」时刷新首页**，内战的详情页和列表页从来没按时间点刷新过。以前静态页上只印「报名截止 某时」，看不出问题；本轮票根和页头上写了「报名中」，不补的话报名截止后静态页会一直说「报名中」。按设计补上：报名截止和开始时，首页、内战列表、详情页三处都刷新（第七处「以后再接」式的缺口）。

## 逐条结果

| 任务 | 结果 |
|---|---|
| 1 赛事列表 | 深色栏目头（各阶段数量）；报名中、即将开始报名：票根两列，带已通过队数；已截止、已结束：表格（手机上变成分段） |
| 2 赛事详情 | 深色栏目头：状态形状、仅限交大 / 支持个人报名标签、标题、简介、关键事实条（报名截止、比赛时间、每队人数、已通过、个人报名）、报名入口占位；主栏封面（切角）、说明（`c-prose`）、已通过队伍表、个人报名（位置人数 + 名片）；侧栏资料表、相关文章 |
| 3 内战列表 | 深色栏目头（即将开始、最近结束的数量）；即将开始：票根带名额格；最近结束：表格（时间、规格、报名人数） |
| 4 内战详情 | 深色栏目头：状态、规格、大号日期和时间、关键事实（报名截止、一场需要、已报名 + 名额格）、报名占位；报名表单的位置改成 `c-choice`；主栏说明、三个位置的人数、报名名单表；侧栏资料表 |
| 5 战队列表 | 深色栏目头（创建战队、战队数、招募中数、每队上限）；标签条（带数量）；图块墙（`人数 / 上限`、招募中 / 暂不招募） |
| 6 战队主页 | 深色栏目头：大队标、状态、队名、队长、成立日期、成员名额格、参赛次数、入队占位；主栏简介、成员表、参赛记录表；侧栏资料表 |
| 7 成员展示 | 栏目头、分组目录（标签条样式的锚点，带人数）、每组编号区块头和名片网格、全部成员编号名册（`001` 起，按加入先后） |
| 8 统计挪进服务层 | `tournaments.services.approved_counts`、`scrims.services.signup_totals`、`teams.services.team_totals`（一条聚合查询）；首页改为调用它们 |

另外：报名状态的形状统一成 `components/registration_status.html`（已通过对勾、待审核空心圆、已驳回红色斜杠、已撤回灰色斜杠）；名额格组件加了 `hide_count`，数字已经印在旁边时不再重复；票根上「即将开放」改成和列表分组一致的「即将开始报名」。

## 设计偏差

无新增偏差。内战按时间点刷新是**补上设计早就写了的**（13.13.4 最后一行），不是改设计。

## 验收输出

```
$ uv run ruff check . && uv run ruff format --check .
All checks passed!
244 files already formatted

$ uv run python manage.py tailwind build --force
Built production stylesheet '/home/user/sjtu-ow/static/css/app.css'.

$ uv run pytest -q
936 passed in 255.05s (0:04:15)

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ （生产配置）uv run python manage.py check --deploy
System check identified no issues (0 silenced).

$ uv run python manage.py render_error_pages   # git status deploy/：无变化
Wrote /home/user/sjtu-ow/deploy/error_pages/maintenance.html
```

927 → 936（`core/tests/test_arena_pages.py` 8 条、`scrims/tests/test_home_listing.py` 1 条）。`app.css` gzip 后 24217 字节。Docker 构建未验证。

**改掉的旧断言**：

- `members/tests/test_members.py`：职务的类名 `member-cards__title` 改成 `c-person__title`（065 的类随旧样式表删了）
- `teams/tests/test_teams.py::test_team_list_does_not_run_a_query_per_team`：查询数 3 → 4。页头多了一条「战队数、招募中数」的聚合查询，**仍然是常数**（这条测试防的是每支队一条查询）；第一版是两条 `count()`，合成一条聚合后是 4

## 变异

`handoff/rounds/076-arena-and-roster/mutate.py`：

```
KILLED   报名中的赛事也用表格  | 1 failed in 0.59s
KILLED   阶段数量只数报名中  | 1 failed, 1 passed in 0.80s
KILLED   待审的也算进已通过  | 1 failed, 2 passed in 1.13s
KILLED   详情页不写个人报名人数  | 1 failed, 3 passed in 1.30s
KILLED   详情页已通过写成散人数  | 1 failed, 3 passed in 1.28s
SURVIVED 内战报名人数不按内战分  | 17 passed in 3.13s
KILLED   列表的名额格不画  | 1 failed, 4 passed in 1.63s
KILLED   已结束的内战也算即将开始  | 1 failed, 4 passed in 1.67s
KILLED   战队图块不写上限  | 1 failed, 5 passed in 1.76s
KILLED   招募中的总数不过滤  | 1 failed, 5 passed in 1.85s
KILLED   战队页不写成立日期  | 1 failed, 6 passed in 1.95s
KILLED   名册编号从 000 开始  | 1 failed, 7 passed in 2.29s
KILLED   报名截止时不刷新  | 1 failed, 13 passed in 3.13s
KILLED   开始时只刷新首页  | 1 failed, 13 passed in 3.30s
13/14 killed
```

幸存的是测试写弱了：只有一场内战有报名，统计不按内战分也看不出来。给另一场也加一个报名后重跑：

```
KILLED   内战报名人数不按内战分  | 1 failed, 4 passed in 1.71s
1/1 killed
```

14/14。「已结束的内战也算即将开始」「招募中的总数不过滤」两条第一次写测试时也会幸存（没检查「即将开始」里没有已结束的、只有一支招募中的队），跑变异前先补强了断言。

## 截图

1280：赛事列表、赛事详情（未登录、队长）、内战列表、内战详情（未登录、已报名）、战队列表、战队主页（未登录、队长）、成员展示。390：赛事详情和内战详情（登录后，资料不完整）。发现并修掉：队长看到的报名状态用错了形状（一律蓝色空心方块）；已报名内战的「修改报名」「取消报名」被挤成两行；页头名额格旁边重复印数字。

## 未完成 / 顺带发现

- 演示数据里有人既是队长又在散人池里（脚本随手分配的），页面按队长显示「为战队报名」，符合规则
- 本会话推分支，CI 没跑；测试机没部署

## 改动文件

```
tournaments/templates/tournaments/{index,detail}.html、slots/actions.html
scrims/templates/scrims/{index,detail}.html、slots/{actions,_form}.html
teams/templates/teams/{index,detail}.html、slots/join.html
members/templates/members/index.html
templates/components/{team_tile,slots,tournament_ticket,registration_status}.html
tournaments/{views,services}.py、scrims/{views,services}.py、teams/{views,services}.py、content/home.py
core/templates/core/styleguide.html
core/tests/test_arena_pages.py（新建）、scrims/tests/test_home_listing.py、members/tests/test_members.py、teams/tests/test_teams.py
handoff/STATUS.md、handoff/rounds/076-arena-and-roster/
```
