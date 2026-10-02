# 096 实现报告（分支 claude/flat-muted-ui）

## 结论

完成，提交在分支上，没有合并到 `main`。浅色模式不再泛黄；全站不画描边，改成用色块切开；圆角加大、按钮胶囊；带图页头底边是两道平涂折线，以不同速度漂移；列表行首的日期只留字。

## 逐条结果

1. **不泛黄**：浅色的 `bg`、`surface`、`surface-2`、`line`、`control`、`fg`、`fg-2`、`fg-3`、`toast`、`on-toast` 回到 v5 的值；`error.css`、样张页色板、邮件、设计表同步。强调色和深色模式没动
2. **不画边**（脚本按选择器逐条处理，`input.css`）：33 处用 `--color-line` 画的描边和分隔线——页头、页脚、菜单、抽屉、卡片、名片、战队卡、成员小卡、表单步骤、登录卡、空状态、标签栏、评论、首屏数字条、目录、作者卡、上下篇、详情横幅等——去掉；表格行和菜单分隔改成 2px 页面底色的切口；位置标签和评论排序的描边改成浅色块；文章 `<hr>`、样张页白色色块的描边保留；输入框边框保留
3. **分组列表**：`c-rows` 改成弹性列、间隙 3px、没有自己的底色；每行一块白色，4px 圆角，第一行上角、最后一行下角 16px；悬停时底色深一档
4. **圆角**：新增 `--radius-md` 12px、`--radius-lg` 16px，19 个卡片类组件改用 16px；按钮改 `--radius-full`；卡片悬停从描边变深改成底色变深
5. **地平线**：先改成两道平涂折线（远的半透明，`HORIZON_STEP = "0.5"`），再按用户「可以改成动态的」拆成 `horizon-far.svg`、`horizon-near.svg` 两张首尾等高、能无缝拼接的遮罩（`_tiling_ridge()`），CSS 两层遮罩各自 `repeat-x`，`@keyframes c-horizon` 让远的 120 秒走一张图宽、近的两张；站点原有的「减少动态效果」规则会停住它。旧的 `horizon.svg` 删除
6. **日期**：`c-date` 去掉灰色底和圆角，48px 宽左对齐，月份 14px `accent-text`，日子 32px 数字字体。先做了三种样稿对比（见 review）
7. **文档**：设计 13.2.2 颜色表和 v6.0 草案段落（不画边、圆角、地平线漂移、日期）、13.2.4 圆角、13.2.6 列表行和日期块
8. **测试**：`test_flat_muted.py` 新增 6 条（浅色不偏暖、只剩两处允许的描边、列表是分组块、地平线两层平涂折线、地平线无缝漂移、日期只是字），`test_design_system.py` 登录卡一条改成「没有描边、16px」，`test_cover_placeholders.py` 静态图清单

## 验收输出

整组检查（Windows 本机，`PYTHONUTF8=1`，分支 `claude/flat-muted-ui`）：

```
All checks passed!
266 files already formatted
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
1201 passed in 214.05s (0:03:34)
No changes detected
System check identified no issues (0 silenced).
```

（中间两次全量各有一次 `test_6v6_finishes_within_a_second` 超时，单独跑三次都过，见 review。最后这次全过。）

变异（`handoff/rounds/096-md3-cuts/mutate.py`）：

```
baseline green, 7 tests
caught the warm paper comes back -> test_the_light_neutrals_have_no_warm_cast
caught warm text comes back -> test_the_light_neutrals_have_no_warm_cast
caught a card is outlined again -> test_nothing_is_outlined_only_toned_apart
caught table rows are ruled again -> test_nothing_is_outlined_only_toned_apart
caught table rows are ruled again -> test_a_list_is_a_group_of_tiles
caught the list is one box -> test_a_list_is_a_group_of_tiles
caught the tiles' inner corners round off -> test_a_list_is_a_group_of_tiles
caught the transition ridge is solid -> test_the_horizon_steps_down_in_two_flat_ridges
caught the horizon stands still -> test_the_horizon_drifts_without_a_seam
caught the near ridge drifts no faster -> test_the_horizon_drifts_without_a_seam
caught a seam where the tiles meet -> test_the_horizon_drifts_without_a_seam
caught the date back in a grey box -> test_a_row_leads_with_its_date_as_type_not_a_box
caught a small day -> test_a_row_leads_with_its_date_as_type_not_a_box
caught the sign-in card outlined and square -> test_sign_in_is_a_card_beside_what_an_account_is_for
restored and green; missed: none
```

13 处变异（14 项检查）全部被抓到。

地平线确实在动：无头 Edge 隔 4 秒读两次遮罩位置，战队页 `-38.7px 100%, -77.3px 100%` → `-92.0px 100%, -184.0px 100%`，赛事列表页头 `-39.1px, -78.2px` → `-92.4px, -184.9px`。

## 设计偏差

无。

## 未完成 / 顺带发现 / 需要确认

- **需要确认**：强调色和深色模式要不要也回到 v5；合并还是继续试
- **未验证**：手机宽度、Safari
- **顺带发现**：开发服务器每次改 Python 文件都卡死，这一轮重启了五次
