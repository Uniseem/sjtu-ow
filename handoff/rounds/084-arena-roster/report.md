# 084 实现报告

## 结论

完成。赛事、内战、战队、成员的列表和详情按 v3.0 调了版式。

## 逐条结果

1. **眉标和区块头**：赛事、内战、战队、成员四页去掉 TOURNAMENTS / SCRIMS / TEAMS / MEMBERS；区块头的数量从借用的 `c-comments__count` 改为 `c-count`，去掉横线占位
2. **侧栏资料卡**：赛事、内战、战队详情页的资料表加 `c-facts--card`（描边大圆角卡，最后一行没有分隔线）；赛事「相关文章」改用文章页的 `c-related`，去掉 `border-b-2 border-fg`
3. **内战位置统计**：`c-rolestats` 三张 `surface-low` 小卡，去掉 `border-y` 和竖线
4. **成员页**：「共 N 位成员」包进一个元素；「全部成员」改 `c-roster` 小卡网格（首字头像、昵称、分组标签、右上角编号 `001` 起），桌面四列、平板两列、手机一列，`data-reveal` 依次出现；区块头旁加人数徽标
5. **设计**：13.2.7 加 `c-facts--card`、`c-rolestats`、`c-roster`；6.3 名册的描述
6. **顺带**：`AGENTS.md` 记下 083 的坑「变异测试前先确认基线是绿的」；本轮的 `mutate.py` 先跑基线，红了就停

## 验收输出

```
== ruff
All checks passed!
247 files already formatted
== tailwind
Built production stylesheet 'C:\Users\fyc12\Desktop\Claudee\sjtu-ow\static\css\app.css'.
== pytest
1 failed, 986 passed in 216.79s (0:03:36)
== makemigrations
No changes detected
== check --deploy
System check identified no issues (0 silenced).
```

那一条失败是 `core/tests/test_arena_pages.py::test_the_roster_numbers_people_by_when_they_joined`：旧测试在昵称前 200 个字符里找编号，新卡片把编号放在昵称后面。改成按卡片拆开、在同一张卡里取昵称和编号（仍然断言 `001`、`002`、`003` 按加入先后）。之后：

```
8 passed in 1.21s
987 passed in 201.33s (0:03:21)
```

跑子集时 `scrims/tests/test_teaming.py::test_6v6_finishes_within_a_second` 偶发失败一次，单独重跑 `1 passed`（`AGENTS.md` 记着的计时测试，机器忙时会慢）。

变异（`handoff/rounds/084-arena-roster/mutate.py`）：

```
BASELINE 9 passed in 4.62s
KILLED   赛事页又带英文眉标  | 1 failed in 1.28s
KILLED   成员页又带英文眉标  | 1 failed, 3 passed in 3.46s
KILLED   内战区块头借用评论计数  | 1 failed, 1 passed in 2.46s
KILLED   赛事资料表不在卡片里  | 1 failed, 4 passed in 4.07s
KILLED   战队资料表不在卡片里  | 1 failed, 4 passed in 4.11s
KILLED   相关文章用回粗线  | 1 failed, 5 passed in 4.74s
KILLED   位置统计用回上下横线  | 1 failed, 6 passed in 5.06s
KILLED   成员数又被拆开  | 1 failed, 7 passed in 6.20s
KILLED   名册不编号  | 1 failed, 8 passed in 6.60s
KILLED   名册卡片没有头像  | 1 failed, 8 passed in 6.09s
10/10 killed
```

浏览器：1280 截图看了赛事列表、赛事详情、内战详情、战队主页、成员；手机 375 下这 5 页 `scrollWidth` 都是 375，名册一列。

## 设计偏差

无。

## 未完成 / 顺带发现 / 需要确认

- 报名、创建战队、申请入队、战队管理这些表单页还带英文眉标（REGISTER、FREE AGENT、NEW TEAM、APPLY、MANAGE），归 085
- 赛事卡片上「0 支队伍已通过」的「0」和文字之间是 `c-meter` 的间距，数字大、文字小，算设计如此

## 改动文件

- 模板：`tournaments/templates/tournaments/{index,detail}.html`、`scrims/templates/scrims/{index,detail}.html`、`teams/templates/teams/{index,detail}.html`、`members/templates/members/index.html`
- 样式：`assets/css/input.css`
- 测试：`core/tests/test_arena_v3.py`（新）、`core/tests/test_arena_pages.py`
- 文档：`docs/design.md`、`AGENTS.md`
