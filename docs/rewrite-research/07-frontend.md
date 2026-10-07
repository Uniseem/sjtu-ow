# 07 · 前端体系（Vue3 复刻清单）

来源：前端调研代理。基线 `ec44ae4`。技术栈：Django 模板 + django-htmx + Tailwind CSS 4.3.2（django-tailwind-cli 编译，assets/css/input.css → static/css/app.css）+ HTMX 2.0.10 + Alpine CSP 3.17.1 + SortableJS 1.15.6 + EasyMDE 2.21.0 全部自托管。

## ① 布局与组件

### 基础布局（templates/ 根）
| 布局 | 位置 | 说明 |
|---|---|---|
| 前台 base | `templates/base.html` | head 顺序极重要：theme.js → arrival.js → tailwind css → 可选 font_css_url → state.js → speculation rules（base.html:23-28）。body：跳正文链接、测试环境横幅、微信提示横幅、c-masthead（品牌/主导航/搜索框≥1280px/主题菜单/账号槽/手机抽屉/加载条 c-loadbar）、slots/messages、main、c-footer（社区/参与/账号槽/关于四栏）。尾部脚本：htmx → alpine.csp(defer) → app.js → loading.js → contextmenu.js → autosave.js → 块级 extra_js（:145-151）。data-state-filled 标记本页登录态是否已由 Django 填好 |
| 个人中心 | `templates/me/base.html` | pagehead + l-container--narrow + 双栏（c-sidenav 桌面 / c-tabs 手机）+ 未补全提示 + 发信提示。仅实时渲染，绝不预渲染 |
| 账号（allauth） | `templates/account/layout.html`、`templates/allauth/layouts/{base,entrance,manage}.html` | 一列窄表单 c-auth + 侧栏 c-why（为何要这些信息） |
| 管理后台 | `backoffice/templates/backoffice/base.html` | 自有 b-* 布局（深色顶栏 b-top、b-head 面包屑/标题/标签 b-tabs、b-main），theme.js + tailwind + backoffice.js + autosave.js，内置图片选择 <dialog data-image-dialog> 和编辑器图标 sprite。不加载 htmx/alpine |
| Wagtail 底层后台 | `templates/wagtailadmin/{admin_base,base}.html` | 仅品牌覆盖，配 static/css/admin.css（把站点令牌拷成 --sj-* 再映射 Wagtail 的 --w-color-*） |
| 错误页 | `templates/errors/base.html` + 403/404/429/500/maintenance | 完全独立：不用 app.css、无 JS，仅 static/css/error.css；令牌手工同步并有测试盯住 |

### 组件模板（templates/components/，22 个）
account_area（登录后 details 账号菜单，含"管理后台"入口）、avatar（真人头像/默认头像池/首字底图三档降级，size xs-sm-md-lg，c-hue-N 底色）、brand（红底白 chevron 站标 SVG）、empty_state、form_field（c-field 三分支：单选框/多选组/普通，帮助文字+首条错误 role=alert）、icon（全部 45+ 图标为内联 SVG path，24×24、1.75 描边，无图标库）、main_nav（按路径前缀标 aria-current，可缓存）、pagehead_picture（栏目横幅，昼/夜两套 c-scene）、pagination、play_style（位置+段位，180 天过期变灰 is-stale）、post_card（c-media 文章卡）、profile_gap_links、rank_badge、registration_status、role_icons（坦/输/援自制字形）、scrim_row（c-row + c-date + c-seats）、seats（格子席位 role=img）、section_head、speculation_rules（JSON 预渲染规则，排除 admin/wagtail/accounts/me/_fragments/_styleguide 及 download/target/data-no-prerender）、status_badge（live/ok/warn/info/done/off/rejected）、team_tile、tournament_card（阶段驱动的状态+日期文案）。

