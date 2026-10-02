# 098 实现报告（分支 claude/flat-muted-ui）

## 结论

完成，提交在分支上。首页「近期」不再留大块空白；进度条换成名额格；状态标签去掉底色块，改成山形记号加字。

## 逐条结果

1. **近期**：删掉 v5.2 的「行 `flex: 1` 拉到和大图卡等高」；两栏时 `.c-upcoming--two > .c-feature` 取消 16:9、最低 18rem，高度跟着网格行（由列表决定）
2. **名额格**：模板标签 `seats(taken, total)`（`core/templatetags/ow.py`，最多 24 格，超过时每格代表一份，超员时全满）；组件 `templates/components/seats.html`（`role="img"`、读屏标签）；样式 `.c-seats`（格高 6px、2px 圆角、格间 3px、报了的 `accent`、空的 `surface-2`）。首页、`scrim_row`、内战详情横幅、样张页换掉 `<progress>`；删掉 `.c-meter`
3. **状态**：`.c-status` 去掉底色、内边距、圆角，`::before` 是 `peaks.svg` 遮罩，颜色取 `--status`；各状态设 `--status` 和字色；带图横幅、大图卡里字用 `night-fg`
4. **文档**：设计 13.2.6 状态、名额格；细节文档「近期」
5. **测试**：`test_flat_muted.py` 加 3 条；`test_arena_pages.py`、`test_home_sections.py` 改成数格子，`test_design_system.py` 样张页组件清单 `c-meter` 换 `c-seats`

## 验收输出

（Windows 本机，`PYTHONUTF8=1`，分支，开发服务器停掉后跑）

```
All checks passed!
267 files already formatted
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
1214 passed in 204.46s (0:03:24)
No changes detected
System check identified no issues (0 silenced).
```

变异（`handoff/rounds/098-seats-and-status/mutate.py`）：

```
baseline green, 3 tests
caught the pill comes back -> test_a_status_is_a_mark_and_a_word_not_a_pill
caught a status without its mark -> test_a_status_is_a_mark_and_a_word_not_a_pill
caught taken seats counted from the end -> test_places_are_counted_in_cells_not_a_bar
caught no ceiling on cells -> test_places_are_counted_in_cells_not_a_bar
caught the bar comes back on the home page -> test_places_are_counted_in_cells_not_a_bar
caught the rows stretch again -> test_the_upcoming_scrims_keep_their_own_height
caught seats in the wrong colour -> test_places_are_counted_in_cells_not_a_bar
restored and green; missed: none
```

7 处变异全部被抓到。

## 设计偏差

无。

## 未完成 / 需要确认

- **需要确认**：`c-tag` 属性标签要不要也去掉底色块
