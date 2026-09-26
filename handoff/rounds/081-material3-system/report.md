# 081 实现报告

## 结论

完成。设计文档升到 v3.0，全站的令牌、组件、页头页脚、错误页、样张页换成 Material 3；首页和各页的版式留给 082 起的几轮。

## 逐条结果

### 1. 设计文档 v3.0

- 13.2 节整节重写：参考与取舍（Android 开发者站、AOSP 站、Material 3、玻璃拟态、高校官网；用户否掉过的六种）、九条原则、以交大红为种子色的色彩角色表和对比度组合表、字号对应 Material 3 等级、圆角 / 阴影 / 磨砂材质 / 三条缓动、标志性元素（校徽水印、磨砂顶栏、色彩渐变底、指示条、关键数字条、色调磁贴、名额格、进度条）、组件表（新增 `c-card`、`c-hero`、`c-quick`、`c-figures`、`c-agenda`，按钮新增 `--tonal`）、页面骨架、实现规则（校徽的来源和范围、`<progress>` 代替写宽度的 div、`motion.js`）
- 13.3 节：页头四种状态的表（整条、胶囊、收起、弹出）；浅色抽屉和页脚；账号区域
- 5.2 节首页改为 M 版；5.4 节投稿入口位置；12.4.1 新增 `founded_on`、`qq_group_url`；12.5.1 焦点图子表删除（082 实现）；13.5 个人中心的当前项；13.12.4 `--font-figure` 默认值；13.13.4 三行事件补上首页（内战报名、报名通过、邮箱验证会改首页上的数字），新增「社区成立日期、QQ 群链接修改 → 首页」；附录 C 首页参数；19.2 第 8、9 条；附录 D v3.0
- 核对：13.2 以外还提到 v2.0 视觉的地方（编号菜单、DIN 字体、「参与」区块）逐个改了

### 2. 令牌与对比度

`@theme` 换成 Material 3 的角色：`primary` / `primary-deep` / `primary-container` / `on-primary-container`、`tertiary-container`、六级 `surface`、三级 `on-surface`、`outline` / `outline-variant`、反色三个（提示条）、三种状态各带容器色、六种磁贴色和五种图标片色；圆角 `--radius-xs`…`--radius-xl`、`--radius-full`；阴影三级；缓动 `--ease-standard`、`--ease-emphasized`、`--ease-spring`（`linear()` 弹簧，不支持时退回贝塞尔）。

动笔前先算了一遍对比度：正文 13.3–16.4，第三级文字在最深的表面上 5.30，控件边框在最深的表面上 3.65，磁贴上的白色图标最低 5.79。对比度测试按设计新表逐对计算。

**半透明色**：一开始写了 11 处 `rgb(...)`（磨砂底、悬停底、阴影），测试只查十六进制所以漏过。全部改成 `color-mix(in oklab, var(--color-…) N%, transparent)`，测试加了 `rgb()` / `hsl()` 的扫描，设计 13.2.3 写明。

### 3. 深色区块改色调区块

模板里 `on-night` 11 处、`c-pagehead--night` 6 处改成 `on-tonal`、`c-pagehead--tonal`；写死的旧令牌类 5 处（`bg-sunken`、`border-line`）换掉。`.on-tonal` 只换底色（`surface-mid`），文字不翻转。

### 4. 组件

`input.css` 保留全部类名，重写样式：按钮胶囊（实心、色调、描边、文字）；标签 8px 圆角；状态改为色调小标签；表单 12px 圆角、聚焦 2px 主色边；复选框和单选主色；位置选择块改筛选标签式；提示改色调条；提示条改反色；空状态、面板、卡片、票根、表格、名片、图块改圆角描边卡片；筛选标签条改胶囊式；侧栏菜单改 Material 导航项；正文引用改色调块；评论置顶改色调底。切角（`clip-path`）、斜纹、发丝线框全部去掉。图标改圆头圆角。

### 5. 页头

`<header class="c-masthead" data-masthead>`，粘性定位；整条和胶囊都是 64px 占位（胶囊 52px 高 + 12px 离顶），变形时下面不跳。`static/js/motion.js`：80px 以下整条；超过变胶囊；继续往下超过 6px 在变形结束（320ms）后收起；往上超过 6px 弹出；焦点在页头里不收起；「减少动态效果」下不等变形。搜索框加「/」提示，按 `/` 聚焦（输入框里不触发）。

### 6. 校徽

`static/img/sjtu-emblem.svg`：用户确认的文件，`viewBox` 从 A4 裁到 `167.84 146.61 283.5 283.51`（先在浏览器里用 `getBBox` 量出 52 条路径的外框），图形未改。扫描：没有脚本、事件属性、外部链接、嵌入图片（唯一的命中是 XML 声明里的 `standalone=`）。`THIRD_PARTY_NOTICES.md` 登记来源、权利归属和使用范围。

### 7. 其他

- 站点标志换成样稿里的圆角方块（`components/brand.html`、`favicon.svg`、错误页）；去掉「SJTU OVERWATCH COMMUNITY」小字
- 错误页样式表 `static/css/error.css` 重写，`render_error_pages` 重新生成 `deploy/error_pages/maintenance.html`
- 样张页色块换成新令牌（37 个），说明文字改成新元素，加色调按钮
- **滚动出现的兜底**：`state.js` 在 `<head>` 里加 `js` 类（避免闪烁），内容在 `.js` 下先藏起来等 `motion.js`。写复核指南时想到 `motion.js` 加载失败会让内容永远藏着，加了 3 秒兜底：`motion.js` 没报到（`motion-ready`）就撤掉 `js`
- 本地开发库造了一批示例数据（12 个用户、6 支战队、2 场赛事、6 场内战、6 篇文章）方便看版式；脚本在会话临时目录，没进仓库。造数据前用 `manage.py backup` 备份过