### 个性化槽位（预渲染页登录态体系，设计 13.13.3）
模板：templates/slots/{account,agenda,footer_account,messages}.html，带 data-slot + oob 开关。注册：core/apps.py（account/messages/footer-account/my-agenda）、comments/apps.py（article-comments:页id）、teams/apps.py（team-join:队id）、scrims/apps.py、tournaments/apps.py。注册表 core/slots.py（最多 12 个，name:参数 语法）。接口 GET /_fragments/state/?slots=… 返回 oob 片段，HTMX swap:"none" 换入。详见 08。

## ② c-*/l-* 组件与设计令牌（assets/css/input.css，5957 行）

### 令牌体系
- **Tailwind 色板整体关闭**：@theme 内 --color-*: initial（input.css:27）。模板只准用语义名。
- **语义色（浅色）**：底面 bg / surface / surface-2 / line / control；文字 fg / fg-2 / fg-3；品牌砖红 primary / primary-hover / primary-text / primary-soft / on-primary-soft；守望橙 accent / accent-text（小字 4.5:1）/ accent-display（大字 3:1）/ accent-soft / on-accent-soft；状态 ok(-soft) / warn(-soft) / info(-soft)；Toast toast / on-toast；**夜带专用** night / night-2 / night-accent / night-surface / night-line / night-control / night-fg(-2/-3) / night-primary-* 等（页脚和带封面的 stage 两模式恒深色——在带内把全部语义变量重绑定为 night 值，input.css:426-445。Vue 里要保留这个"局部变量域"技巧）。
- **深浅色机制**：@custom-variant dark（input.css:106-116）= prefers-color-scheme: dark 且没有 data-theme="light"，或 data-theme="dark"。深色值在 :root { @variant dark { 同一批变量名重赋值 } }（:119-149）。theme.js 在 head 内、首帧前写 data-theme。
- **其它令牌**：radius xs4/sm8/md12/lg16/full；阴影只有 --shadow-float；缓动全是同一条 cubic-bezier(0.2,0,0,1)；容器 --container-page: 120rem、--container-prose: 44rem。
- **排版变量**（:157-205）：--font-body/-h1..h4/-nav/-button/-numeric/-code/-figure；回退栈 -apple-system…PingFang SC…微软雅黑…；手机标题 85%。可被"排版设置"生成的 fonts.<hash>.css 整体覆盖。
- 工具字体类：.font-nav/.font-button/.font-numeric(tabular-nums)/.font-code/.font-figure。

### l-* 布局（:449-521）
l-container（120rem）、l-container--narrow（80rem）、l-section、l-split（主列+20rem 侧栏）、l-prose（44rem）。

