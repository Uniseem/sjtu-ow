# 106 页面切换：加载过渡，不闪、不弹入（报告）

## 经过

第一版（没提交）：`@view-transition` 加「旧页 120ms 淡出、新页 240ms 淡入并上移 8px」。用户在本机看了说闪、而且要的是等待时的加载动画、不是最后的弹入（`request.md`）。改成现在这样：等待时页头底边有加载条，换页那一下只有很短的交叉淡化。

## 做了什么

1. **设计 v6.4**：13.2.4「切换时的过渡」（等待时、换页那一下、深浅色、页内锚点、减少动态效果），13.2.7 组件表加 `c-loadbar`，附录 D
2. **`assets/css/input.css`**：
   - `@media (prefers-reduced-motion: no-preference)` 里 `@view-transition { navigation: auto; }` 和 `html { scroll-behavior: smooth; }`
   - `::view-transition-old(root), ::view-transition-new(root)` 只改 `animation-duration: 150ms`，保留浏览器默认的淡入淡出和 `plus-lighter` 混合；深浅色切换时（`:root.is-theme-switch`）240ms
   - `.c-masthead` 加 `view-transition-name: masthead`
   - 新组件 `.c-loadbar`：页头底边 3px、强调色、从左往右 `scaleX`，`.is-loading` 时 `ow-loadbar 15s ease-out 150ms both`（0 → 0.3 → 0.6 → 0.8 → 0.95）；`view-transition-name: loadbar`，新页面到了随旧页淡掉
3. **`static/js/loading.js`**（新）：站内、离开本页的链接点击（不含修饰键、`target`、`download`、`data-no-loading`、本页锚点）和会离开本页的表单提交（不含 HTMX 表单）时给 `<html>` 加 `is-loading`；15 秒没离开自己去掉；从后退缓存回来（`pageshow` 的 `persisted`）去掉
4. **`templates/base.html`**：页头里放 `<div class="c-loadbar" aria-hidden="true">`，页尾加载 `loading.js`
5. **`static/js/theme.js`**：新函数 `switchTo()`，支持且没要求减少动态效果时用 `document.startViewTransition` 包住切换，期间 `<html>` 带 `is-theme-switch`
6. **导出个人信息的两个链接**加 `download`
7. **测试**：`core/tests/test_transitions.py`（11 条）
8. **探测脚本**：`loadbar_probe.py`、`loading_probe.py`（无头 Edge，借 `cdp_shoot.py` 的 WebSocket 客户端，只用标准库），截图在 `artifacts/`

## 命令输出

变异（`mutate.py`，18 处）：

```
baseline green, 11 tests
caught no cross-page transition -> test_pages_change_with_the_browsers_cross_page_transition
caught transitions even with less motion asked for -> test_pages_change_with_the_browsers_cross_page_transition
caught the new page pops in again -> test_the_swap_is_a_short_cross_fade_without_a_pop_in
caught the swap drags on -> test_the_swap_is_a_short_cross_fade_without_a_pop_in
caught the masthead fades with the page -> test_the_masthead_is_its_own_layer_and_stays_put
caught no bar in the masthead -> test_the_masthead_carries_a_loading_bar_and_its_script
caught the bar script is not loaded -> test_the_masthead_carries_a_loading_bar_and_its_script
caught the bar shows at once -> test_the_bar_waits_a_moment_then_creeps_without_finishing
caught the bar finishes on its own -> test_the_bar_waits_a_moment_then_creeps_without_finishing
caught the bar shows for new tabs -> test_the_script_starts_the_bar_only_for_leaving_this_page
caught the bar shows for same-page anchors -> test_the_script_starts_the_bar_only_for_leaving_this_page
caught the bar shows for HTMX forms -> test_the_script_starts_the_bar_only_for_leaving_this_page
caught the bar never gives up -> test_the_bar_gives_up_and_clears_when_the_page_stays
caught the bar stays on after going back -> test_the_bar_gives_up_and_clears_when_the_page_stays
caught downloads are not marked -> test_downloads_are_marked_so_the_bar_skips_them
caught colour mode jumps -> test_changing_colour_mode_cross_fades
caught colour mode animates despite less motion -> test_asking_for_less_motion_switches_colour_mode_at_once
caught anchors always scroll smoothly -> test_anchor_links_scroll_smoothly_unless_less_motion_is_asked_for
restored and green; missed: none
```

**无头 Edge，换页时实际跑的动画**（`loading_probe.py`，在新页面上用 `pagereveal` 事件读）：