## 验收输出

```
== ruff
All checks passed!
244 files already formatted
== tailwind
Built production stylesheet 'C:\Users\fyc12\Desktop\Claudee\sjtu-ow\static\css\app.css'.
== pytest
960 passed in 179.26s (0:02:59)
== makemigrations
No changes detected
== check --deploy
System check identified no issues (0 silenced).
```

（ruff 第一遍报了 5 处行太长，缩短后 `All checks passed!`；之后加了兜底和一条断言，设计体系测试 `43 passed`，全量在提交前重跑，见 review.md。）

变异（`handoff/rounds/081-material3-system/mutate.py`）：

```
KILLED   第三级文字调得太浅（不到 4.5）  | 1 failed, 25 passed in 7.65s
KILLED   控件边框用回装饰线的颜色（不到 3）  | 1 failed, 25 passed in 7.22s
KILLED   图标片颜色太浅，白色图标看不清  | 1 failed, 27 passed in 7.43s
KILLED   提示条的字和底对比不够  | 1 failed, 27 passed in 7.03s
KILLED   令牌以外写 rgb() 半透明色  | 1 failed, 30 passed in 7.91s
KILLED   色调区块把文字翻成浅色  | 1 failed, 29 passed in 6.59s
KILLED   页头换回不透明的实底  | 1 failed, 5 passed in 3.09s
KILLED   胶囊不是圆角  | 1 failed, 5 passed in 3.28s
KILLED   收起时不移出屏幕  | 1 failed, 5 passed in 3.06s
KILLED   滚动出现不看 .js 就隐藏内容  | 1 failed, 35 passed in 5.73s
KILLED   js 类放到提前返回之后  | 1 failed, 35 passed in 4.21s
KILLED   motion.js 没来时不撤掉 .js（内容一直藏着）  | 1 failed, 35 passed in 3.12s
KILLED   收起时不顾键盘焦点  | 1 failed, 5 passed in 1.85s
KILLED   页头没有接上 motion.js  | 1 failed, 5 passed in 1.74s
KILLED   抽屉导航又带编号  | 1 failed, 3 passed in 1.31s
KILLED   校徽文件回到整页 A4 画布  | 1 failed, 36 passed in 3.12s
KILLED   第三方声明漏登记校徽  | 1 failed, 36 passed in 5.70s
KILLED   错误页的主色和站点不一致  | 1 failed, 25 passed in 7.04s
KILLED   样张页色块还写旧值  | 1 failed, 28 passed in 5.48s
19/19 killed
```

浏览器里（开发服务器，1280×800）模拟一组滚动，逐步读页头的类：

```
初始        cap false  hide false  y 0
下滚 300    cap true   hide false  y 300
等 400ms    cap true   hide true   y 300
上滚 20     cap true   hide false  y 280
下滚到 900  cap true   hide true   y 900
回顶        cap false  hide false  y 0
按 / 后聚焦搜索框  true
```

关掉过渡后读到的最终样式：整条 64px、直角、满宽；胶囊 52px、离顶 12px、宽 1100px、圆角 999px、磨砂 `saturate(1.8) blur(20px)`；收起 `translateY(-76px)`。手机（375×812）下首页、文章、赛事详情、内战详情、战队主页、成员、注册、搜索 8 页都没有横向溢出（`scrollWidth` 375）；抽屉打开后是浅色面板，10 个链接，当前项标出。

## 设计偏差

- 顶栏搜索框用 Material 3 的填充式搜索栏，没有 3:1 边框。设计 13.2.3 写成了例外（靠图标、占位文字和「/」提示认出来），测试不再要求它
- 首页、成员、登录页模板里还有 v2.0 写死的工具类（「近期」下的 2px 深色线、「注册以后可以」上的粗线、成员页「共 N 位成员」的间距）。这些是页面版式的事，按计划在 082 起的几轮改

## 未完成 / 顺带发现 / 需要确认

- 首页版式（M 版）、`founded_on`、`qq_group_url`、删除焦点图：082
- 赛事、内战、战队、成员、资讯、文章、搜索、个人中心、表单的版式：083 起
- **动效的真实观感没看过**：浏览器面板在后台不渲染动画帧，只验证了状态；缓动和回弹要在真浏览器里看
- **需要你提供**：社区成立日期（082 首页「社区已成立」用）、QQ 群链接
- 示例数据里内战的时间按 UTC 设了钟点，显示成凌晨，只影响本地开发库

## 改动文件

- 设计与文档：`docs/design.md`、`README.md`、`THIRD_PARTY_NOTICES.md`
- 样式与脚本：`assets/css/input.css`（重写）、`static/css/error.css`（重写）、`static/js/motion.js`（新）、`static/js/state.js`
- 资源：`static/img/sjtu-emblem.svg`（新）、`static/img/favicon.svg`
- 模板：`templates/base.html`、`templates/components/{brand,icon,main_nav,section_head,account_area}.html`、`templates/errors/base.html`、赛事 / 内战 / 战队的列表和详情页头、首页色调区块、文章封面和视频块、样张页
- 其他：`core/styleguide.py`、`deploy/error_pages/maintenance.html`
- 测试：`core/tests/test_design_system.py`、`content/tests/test_home_sections.py`