### c-* 组件完整清单（按 input.css 顺序）
- 系统级：c-cut、c-hatch（无图占位灰块）、c-stretch（整卡可点伪元素）、c-eyebrow、c-figure（大数字）。
- 页头/导航：c-masthead（sticky、独立 view-transition-name :561-568）、c-loadbar、c-brand、c-nav、c-masthead__search/__end/__find、c-iconbtn、c-account、c-menu（details 下拉）、c-theme、c-drawer（手机抽屉，纯 details）。
- 右键菜单：c-ctxmenu / __item / __foot / c-ctxmenu-toast（:947-1013）。
- 场景：c-scene--light / c-scene--dark（昼/夜两份按模式显隐 :1016-1028）。
- 页脚/横幅/面包屑：c-footer（夜带+四栏）、c-banner（--test / --hint）、c-crumbs。
- 页头：c-pagehead / --picture（渐隐蒙版 + 底部双山脊 :1291-1352）/ __img/__row/__lede/__meta/__actions；c-sectionhead。
- 操作件：c-btn（--primary/--danger/--tonal/--quiet/--light/--sm/--block :1420-1530）、c-link。
- 容器：c-card、c-panel__head/__actions、c-tag（--accent/--strong）、c-status（--live 脉动/--ok/--warn/--info/--rejected :1607-1664）。
- 游戏语义：c-seats、c-rank / c-rank__div、c-roles/c-role（--main 实心其它描边）、c-play/c-play__rank（is-stale 变灰）、c-stat。
- 数据：c-facts（键值资料）、c-table（:1834-1922，align-self: start 防网格拉高）。
- 人物：c-avatar（--xs/--sm/--md/--lg）+ c-hue-1..5、c-people、c-group、c-person（名片）、c-squad__item。
- 表单：c-field（is-invalid 变红边+红底 :2366-2374）、c-autosave（data-state=saving/saved/partial/failed 变色 :2223-2232）、c-input（44px 控件、select 自绘箭头）、c-faces（头像九宫格）、c-choices/c-choice（单选卡）、c-form、c-step、c-formbar、c-auth（登录双栏）、c-why。
- 反馈：c-notice（--info/--ok/--warn/--error）、c-toasts/c-toast（:2660-2700）、c-empty、c-pager、c-tabs（横滚 + __count，app.js 滚到当前项）、c-sidenav。
- 正文：c-prose（:2845-3032，Markdown 渲染目标，含 c-prose__video B 站 iframe 与 c-prose__table）。
- 评论：c-comments（__head/__sort/__list）、c-composer、c-comment（--reply 缩进、__placeholder、__meta、__name、__body、__at、__actions、__thread）、c-act（小动作按钮）。
- 首页：c-hero（全屏首屏 + 双向渐变蒙版 :3277-3345、__emblem 齿轮、__title 两行第二行橙色、__lede、__actions、__foot）、c-stats、c-upcoming（--two 大卡+列表）、c-feature（大图卡 hover 微缩放）、c-media-grid（--two）、c-rows/c-row（+__title/__meta/--plain/__text）、c-date（月/日方块）、c-homegrid、c-media（图片卡 + c-drift 漂移）、c-teams（--six/--list 等）。
- 详情页：c-stage（赛场横幅，夜带+山脊，--plain 无图版）、c-cover、c-reading（--toc 双栏）、c-toc（--fold / --side）、c-author、c-sequel（上下篇）、c-article、c-searchbar、c-rolestats、c-roster、c-alumni、c-more、c-swatch。
- 后台专用层（同文件后半 ~:4860-5500）：b-top/b-brand/b-nav/b-head/b-tabs/b-subtabs/b-main/b-form/b-filters/b-check/b-actions/b-dialog/b-people…（backoffice 用 b- 前缀复用同一令牌体系）。

### static/css/ 其它三个
| 文件 | 职责 |
|---|---|
| admin.css | Wagtail 底层后台专用：令牌拷成 --sj-*（浅/深）再映射 Wagtail --w-color-*；有测试保证与 input.css 同步 |
| markdown-editor.css | EasyMDE 皮肤，全部选择器以 .md-field 开头压过 EasyMDE 自带样式；含 md-help、md-preview、md-words |
| error.css | 错误/维护页独立手写样式（无依赖、无 JS），令牌手工拷贝有测试盯住；maintenance.html 把它整个内联 |
| app.css | Tailwind 编译产物（压缩单行），不是手写文件 |

## ③ static/js/ 12 个文件职责表

