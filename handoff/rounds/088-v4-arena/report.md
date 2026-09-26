# 088 赛场与名册按 v4.0 重做 报告

## 做了什么

1. **新组件**
   - `tournament_card.html`：赛事图片卡。封面，或者灰底写赛事名；状态和这个阶段要紧的日期；标题；「N–M 人一队 · 已通过 N 队」
   - `scrim_row.html`：内战列表行。日期块；标题；「周五 19:30 · 规格 · 已报 N / M」；进度条；状态
   - `team_tile.html` 改写成 `c-teams` 的一格
2. **列表页**
   - 赛事、内战、战队的栏目头去掉色调底和数字统计条
   - 赛事：报名中、即将开始用图片卡三列，其余用表格
   - 内战：即将开始用列表行，最近结束用表格
   - 战队：`c-teams` 网格，筛选挪进栏目头
   - 区块头的数量徽标全部去掉
3. **详情页**
   - 赛事、内战、战队都用 `c-stage` 横幅。赛事有封面时是大图压暗色渐变；内战、战队是实色条
   - 横幅里写面包屑、状态、标题、一行事实（`dl`）
   - 报名和申请加入挪到横幅下面的 `c-panel`，三个页面状态片段的外边距去掉
   - 侧栏资料表放进 `c-panel`；赛事的相关文章改成列表行
   - 内战的位置统计改成 `dl` 三格；个人报名和内战名单下的说明小字去掉
4. **成员展示**：去掉数量徽标和「按加入先后」，编号 001 起照旧
5. **删除**：`tournament_ticket.html`、`scrim_ticket.html`、`slots.html` 三个组件，`slot_cells`、`percent_of` 两个过滤器，以及票根、名额格、图块墙、`.on-tonal`、`c-pagehead--tonal`、`c-related` 的样式。`section_head.html` 不再输出编号和英文。文章页的关联赛事改用赛事图片卡
6. **样张页**：赛场一节换成横幅、赛事卡、内战行；图块换成 `c-teams`；名额格换成进度条
7. **设计**：13.2.6 补 `c-stage`，13.6 模板目录更新

## 验证

变异（`handoff/rounds/088-v4-arena/mutate.py`）：

```
BASELINE 134 passed in 29.19s
KILLED   报名放回横幅里  | 1 failed, 12 passed in 5.94s
KILLED   资料表不在面板里  | 1 failed, 12 passed in 6.64s
KILLED   内战区块头又带数量徽标  | 1 failed, 1 passed in 2.74s
KILLED   赛事栏目头又带统计条  | 1 failed, 1 passed in 2.72s
KILLED   内战列表行没有进度条  | 1 failed, 4 passed in 3.29s
KILLED   赛事卡数上待审的队  | 1 failed, 2 passed in 2.81s
KILLED   战队格每支队多查一次  | 1 failed, 75 passed in 28.48s
KILLED   位置统计不是三格  | 1 failed, 14 passed in 8.13s
KILLED   横幅图上不压暗色  | 1 failed, 106 passed in 30.81s
9/9 killed
```

整组检查（Windows 本机，`PYTHONUTF8=1`）：

```
All checks passed!
247 files already formatted
Built production stylesheet '...\static\css\app.css'.
1000 passed in 232.44s (0:03:52)
No changes detected
System check identified no issues (0 silenced).
```

测试数从 1003 变成 1000：删掉了名额格的三条测试（组件和过滤器一起删了），新增和改写的测试数目相抵。

**发现的真问题**：第一版的战队格写的是 `{{ members|default:team.member_count }}`。Django 的 `default` 会先把参数算出来，列表页传了人数也会每支队再查一次数据库。`test_team_list_does_not_run_a_query_per_team` 和第 15 章审计测试都红了，已改成 `{% if %}`，并加进变异。

视觉（无头 Edge 截整页）：赛事列表和详情（浅色、深色）、内战列表和详情、战队列表和主页、成员展示，1440 宽截图；这 7 页 375 宽 `scrollWidth` 都是 375。

## 没做的

- 个人中心、表单、评论、错误页（089）
- 评论区还在用 `c-count`（089 改）
