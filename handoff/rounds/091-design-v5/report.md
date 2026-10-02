# 091 实现报告

## 结论

完成。设计 v5.0 + v5.1 落地：深红 + 橙两个强调色，五个栏目页头背后有图，首屏全屏、半透明的交大校徽齿轮慢转、数字条在首屏底边；深浅色可以在页头切换（默认跟随系统），除页脚和带封面的横幅外全站跟着模式走；首屏和栏目页头的占位场景各有白天版；42 张占位图都会动。中途做过的光点首屏和「印刷排版」被用户否决，没进仓库。

## 逐条结果

1. **设计先改**（`docs/design.md` 文档头 v5.1）：13.2 约束后补 v5.0、v5.1 两段（用户原话、被否掉的两版）；13.2.1 第 1、2、3、5 条；13.2.2 颜色的写法（`dark` 变体）、令牌表（`accent` 一组、`accent-display`、`warn` 新值、`night-*`、`scrim` 到 80%）、对比度规则；13.2.3 首屏标题字号；13.2.4 动效；13.2.5 表（首屏、栏目页头）、「图上的字」两种压法、新的「动起来」「首屏和栏目页头」两节、占位图文件数；13.2.6 页头、主导航、新 `c-theme`、页脚、栏目头、按钮、状态、大图卡、进度条、数字条、筛选、首屏、横幅、新 `c-scene--*`，加「深色条」一段；13.2.7 首页骨架；13.2.8 校徽、占位图；13.3 页头和手机端；5.2 首屏一行（数字条并进去）；12.4.1 `hero_image` 说明和五个 `banner_*`；13.13.4 栏目横幅；第 19 章第 9 条改成「可以切换」；附录 D 记 v4.2（没发布、被取代）、v5.0、v5.1
2. **颜色**（`assets/css/input.css`）：新令牌 `accent`、`accent-text`、`accent-display`（v5.1，大字用的橙 `#CC6F00`，浅色底上 3.3:1）、`accent-soft`、`on-accent-soft`、一组 `night-*`；`warn` 改 `#736000` / `#F6F0C6`。当前导航、筛选、进度条用 `accent`，「报名中」用 `accent-soft`
3. **`dark` 变体**：`@custom-variant dark` 两个条件（`data-theme="dark"`；或系统深色且没选浅色），深色值写在 `:root { @variant dark { … } }`。`tailwind build` 编译成两条普通规则（一条在 `@media (prefers-color-scheme: dark)` 里）；`tailwind runserver` 的监视进程输出保留 CSS 嵌套的版本，测试两种都认。顺带：原来深色块里的 `:root { color-scheme: dark }` 和后面的 `:root { color-scheme: light }` 优先级相同，按层叠规则后写的赢，深色模式下表单控件、滚动条可能还是浅色的（旧版本没在浏览器里复现）；现在变体的选择器优先级更高，内置浏览器里读到选深色时 `color-scheme` 是 `dark`、选浅色是 `light`
4. **切换**：`static/js/theme.js` 放在 `<head>`、样式表前面，同步执行：读 `localStorage["ow-theme"]` 写 `<html data-theme>`；页面加载后显示菜单、标记当前项（`aria-pressed`）、点了就存或清、把浏览器地址栏颜色（`theme-color`）改成页头的颜色；别的标签页改了跟着变；系统模式变了地址栏跟着变；存储出错（无痕模式）不影响切换本页。页头是 `<details class="c-theme">`（太阳 / 月亮图标，三项），手机上在菜单里是一行三个按钮（`c-drawer__theme`），两处都默认 `hidden`。新图标 `sun`、`moon`、`monitor`
5. **跟着模式走**：深色条（`night-*` 换值）只剩 `.c-stage:not(.c-stage--plain)` 和 `.c-footer`；页头 `surface` 底；栏目头 `surface` 底加底线；首屏和栏目页头的压层从 `night` 改成 `bg`（浅色下是白、深色下是近黑），字用正文色；首屏标题第二行和数字用 `accent-display`；校徽主体用 `fg` 20%、齿轮用 `primary` 55%；「加入 QQ 群」从 `c-btn--light` 改 `c-btn--secondary`。带封面的横幅试过跟着模式压白色，深色封面变成一片灰、面包屑看不清，所以保持深色（设计 13.2.5、13.2.6 写明）
6. **栏目页头图**：`SiteSettings` 加 `banner_news`、`banner_tournaments`、`banner_scrims`、`banner_teams`、`banner_members`（`core/0014`，后台「栏目横幅」一组）；`templates/components/pagehead_picture.html` 用在五个栏目页；改横幅时 `core/signals.py` 请求重新生成对应栏目页（资讯是第一个文章栏目页的地址）
7. **场景图**：模板标签 `{% section_picture 位置 类名 %}`（替换掉 `section_banner`）：上传了图就一张；没上传就两张 `<img>`（`c-scene--light` 是 `section-<位置>-light.svg`，`c-scene--dark` 是目录里那张），样式按模式只显示一张。设置从请求上取（上下文处理器已经读过），不多查一次库——一开始直接 `SiteSettings.load()`，战队列表的查询数测试从 4 变 5，改掉了
8. **首屏**（`home_page.html`）：数字条挪进 `c-hero` 底部（`c-hero__foot` 里的 `<dl class="c-stats">`），首屏是纵向弹性布局，正文一块撑开居中；底边多压一层 `bg` 渐变，数字下面的图不抢眼；校徽桌面宽 `min(40rem, 46vw, 100svh - 16rem)`，手机 `min(19rem, 72vw)`。校徽拆层：`core/emblem.py`（`<defs>` 之后最长的路径是齿轮）+ `manage.py render_emblem_layers`，生成 `static/img/sjtu-emblem-body.svg`、`sjtu-emblem-gear.svg`
9. **动图**（`core/placeholders.py`）：
   - `_Svg.animate()` 生成一条类规则（时长、起点、方向、`transform-box`、可选 `--d`），`render()` 把用到的 `@keyframes` 和类放进一个 `<style>`，最后一条是「减少动态效果」时 `animation: none`
   - 动画的时长、起点、分组用**另一个随机数序列**（`Random(-种子)`），画图的序列一次都没多取：对比 090 提交的文件，所有圆、矩形、塔楼路径原样都在；不同的只有夜景窗户按节奏重新分组（同样的窗户分到不同的 `<path>`）和沙丘两端从 ±20 延到 ±80（Catmull-Rom 曲线在画面边上有一点点不同）
   - 九种场景各自怎么动见设计 13.2.5「动起来」；要平移的图层两边、下边各多画 80px
   - 白天版：`SECTION_SCENES` 每个位置带一套白天配色（列表长度和夜里的一致，随机抽取的结果才一样），`render_daylight()`；天际线加了 `towers`、`clouds`、`beacon` 三个可选键，山峦、极光加 `clouds`
   - `every_file()` 给出全部 42 张；`render_placeholders` 写全部、删掉不在清单上的 `cover-*` 和 `section-*`
   - 42 张共 576KB，最大一张 21KB
