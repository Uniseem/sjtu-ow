# 187 下拉菜单点别处收起；前台右键菜单（报告）

## 做了什么

1. `static/js/app.js`：颜色模式（`c-theme`）、账号（`c-menu`）、手机抽屉（`c-drawer`）三个 `<details>` 下拉：打开一个时收起别的（捕获 `toggle` 事件，它本身不冒泡）、点菜单外面收起、按 Esc 收起并把焦点还给按钮。挂在 `document` 上，登录后换进来的账号菜单也管得到。没有脚本时照旧能用
2. `static/js/contextmenu.js`：前台右键弹出本站菜单，用 DOM 接口建元素（不拼 HTML 字符串）。按场合列：链接上「在新标签页打开」「复制链接」；图片上「在新标签页打开图片」「复制图片地址」；选中文字「复制」「在站内搜索“…”」；总有「后退」「前进」「刷新」「复制本页链接」，滚下去过时多「回到顶部」（系统要求减少动态效果时不平滑滚动）。复制成功在鼠标旁提示「已复制」（剪贴板接口不可用时退回 `execCommand`）。空间不够时菜单往左、往上翻。方向键、Home、End 移动，Enter 执行，Esc、Tab、点外面、滚动、改窗口大小、切走窗口都收起
3. 留给浏览器的地方：按住 Shift 右键；输入框、文本框、下拉框、可编辑区域、带 `data-native-contextmenu` 的元素；触屏（主指针不是鼠标时整个脚本不启用，手指或笔触发的右键也交给浏览器）；后台（Wagtail 的模板不加载这个脚本）
4. 样式 `c-ctxmenu`、`c-ctxmenu__item`、`c-ctxmenu__foot`、`c-ctxmenu-toast`：和账号下拉的面板一样，只用颜色令牌，深浅色跟着走，字号不小于 14px
5. `templates/base.html` 在 `app.js`、`loading.js` 后加载；样张页加一个静态的右键菜单
6. 设计 13.2.6、13.3（v6.65）
7. `core/tests/test_menus_and_context_menu.py`（8 条）

## 浏览器里看过（本机开发服务器 + 内置浏览器）

本机开发库落后 6 个迁移，先 `migrate`。用本机开发库里一个已有的演示账号直接生成会话（没有输入密码，用完删掉了），打开 `/news/`：

- 页面加载的脚本：`theme.js, arrival.js, state.js, htmx.min.js, alpine.csp.min.js, app.js, loading.js, contextmenu.js`
- 点开颜色模式菜单 → 开着的是 `["c-theme max-sm:hidden"]`；再点开账号菜单 → 只剩 `["c-menu"]`（用户截图里两个叠着的情况没有了）
- 点页面空白处 → `[]`；再打开账号菜单按 Esc → `{"focused": "SUMMARY.c-menu", "open": []}`
- 在文章标题链接上右键 → 菜单项 `在新标签页打开、复制链接、后退 Alt+←、前进 Alt+→、刷新 F5、复制本页链接`，底部「按住 Shift 再右键：浏览器自带的菜单」，焦点在第一项；下面放不下，菜单翻到鼠标上方（`top 320, bottom 648.8` = 鼠标位置）
- 点「复制链接」→ 菜单收起，提示「已复制」
- Shift 右键空白处 → 没有本站菜单；在页头搜索框里右键 → 没有本站菜单
- 深色模式下选中标题文字右键 → `复制 Ctrl+C、在站内搜索“资讯”、后退、前进、刷新、复制本页链接`，方向键下移到「在站内搜索“资讯”」；面板和高亮在深色下正常（截图）

截图里这个演示账号也有「管理后台」：它在本机开发库里是内容编辑、赛事管理员、内战管理员，符合 185 的规则。

## 命令输出

测试机仍连不上（`ssh: connect to host 2a0e:6a80:3:9c7:: port 22: Network is unreachable`），在本机跑。

变异（本机，11 处，全部被抓到）：

```
baseline green, 6 tests
caught script not loaded -> test_every_front_page_loads_the_menu_script
caught shift no longer gives the browser menu -> test_the_browser_menu_stays_where_it_is_needed
caught form fields taken over -> test_the_browser_menu_stays_where_it_is_needed
caught long press taken over -> test_the_browser_menu_stays_where_it_is_needed
caught phones taken over -> test_the_browser_menu_stays_where_it_is_needed
caught no image actions -> test_it_offers_what_the_design_lists
caught no Esc -> test_it_closes_and_moves_by_keyboard
caught opening one leaves the other open -> test_the_dropdowns_close_on_outside_clicks_esc_and_each_other
caught outside clicks ignored -> test_the_dropdowns_close_on_outside_clicks_esc_and_each_other
caught Esc leaves the dropdown open -> test_the_dropdowns_close_on_outside_clicks_esc_and_each_other
caught style guide without it -> test_the_style_guide_shows_the_context_menu
restored and green; missed: none
```

整组检查（本机，跑之前停了开发服务器）：

```
All checks passed!
355 files already formatted
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
1716 passed, 1 skipped in 169.43s (0:02:49)
No changes detected
System check identified no issues (0 silenced).
```

`docker build` 本机没跑，看 CI。

## 没做

- 右键菜单的测试是查脚本里的关键几处在不在（口子、菜单项、按键），真正的交互只在浏览器里看过一次；测试机恢复后可以把它加进 `journey.py`
- 文章里的 B 站视频是 iframe，右键事件进不到本站页面，照旧是播放器自己的菜单