| 文件 | 职责 | 依赖的后端 |
|---|---|---|
| app.js（103 行） | 微信 UA 提示横幅；.c-tabs 滚到当前项；页头所有 details 下拉互斥关闭+外点关闭+Esc；data-confirm 提交确认；HTMX 配置 allowEval=false、从 cookie 读 csrftoken 加 X-CSRFToken 头 | 所有前台页 |
| state.js（70 行，head 内联） | 预渲染页登录态补齐：无 ow_logged_in/ow_flash cookie 完全不发请求；有则收集 [data-slot] 请求 /_fragments/state/，oob 换入；data-state-filled=1 直接撤骨架；429/5xx/断网兜底；8 秒强制撤；Speculation Rules 预渲染页等 prerenderingchange | GET /_fragments/state/ |
| loading.js（131 行） | 页面切换加载条：150ms 内不出现，sessionStorage ow-loading 跨页传递进度，15s 兜底，bfcache 恢复即停 | 纯前端 |
| arrival.js（35 行，head 内） | 新页读 ow-loading（20s 新鲜度），加载条从上一页进度冲满再淡出 | 纯前端 |
| theme.js（124 行，head 首脚本） | 深浅色：localStorage ow-theme；首帧前设 data-theme 防闪烁；storage 事件跨标签同步；meta theme-color 回写；View Transition 240ms 交叉淡化；减动效直接切；菜单初始 hidden 脚本可用才显示 | 无后端 |
| contextmenu.js（243 行） | 全站自定义右键菜单：仅 (pointer:fine)；Shift+右键/表单区/触摸放行原生；链接/图片/选中文字分组项 + 后退前进刷新复制回到顶部；clipboard + execCommand 兜底；完整键盘导航；滚动/缩放/失焦/htmx 请求前自动关 | /search/、history |
| autosave.js（509 行） | 改了就自动保存（详见 08 契约） | 所有 data-autosave 表单 |
| backoffice.js（317 行） | 后台：data-confirm、data-autosubmit、data-select-all、data-inline 表单 fetch 提交 JSON {replace} 换块、搜人即输即查（250ms 防抖）、选图对话框（fetch 选图器 + 上传 + dispatchEvent change）、data-chooser-nav | 后台选图器、搜人接口 |
| markdown-editor.js（288 行） | EasyMDE 初始化：预览服务端渲染（200ms 防抖 + 序列号防乱序）；图片上传；中文字数统计；B 站视频插入；图标用后台 sprite；工具栏中文 title；codemirror change→textarea input 事件桥给 autosave；IntersectionObserver 处理隐藏面板 | markdown 预览/上传接口 |
| typography-preview.js（108 行） | 排版设置页实时预览（CSS 变量写入预览盒） | 仅该页 |
| scrim-split.js（282 行） | 内战分队板：勾人区计数、SortableJS 拖拽 A/B 队+位置区+缓冲区、满队拒收、每次拖动触发 change 让 autosave 存整板、复制结果按钮、ow:replaced 重接 | split 页 autosave 接口 |
| tournament-teams.js（142 行） | 赛事编队板（从 scrim-split 派生）：池+多队 zone（capacity/min）、满队拒收、data-blocked 卡死在池里、低于下限标 is-under、data-move 键盘路径 | 编队页 |

static/vendor/：htmx 2.0.10、alpine.csp 3.17.1、Sortable 1.15.6、easymde 2.21.0。README 明言"self-hosted; pages never load a third-party CDN"。

## ④ HTMX / Alpine 使用模式

**HTMX 四类用法（很克制）**：
1. 登录态补齐：state.js htmx.ajax(swap:"none") + 服务端 oob 片段。唯一的 oob 换页用法。
2. 评论全局部刷新：所有动作 hx-post，统一 hx-target="#slot-article-comments" hx-swap="outerHTML" 返回整个评论区；「加载更多」hx-get beforeend + oob 隐藏自己。
3. 个人中心行内编辑：hx-get 编辑表单进目标行 outerHTML、新建 innerHTML、删除刷新列表。
4. CSRF/配置：app.js 统一在 htmx:configRequest 加 X-CSRFToken 头，allowEval=false。

**Alpine 实况：每页都加载但全仓库 0 个 x-* 指令。** CSP 版不执行属性表达式，站内小交互走两条路：①原生 <details>（主题菜单、账号菜单、手机抽屉、修改报名、折叠目录）；②外部 JS 文件里的普通监听器。**Vue 重构时 Alpine 直接去掉。**

## ⑤ Vue 重构要专门注意的视觉与无障碍细节

### 深浅色
- 三态模型：跟随系统/浅/深，localStorage ow-theme，首帧前应用避免闪烁（theme.js 逻辑必须保留在样式加载前或 Vue 挂载前同步执行）。
- 语义变量是唯一配色通道；深色 = 同名变量整体重赋值，Vue 里继续用 CSS 变量域而非 Tailwind dark: 工具类堆叠。
- 夜带：c-footer 与带封面的 c-stage 两模式都深色（变量域内重绑）；--page-bg 保证夜带内山脊颜色跟页面。
- 切换整页 240ms View Transition 交叉淡化，减动效直接切。meta theme-color 双 media + JS 回写。