10. **后台说明文字**：首屏图片、栏目横幅的说明改成「按浅色或深色模式压一层白色或深色」；`core/0014` 重新生成（本轮新迁移，还没提交过），操作和原来一样
11. **样张页**：`core/styleguide.py` 的色卡补全新令牌和 `night-*`，值和令牌一致
12. **文档**：README（视觉一段、`input.css` 写法、占位图会动和白天版、首页和后台「栏目横幅」）；AGENTS.md（`render_emblem_layers`、深浅色的坑改写、`tailwind runserver` 改写 `app.css` 的新坑）；`THIRD_PARTY_NOTICES.md`（校徽两层、只用在首屏）
13. **演示数据**（本机，不进仓库）：本机库的「首屏图片」是之前手动上传的一张 JPG（不会动），清空了；图还在图库里

## 验收输出

整组检查（Windows 本机，`PYTHONUTF8=1`）：

```
All checks passed!
253 files already formatted
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
1041 passed in 182.06s (0:03:02)
No changes detected
System check identified no issues (0 silenced).
```

（格式检查第一次报 `core/tests/test_regeneration_events.py` 要重排：追加的测试用了 LF、原文件是 CRLF。`ruff format` 之后上面是重跑的结果；这个文件单独跑 `10 passed in 3.25s`。）

变异（`handoff/rounds/091-design-v5/mutate.py`，先跑基线，红了就停）：

```
baseline green, 16 tests
caught night band covers the masthead again -> test_only_the_footer_and_banners_with_a_cover_stay_night
caught night scene hidden in dark mode too -> test_each_scene_shows_only_in_its_own_mode
caught a rule reads the system mode directly -> test_the_dark_values_apply_when_chosen_or_when_the_system_is_dark
caught display orange too bright on white -> test_text_and_field_colours_meet_wcag_aa
caught hero veiled in night, not the page ground -> test_the_hero_and_section_heads_are_veiled_in_the_page_ground
caught emblem drawn opaque white -> test_the_emblem_is_see_through_in_the_mode_s_colours_and_its_gear_turns
caught theme script loads late -> test_the_mode_is_set_before_the_page_paints
caught theme menu shown without the script -> test_the_masthead_offers_three_modes_once_the_script_runs
caught storage write not guarded -> test_the_script_keeps_a_pick_and_forgets_it_for_the_system
caught pictures ignore reduced motion -> test_every_picture_moves_and_stands_still_under_reduced_motion
caught pictures ignore reduced motion -> test_the_committed_pictures_are_what_the_code_draws
caught day palette with a different list length -> test_the_committed_pictures_are_what_the_code_draws
caught only the night scene behind a section head -> test_a_section_head_has_its_scene_by_day_and_night
caught only the night scene behind a section head -> test_the_hero_shows_the_uploaded_picture_or_else_its_scene_by_day_and_night
caught settings loaded again instead of from the request -> test_team_list_does_not_run_a_query_per_team
caught a section banner refreshes nothing -> test_a_section_banner_refreshes_its_section_page
caught the news banner refreshes nothing -> test_a_section_banner_refreshes_its_section_page
caught figures back under the hero -> test_the_figures_close_the_hero
restored and green; missed: none
```

