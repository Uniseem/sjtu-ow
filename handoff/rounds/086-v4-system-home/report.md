# 086 设计体系 v4.0：颜色、页头页脚和首页 报告

## 做了什么

1. **设计文档 v4.0**
   - 13.2 重写：约束（用户一路上说过的要求）、原则、深浅两套颜色、字号（最小 14px）、版式与动效、图片与官方素材、组件表、页面骨架、实现规则
   - 13.3 页头改为不变形的实色条；页脚加「游戏图片版权归暴雪娱乐所有」
   - 5.2 首页改为首屏图、数字条、近期、资讯与公告、战队
   - 12.4.1 新增 `hero_image`；13.13.4 首屏图片修改也刷新首页
   - 19.2 第 8、9 条改写（深浅色跟随系统）；附录 D 加 v4.0
2. **颜色**（`assets/css/input.css` 前半部分重写）
   - 浅色写在 `@theme`，深色写在 `@media (prefers-color-scheme: dark)` 的 `:root` 覆盖同名变量
   - v3 的令牌名（`surface-high`、`primary-deep` 等）做成指向 v4 的 `var()` 别名，087–089 还没重做的页面也跟着换色，深色模式也成立
   - 首屏和图片卡的深底用 `night`、`night-2`，两种模式一样
3. **页头页脚**
   - 页头是 `surface` 实色条，`position: sticky`，不变形、不收起；搜索换成放大镜按钮；「注册」改成主要按钮
   - `static/js/motion.js` 删除；`state.js` 不再加 `js` 类；前台模板去掉 `data-reveal`
   - 站点标志去掉金色小圆点（网站图标、错误页同步）
   - 页脚声明加游戏图片版权
4. **首页**
   - `content/home.py`：`feature_tournament`（截止最早的一场正在报名的赛事）、`scrim_rows`（前 4 场，带报名人数）、`scrims_held`（已结束的内战）；资讯改 4 篇
   - `home_page.html` 重写：`c-hero`（有图 / 没图两种）、`c-stats`、`c-feature`、`c-rows` + `c-date` + `c-meter`、`c-media`、`c-teams`
   - `SiteSettings.hero_image`（迁移 `core/0013`），`core/signals.py` 改它时刷新首页
5. **其他**：错误页样式换 v4 颜色、去掉渐变底，重新生成维护页；样张页的颜色表和首页一节换成 v4 组件；README「视觉风格与首页」重写；AGENTS.md 更新截图方法和深浅色的坑
6. **测试**
   - `core/tests/test_design_system.py`：两种模式各算一遍对比度；深色块漏写颜色会红；v3 名字是别名；没有玻璃和渐变色块；令牌以外不写色值（深色块也算令牌）；页头实色不变形；内容不等脚本；首页网格都是 `minmax(0, …)`；页脚写游戏图片版权
   - `content/tests/test_home_sections.py`：数字条、首屏有图没图、QQ 按钮、大图卡取最早截止、内战前 4 场按开始排、近期的进度、资讯 4 张卡、首屏图片刷新首页
   - `scrims`、`tournaments` 的首页列表测试改指向「近期」区块
7. **本地开发库**：导入用户同意下载的 6 张官方图（首屏、赛事封面、三篇文章封面），只在本地 `media/`，不进仓库；导入前 `manage.py backup` 备份过

## 验证

变异（`handoff/rounds/086-v4-system-home/mutate.py`）：

```
BASELINE 96 passed in 22.44s
KILLED   深色块漏写一个颜色  | 1 failed, 56 passed in 23.02s
KILLED   深色的第三级文字对比度不够  | 1 failed, 59 passed in 24.87s
KILLED   浅色控件边框对比度不够  | 1 failed, 55 passed in 24.94s
KILLED   页头又磨砂  | 1 failed, 5 passed in 5.57s
KILLED   又加渐变色块  | 1 failed, 62 passed in 24.89s
KILLED   首页网格不用 minmax(0  | 1 failed, 69 passed in 25.50s
KILLED   没上传首屏图时不放校徽  | 1 failed, 22 passed in 13.98s
KILLED   QQ 按钮不用图上的白色描边  | 1 failed, 23 passed in 14.55s
KILLED   大图卡取最晚截止的赛事  | 1 failed, 24 passed in 15.10s
KILLED   内战不按开始时间排  | 1 failed, 25 passed in 12.80s
KILLED   累计内战把没打的也算上  | 1 failed, 21 passed in 12.70s
KILLED   改首屏图片不刷新首页  | 1 failed, 34 passed in 18.71s
KILLED   页脚不写游戏图片版权  | 1 failed, 7 passed in 6.33s
KILLED   内容又等脚本才出现  | 1 failed, 6 passed in 5.60s
14/14 killed
```

「页头又磨砂」单独确认过是哪两条测试抓到的：

```
FAILED core/tests/test_design_system.py::test_the_masthead_is_a_plain_bar_that_stays_put
FAILED core/tests/test_design_system.py::test_v4_draws_no_glass_and_no_washes
```

整组检查（Windows 本机，`PYTHONUTF8=1`）：

```
All checks passed!
247 files already formatted
Built production stylesheet '...\static\css\app.css'.
1001 passed in 270.75s (0:04:30)
No changes detected
System check identified no issues (0 silenced).
```

第一次整组跑时 `scrims/tests/test_teaming.py::test_6v6_finishes_within_a_second` 失败过一次（AGENTS.md 记的计时测试，机器繁忙时偶发），上面这次整组跑通过。

视觉（无头 Edge 调试端口截整页）：

- 首页 1440 浅色、深色：首屏图、数字条、近期大图卡和内战列表、资讯四张图片卡、公告、战队、页脚都正常
- 375 宽：`/`、`/news/`、`/tournaments/`、`/scrims/`、`/teams/`、`/members/`、`/news/demo-0/`、`/accounts/login/` 的 `scrollWidth` 都是 375。手机上「3 年 125 天」原来折行，数字条改成手机 1.5rem、桌面 2rem

## 没做的、留给后面的

- 资讯、文章、赛事、内战、战队、成员、个人中心、表单、评论的版式还是 v3 的（靠别名换了颜色），087–089 重做
- 错误页还只有浅色（089）
- 真手机上的深色模式未验证