### 动效偏好（全站尊重 prefers-reduced-motion）
- 全局熔断：@media (prefers-reduced-motion: reduce) 把所有动画/过渡压到 0.01ms（input.css:336-346）——Vue 的过渡动画也要被同样机制覆盖。
- 换页 @view-transition { navigation: auto } 150ms 交叉淡化仅 no-preference；masthead 和加载条有独立 view-transition-name 不参与淡化。
- 加载条节奏：150ms 内不出现 → 15s ease-out 爬到 0.95 → 到页 300ms 冲满 + 250ms 淡出，进度跨页经 sessionStorage 传递。

### 标志性视觉（必须复刻）
- 首页首屏：全屏 hero 双向渐变蒙版、两行大标题（第二行 accent-display 橙）、右侧交大校徽双层 mask（本体 20% + 齿轮 primary 55%），齿轮 90s 一圈慢转（图层 static/img/sjtu-emblem-{body,gear}.svg）。
- 双山脊漂移：页头/赛场横幅底部两层 mask 山脊 120s 无缝循环，近脊快一倍（horizon-{far,near}.svg）；邮件头 PNG 是同一地平线的 Pillow 版。
- 占位图动画：按对象稳定挑选的 SVG 场景（keyframes 写在 SVG 内部，只有 transform/opacity，无脚本）；卡片默认封面 c-drift 四种缓慢漂移。
- 昼/夜两套栏目场景按模式显隐。
- 右键菜单体系及"按住 Shift 用原生菜单"惯例。

### 字体
默认全系统回退栈；可运营位"排版设置"上传 TTF → fonttools 切片 → fonts.<hash>.css 覆盖 9 个区域的 --font-* 变量 → base.html 注入。woff2 自托管，font-src 仅 self。Vue 版要么保留这套变量覆盖机制，要么把生成 CSS 的加载位留出来。

### CSP（重构红线）
- 前台策略 SECURE_CSP：default-src 'self'；**script-src 仅 'self' + 'inline-speculation-rules'（无 nonce、无 unsafe-inline/unsafe-eval）**；style/img/font/connect-src 全 self（img 加 data:）；frame-src self + 唯一外域 https://player.bilibili.com；frame-ancestors 'none'；base-uri/form-action self。
- 测试锁死：script-src 集合精确断言、真实页面无内联 script 体、模板禁 on*= 内联事件。**Vue 产物必须同构：无内联脚本/样式、无 JSONP、无外链 CDN；Vue 用 runtime-only 构建（无模板编译器）。**
- 后台单独放宽：ADMIN_CSP 允许 unsafe-inline/eval（仅 /admin/ 与 /wagtail/）；邮件样张页 EMAIL_CSP 只放开 style unsafe-inline。
- **体积预算**：首页全部 CSS+JS gzip ≤ 300KB 的测试——引入 Vue 运行时后这个预算要重谈，是重构硬约束之一。

### 其它无障碍/行为细节
跳正文链接；:focus-visible 2px primary 描边；控件 44px 最小高度；:selection 砖红柔色；评论区/表单错误 role=alert/status；toast aria-live=polite；头像 aria-hidden；data-confirm 全站删除确认约定；autosave 的 beforeunload 提示；Speculation Rules 预取仅公共页；微信内建浏览器提示横幅。

### 样张与邮件（供 Vue 版组件对照）
- /_styleguide/：17+ 节组件样张（颜色/字体/标志/按钮/标签状态段位位置/图标/列表行/表格/图块名片/表单/反馈空态分页/正文/夜带横幅/面板链接单选/首页组件/评论/占位图），仅管理员可见。
- /_styleguide/emails/：34 种邮件样张，每封 iframe 按原样渲染（EMAIL_CSP）。
- 邮件布局 templates/email/layout.html：纯内联样式 + table、SJTU 红头（#9b3a33）+ 站标 + 双山脊 PNG（cid:ow-mark、cid:ow-horizon）+ 白卡 + 灰脚；强制 light；parts：button/code/facts，另有 plain 纯文本版。