```
new page: {'url': '/news/october-schedule/', 'viewTransition': True, 'loading': False, 'animations': ['::view-transition-group(masthead) -ua-view-transition-group-anim-masthead 250', '::view-transition-group(root) -ua-view-transition-group-anim-root 250', '::view-transition-group(loadbar) -ua-view-transition-group-anim-loadbar 250', '::view-transition-new(root) -ua-view-transition-fade-in 150', '::view-transition-new(root) -ua-mix-blend-mode-plus-lighter 150', '::view-transition-old(root) -ua-view-transition-fade-out 150', '::view-transition-old(root) -ua-mix-blend-mode-plus-lighter 150', ...]}
colour mode: {'transitions': 1, 'during': True, 'after': False, 'theme': 'dark'}
```

页面主体只有浏览器默认的淡入淡出（150ms）和 `plus-lighter` 混合，没有位移；页头、加载条各自成层。深浅色切换走了一次过渡，过程中带 `is-theme-switch`，结束后去掉。

**加载条**（`loadbar_probe.py`）。直接点链接时，点击后读旧页的请求会被调试工具压到新页面加载完才返回（问 0.10 秒、答 2.18 秒），看不到旧页；而且这个链接按下鼠标时就被 105 的规则提前准备了，新页面 100ms 内就到，加载条按设计不出现。所以改成：在 `window` 上再挂一个点击监听（在 `loading.js` 的 `document` 监听之后执行）取消跳转，页面留在原地，看加载条自己怎么走：

```
link http://localhost:8000/news/october-schedule/
100ms (asked 0.10s, answered 0.10s): {'old': True, 'url': '/news/', 'loading': True, 'barWidth': 0, 'opacity': '1'}
700ms (asked 0.70s, answered 0.71s): {'old': True, 'url': '/news/', 'loading': True, 'barWidth': 372, 'opacity': '1'}
1800ms (asked 1.80s, answered 1.81s): {'old': True, 'url': '/news/', 'loading': True, 'barWidth': 690, 'opacity': '1'}
after release: {'old': True, 'url': '/news/', 'loading': True, 'barWidth': 971, 'opacity': '1'}
```

（页头宽 1280px：150ms 前不出现，0.7 秒 29%，1.8 秒 54%，约 4.8 秒 76%。截图 `artifacts/loadbar-light-1800ms.png`、`loadbar-dark-1800ms.png`。）

**验证过程中踩的坑**：

- 内置浏览器面板关掉了预加载，而且开发服务器发静态文件不带 `Cache-Control`，浏览器按启发式缓存，改了 `theme.js` 后面板里跑的还是旧文件（调用栈显示旧文件的行号）
- 无头 Edge 的启动进程会马上退出，`terminate()` 和 `taskkill /T` 都关不掉真正的浏览器。8:29 第一次探测（改 `theme.js` 之前）的那个实例一直占着调试端口 9333，之后每次探测都连到了它和它的旧缓存上，一度得出「深浅色没走过渡」的错误结论。清掉 48 个残留进程后，改成每次用空闲端口、结束时按配置目录名关进程，重测得到上面的结果
- 调试工具在有跳转进行时会把对页面的读取排到跳转结束之后

整组检查（开发服务器停着）：

```
All checks passed!
271 files already formatted
No changes detected
System check identified no issues (0 silenced).
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
1 failed, 1251 passed in 294.15s (0:04:54)
```

失败的是哪条：分两段重跑，`core/` 全过，其余里面是已知的计时测试（`AGENTS.md`「计时测试在机器繁忙时会偶发失败」）：

```
521 passed in 72.02s (0:01:12)
```

```
FAILED scrims/tests/test_teaming.py::test_6v6_finishes_within_a_second - Asse...
1 failed, 730 passed in 330.24s (0:05:30)
```

单独跑：

```
1 passed in 4.82s
```

## 发现的问题（不在本轮修）

- **1280px 左右页头导航的字竖着折成两行**（「首/页」「资/讯」）：宽屏中间的搜索框和导航挤在一起。内置浏览器 1280 宽的截图里也是这样，不是无头浏览器的字体问题
- 演示站的成员页一页 4.2MB 图片（107）

## 未验证

- 真实网络延迟下、普通浏览器里的观感（无头浏览器里换页时看不到旧页的加载条，只能分开验证「加载条会出现、会走」和「换页时的过渡」）
- Safari（支持跨页面过渡，没有设备测）