16 处变异、18 项检查全部被抓到。

动画确实在播（无头 Edge 打开 `cover-02.svg`，`document.getAnimations()`，间隔 2 秒）：

```
[["breathe","running",1383],["flick","running",1383],["flick","running",1383],[24,false]]
[["breathe","running",3384],["flick","running",3384],["flick","running",3384],[24,false]]
```

（24 个动画在跑，`prefers-reduced-motion: reduce` 为 false。）

切换：在内置浏览器里用脚本点按钮、读计算后的样式（下面是整理过的读数，不是原始输出）：

- 打开首页：没有 `data-theme`，「跟随系统」那一项 `aria-pressed="true"`
- 点「深色」：`data-theme="dark"`，`localStorage` 存了 `dark`；`body` 背景 `rgb(14, 16, 20)`，页头 `rgb(23, 26, 32)`，`theme-color` 也是 `rgb(23, 26, 32)`；夜里那张场景图 `display: block`、白天那张 `none`；菜单收起
- 打开 `/news/`：仍是 `data-theme="dark"`，背景 `rgb(14, 16, 20)`
- 点「浅色」：背景 `rgb(245, 246, 248)`；点「跟随系统」：`data-theme` 去掉，`localStorage` 里没有了

截图（无头 Edge，1440×900 和 390×844，浅色 / 深色）：首页、资讯、赛事详情、手机首页和菜单都看过，发给了用户。

## 设计偏差

无。实现中改设计的地方都先改了文档：带封面的横幅保持深色（见逐条第 5 条）、`accent-display` 新令牌、手机上开关在菜单里。

## 未完成 / 顺带发现 / 需要确认

- **需要确认**：页脚和带封面的横幅两种模式都是深色；「加入 QQ 群」改成描边按钮。用户没说过，是我定的
- **未验证**：资讯列表一屏同时播八九张动图，低端手机上的耗电和流畅度没测。SVG 当图片放时，动起来浏览器要整张重画；只改透明度和位移，已经尽量便宜
- **未验证**：浏览器兼容。`dark` 变体编译后是普通选择器；`theme.js` 用的都是老 API。没在 QQ 浏览器、微信内置浏览器里试过
- **顺带发现**：`tailwind runserver` 在本机改任何被扫描的文件后，会把 `app.css` 重写成不压缩、带嵌套的版本，读 `app.css` 的老测试 `test_body_text_rules_match_what_wagtail_renders` 在这种状态下会红（CI 先 `tailwind build`，不受影响）。写进了 AGENTS.md 的坑
- **顺带发现**：错误页（`error.css`）仍然只跟随系统，访客手动选的模式到错误页不生效。设计 13.15 本来就这么写，没改
- 「不正式、AI 味太浓、字号千篇一律」这条意见：试的「印刷排版」被否了，还没有别的解法

## 改动文件

- 设计和文档：`docs/design.md`、`README.md`、`AGENTS.md`、`THIRD_PARTY_NOTICES.md`、`handoff/STATUS.md`、本目录
- 样式和脚本：`assets/css/input.css`、`static/js/theme.js`（新）
- 模板：`templates/base.html`、`templates/components/icon.html`、`templates/components/pagehead_picture.html`（新）、`content/templates/content/home_page.html`、`content/templates/content/article_index_page.html`、`tournaments/templates/tournaments/index.html`、`scrims/templates/scrims/index.html`、`teams/templates/teams/index.html`、`members/templates/members/index.html`
- 代码：`core/models.py`、`core/migrations/0014_sitesettings_section_banners.py`（新）、`core/signals.py`、`core/templatetags/ow.py`、`core/placeholders.py`、`core/emblem.py`（新）、`core/management/commands/render_placeholders.py`、`core/management/commands/render_emblem_layers.py`（新）、`core/styleguide.py`
- 生成的文件：`static/img/placeholders/cover-01.svg` … `cover-36.svg`（加了动画）、`section-*-light.svg`（新，6 张）、`static/img/sjtu-emblem-body.svg`、`sjtu-emblem-gear.svg`（新）
- 测试：`core/tests/test_colour_modes.py`（新，16 条）、`core/tests/test_cover_placeholders.py`、`core/tests/test_design_system.py`、`core/tests/test_regeneration_events.py`、`content/tests/test_home_sections.py`、`content/tests/test_editorial_pages.py`
