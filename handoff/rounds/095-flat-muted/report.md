# 095 实现报告（分支 claude/flat-muted-ui）

## 结论

完成试验，提交在分支 `claude/flat-muted-ui` 上，**没有合并到 `main`**。界面颜色全部换成从占位图里取的低饱和色，「克制」写成彩度上限；带图的页头底边是山脊和雾，区块标题前有山形记号；底图、页脚、错误页、邮件跟着换。

## 逐条结果

1. **颜色**（`assets/css/input.css`，浅色、深色、夜色条三套）：底 `#F1EEE8` / `#141A24`，字 `#1D2531` / `#E8EAEE`，砖红 `#9B3A33` / `#A8463D`，沙杏 `#CF9152` / `#D9A264`，灰绿、赭黄、雾蓝，完整的表在设计 13.2.2。旧的对比度测试照旧全过（AA）。浮层阴影改用夜色混出来
2. **错误页**：`static/css/error.css` 同步，`render_error_pages` 重新生成了 `deploy/error_pages/maintenance.html`
3. **样张页色板**（`core/styleguide.py`）：值同步，「深红」改叫「砖红」，「守望先锋橙」改叫「沙杏（守望先锋橙收淡）」
4. **地平线**：`core/placeholders.py` 加 `render_horizon()`（两道山脊，远的用由淡到浓的渐变当雾，近的实心），生成 `horizon.svg` 当遮罩；`.c-pagehead--picture::before` 和 `.c-stage:not(.c-stage--plain)::before` 用它，颜色取新的 `--page-bg`（在 `:root` 存下页面底色；深色条里 `--color-bg` 被换成夜色，不能直接用）；去掉这两种页头的下边线；详情横幅正文下面留出地平线的高度
5. **山形记号**：`render_peaks()` 生成 `peaks.svg`（远峰半透明、近峰实心）；`.c-sectionhead > h2::before` 用它当遮罩，沙杏色
6. **底图**：`HUE_SCENES` 五套配色换成黄昏低饱和版（砖粉、沙、石板、灰绿、赭）；页脚山脊 `RIDGE_SHADES` 换成新夜色；`render_placeholders` 生成 50 张（多了 `horizon.svg`、`peaks.svg`）
7. **邮件**：`templates/email/` 和 allauth 邮件模板里的写死的颜色换成新值
8. **设计**：13.2.2 颜色表换新值，加「v6.0 草案（分支，未合并）」一段说明画法、规则和地平线、记号、底图
9. **测试**：新文件 `core/tests/test_flat_muted.py`（5 条：令牌彩度、底图彩度、地平线、远山是雾、山形记号）；`test_design_system.py` 两处写死的旧颜色、`test_cover_placeholders.py` 静态图清单和「16:9 场景」的例外（地平线、记号、山脊不是场景）

## 验收输出

整组检查（Windows 本机，`PYTHONUTF8=1`，分支 `claude/flat-muted-ui`）：

```
All checks passed!
266 files already formatted
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
1196 passed in 201.72s (0:03:21)
No changes detected
System check identified no issues (0 silenced).
```

（1196 = 094 的 1191 + 5。）

变异（`handoff/rounds/095-flat-muted/mutate.py`）：

```
baseline green, 5 tests
caught the loud orange comes back -> test_every_colour_token_is_restrained
caught the loud red comes back -> test_every_colour_token_is_restrained
caught a loud base picture -> test_the_base_pictures_are_muted_too
caught the horizon in the band's colour -> test_picture_heads_sink_into_the_page_under_a_horizon
caught no page ground kept -> test_picture_heads_sink_into_the_page_under_a_horizon
caught a rule under the ridge -> test_picture_heads_sink_into_the_page_under_a_horizon
caught the far ridge is solid -> test_the_horizon_fades_its_far_ridge_like_the_art
caught titles without peaks -> test_section_titles_carry_the_peaks
restored and green; missed: none
```

8 处变异全部被抓到。

截图：无头 Edge 1440 宽，浅色 6 张、深色 3 张，发给了用户。

## 设计偏差

无（文档先写了草案再落代码；颜色表和代码一致）。

## 未完成 / 顺带发现 / 需要确认

- **需要确认**：合并还是放弃；交大红收成砖红、守望先锋橙收成沙杏能不能接受
- **未做**：封面插画的白天版（卡片里的深色夜景和淡色界面对比强）
- **未验证**：手机宽度没截图；Safari 的遮罩写了 `-webkit-mask`，没在 Safari 上看
- **顺带发现**：每改一次 Python 文件开发服务器就卡死，这一轮重启了四次（AGENTS 已记）
