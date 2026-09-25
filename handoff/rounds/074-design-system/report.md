# 074 实现报告

## 结论

**完成。** 设计文档升到 v2.0，13.2 节重写成完整的设计体系；样式表从空文件重写；全站外框（页头、手机菜单、页脚、操作提示）、通用组件、图标、站点标志、网站图标、错误页都换成新体系；新增样张页 `/_styleguide/`。

**过渡状态要说清楚**：各页面内部（首页、资讯、赛事、内战、战队、成员、个人中心、登录注册）还是旧模板，065 自定义的那批类（`side-layout`、`member-cards`、`photo-cards` 等）随旧样式表一起删了，所以这些页面在 075–077 改完之前**排版是乱的**（外框正常，内容区没有样式）。daisyUI 的类还能用，因为插件暂时保留。这一轮不部署测试机（本会话也连不上，见下）。

## 逐条结果

| 任务 | 结果 |
|---|---|
| 1 设计先改 | `docs/design.md` v2.0：13.2 节「设计体系」9 小节（参考与取舍、原则、颜色、字体与数字格式、网格形状动效、标志性元素、组件表、页面骨架、实现规则）；13.3 页头页脚；5.2 首页五个区块；文章页；6.3、13.1、13.4（`/_styleguide/`）、13.5、13.6、13.10、13.12.4（`--font-figure`）、13.15、2.2 技术选型表、19.2 第 8/9 条；附录 D |
| 2 样式表重写 | `assets/css/input.css` 全部重写：`@theme` 颜色令牌（关掉 Tailwind 自带色板）、`.on-night` 语境变量（组件在深色区块里自动换色）、13.12 排版设置的全部变量、13.2.7 表里的全部组件 |
| 3 过渡期 daisyUI | 插件保留，主题改名 `ow`、颜色映射到新令牌、圆角全部 0 |
| 4 外框 | `base.html`：深色页头（标志、主导航红线、搜索、账号）、手机上 `<details>` 展开的整屏菜单（导航带编号）、深色页脚（四栏、非官方声明）、跳到正文链接 |
| 5 组件模板 | `icon`（43 个重画）、`brand`、`main_nav`、`account_area`（`<details>` 下拉）、`form_field`、`rank_badge`、`role_icons`、`status_badge`（7 种形状，旧的 kind 名字先映射）、`slots`、`section_head`、`pagination`、`empty_state`、`about_side`、`slots/messages`（提示条 6 秒后淡出，不靠脚本） |
| 6 `--font-figure` | `core/fonts/css.py`：「数字与数据」选了字库字体时同时写 `--font-figure`；按钮区域的选择器加上 `.c-btn` |
| 7 样张页 | `core/styleguide.py` + `core/templates/core/styleguide.html`，14 个区块；权限用 `wagtailadmin.access_admin`（本站后台角色都靠它，`is_staff` 只有超级管理员才有，所以设计里原来写的 `is_staff` 改了）；`robots.txt` 禁止、保留地址片段 |
| 8 网站图标 | `static/img/favicon.svg`，红色切角方块 |
| 9 错误页 | `error.css` 和 5 个模板重写（大号状态码、眉标、主要 / 次要按钮）；`deploy/error_pages/maintenance.html` 重新生成 |
| 10 演示数据 | `seed_demo.py`：30 个演示用户（密码不可用）、6 支战队、3 个分组、10 篇文章（生成的抽象封面）、3 个赛事、5 场内战、评论、3 张焦点图。只在开发库里跑 |

另外新增 `core/templatetags/ow.py`：日期 `2026.09.28`、`09.28`、时间、星期、两位编号、名额格、段位拆分、首字，全站格式只在这一处定。

## 设计是怎么推导的

用户要求参考别的游戏、社区、组织的官网。**本会话的网络策略拦掉了所有游戏官网**（守望先锋、无畏契约、英雄联盟、明日方舟、CS2 等全部 403），能访问的只有 GitHub。调研由两个子任务完成：一个从 GitHub 上保存的官网 HTML/CSS 副本（比如 overfast-api 测试夹具里的守望先锋官网首页、明日方舟官网的复刻仓库）和搜索摘要里取具体数值；另一个调研社区、电竞组织和高校网站。**第二个子任务到本轮提交时还没有返回**，13.2.1 表里 Liquipedia、HLTV、电竞俱乐部、高校和编辑类网站那几行是我按对这些网站的已有了解写的，没有在本会话里核对。

从调研里真正用上的：

- 守望先锋官网：全站 2px 圆角、品牌橙只给按钮和焦点、组件词汇只有三种按钮 → 本站直角、红色只给四处、按钮三种加一个危险操作
- Riot：品牌红几乎只作文字和线条色 → 「红色是信号，不是底色」
- 明日方舟：真实元数据当装饰、`2026 // 09 / 04` 式日期、发丝线分隔的新闻行 → 编号、数字格式、列表行
- 反例：守望先锋官网首页四张一样的亮点卡、补丁说明的彩色左边框——和用户以前否掉的完全一样，所以写进「不学」

推导出的「签名」只有六样（红线、切角、编号、名额格、斜纹、票根），别处不再发明装饰。

## 验收输出

```
$ uv run ruff check . && uv run ruff format --check .
All checks passed!
243 files already formatted

$ uv run python manage.py tailwind build --force
Built production stylesheet '/home/user/sjtu-ow/static/css/app.css'.

$ uv run pytest -q
919 passed in 231.85s (0:03:51)

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ （生产配置）uv run python manage.py check --deploy
System check identified no issues (0 silenced).

$ uv run python manage.py render_error_pages
Wrote /home/user/sjtu-ow/deploy/error_pages/maintenance.html
```

898 → 919（新增 `core/tests/test_design_system.py` 21 条）。`app.css` 136618 字节，gzip 后 23555 字节。

**Docker 镜像构建：未验证**（本会话的容器里没有 Docker 守护进程）。本轮没改 `Dockerfile`。

改了两条旧测试，都是断言旧设计的：

- `test_article_list_pagination_and_category_filter`：分页的当前页现在加粗，`"1 / 2"` 改成 `"<strong>1</strong> / 2"`
- `test_body_text_rules_match_what_wagtail_renders`：原来断言 `.article-body p` 首行缩进、引用用楷体（065 的设计）；改成断言 `.c-prose p` 有段间距、**没有**首行缩进、引用上面有线。「规则不能挂在 `.rich-text` 上」那条保留

## 变异

`handoff/rounds/074-design-system/mutate.py`，每个变异跑 `core/tests/test_design_system.py`，还原后清 `__pycache__`：

```
KILLED   --font-figure 不跟随字库字体  | 1 failed in 0.40s
KILLED   按钮区域的规则不管 c-btn  | 1 failed, 1 passed in 0.48s
KILLED   样张页对所有人开放  | 1 failed, 7 passed in 2.46s
KILLED   样张页只给超级管理员  | 1 failed, 8 passed in 3.02s
KILLED   robots 不禁止样张页  | 1 failed, 9 passed in 3.23s
KILLED   样张页的地址能被页面占用  | 1 failed, 9 passed in 3.37s
KILLED   导航不标当前栏目  | 1 failed, 2 passed in 0.94s
KILLED   手机菜单改成靠脚本的 div  | 1 failed, 3 passed in 1.22s
KILLED   抽屉导航不编号  | 1 failed, 3 passed in 1.23s
KILLED   去掉网站图标  | 1 failed, 4 passed in 1.50s
SURVIVED 页脚不写非官方  | 21 passed in 3.19s
KILLED   账号菜单不用 details  | 1 failed, 6 passed in 2.20s
KILLED   error.css 的红色和令牌不一致  | 1 failed, 20 passed in 3.13s
KILLED   留着 Tailwind 自带的颜色  | 1 failed, 19 passed in 3.19s
KILLED   超出上限不标出来  | 1 failed, 13 passed in 3.22s
KILLED   超过 24 格仍然画方块  | 1 failed, 14 passed in 3.32s
KILLED   时间不换算成上海时间  | 1 failed, 11 passed in 3.27s
KILLED   星期从周日开始数  | 1 failed, 10 passed in 3.35s
KILLED   段位小段不用数字字体  | 1 failed, 18 passed in 3.33s
18/19 killed
```

幸存的一条是**等价变异**：页脚在说明段和最下面一行各写了一次「不是上海交通大学官方网站」，只删最下面一行，规则仍然满足。改成两处都删后重跑：

```
KILLED   页脚不写非官方  | 1 failed, 5 passed in 1.82s
1/1 killed
```

19/19。

## 截图

本地开发库 + `seed_demo.py`，Playwright（容器自带的 Chromium）截 1280 和 390 两种宽度：样张页（登录后）、成员页（看外框）、404。**容器里没有苹方和 DIN**，只有文泉驿，截出来和访客看到的差别很大。所以从 Google Fonts 的 GitHub 仓库下载了 Noto Sans SC、Barlow、Barlow Condensed（都是 OFL，只装在本会话的 `~/.fonts`，不进仓库），再用 fontconfig 在扫描时把它们注册成 `PingFang SC`、`DIN Alternate`、`DIN Condensed`，CSS 里的字体栈就能像在苹果和 Windows 上那样命中。配置写在本报告末尾，以后在 Linux 容器里做视觉工作可以照做。

截图过程中发现并修掉：

- 表格放在网格里会被拉到和旁边一栏一样高，每行被撑成 86px。`c-table` 加 `align-self: start`
- 「交叉双剑」图标画得太乱，删掉（没有地方用）

## 设计偏差

- 13.2.7 的样张页原来写「后台账号（`is_staff`）」：本站的后台角色靠 `wagtailadmin.access_admin` 权限进后台，`is_staff` 只有超级管理员有。设计改成「能进后台的账号」，代码按权限判断
- 13.2.7 抽屉原来写「纯 CSS（复选框）」：复选框加 `<label>` 的写法键盘用户聚焦不到可见元素，改成 `<details>`（本来就是 `AGENTS.md` 推荐的写法），设计同步改了
- 13.13.3 表里账号区域那一行（「昵称和下拉菜单；是否显示『投稿』按钮」）没动：下拉菜单现在有了，「投稿」按钮从来没有放在账号区域里，这句是旧的，留给 078 一起清

## 未完成 / 顺带发现 / 需要确认

- **CI 没跑**：本会话被要求推到分支 `claude/nifty-planck-i1qe4u`，而 CI 只在推到 `main` 和合并请求时跑（`AGENTS.md` 规定直接推 `main`，两边冲突，我按会话的要求推分支）。上面的整组检查都在本地跑过；合进 `main` 后要看一眼 CI
- **测试机没部署**：本会话没有 SSH 密钥（在开发者本机），部署留给 078，要用户那边做或给权限
- `content.models.RESERVED_CHILD_SLUGS` 里没有 `search`：071 加了 `/search/` 路由，但首页下面仍然能建网址片段为 `search` 的页面，建了会被搜索页盖住。本轮只加了 `_styleguide`，`search` 留给 078
- `templates/core/home.html` 是 M0 的首页占位，065 就说没人用，还在
- 旧的 `static/js/carousel.js` 还是 065 的轮播，075 重写成焦点图

## 截图环境（fontconfig）

```xml
<!-- ~/.config/fontconfig/fonts.conf：把开源字体注册成访客设备上的字体名 -->
<match target="scan">
  <test name="family"><string>Noto Sans SC</string></test>
  <edit name="family" mode="assign" binding="same"><string>PingFang SC</string></edit>
</match>
<match target="scan">
  <test name="family"><string>Barlow Condensed</string></test>
  <edit name="family" mode="assign" binding="same"><string>DIN Condensed</string></edit>
</match>
<match target="scan">
  <test name="family"><string>Barlow</string></test>
  <edit name="family" mode="assign" binding="same"><string>DIN Alternate</string></edit>
</match>
```

字体从 `https://raw.githubusercontent.com/google/fonts/main/ofl/...` 下载（`github.com` 本身被本会话的代理按仓库限制了）。Tailwind 编译器也是用 curl 加代理证书下载的：Python 3.13 的严格证书校验不接受代理的 CA，`tailwind download_cli` 失败。

## 改动文件

```
docs/design.md                                   v2.0
assets/css/input.css                             重写
static/css/error.css、static/img/favicon.svg
templates/base.html
templates/components/{icon,brand,main_nav,account_area,form_field,rank_badge,role_icons,status_badge,slots,section_head,pagination,empty_state,about_side}.html
templates/slots/{account,messages}.html
templates/errors/{base,403,404,429,500,maintenance}.html
deploy/error_pages/maintenance.html
core/templatetags/{__init__,ow}.py               新建
core/styleguide.py、core/templates/core/styleguide.html、core/urls.py
core/fonts/css.py                                --font-figure、.c-btn
content/models.py（保留地址）、content/views.py（robots）
core/tests/test_design_system.py                 新建
content/tests/test_content.py、content/tests/test_home_sections.py   两条断言按新设计改
README.md、AGENTS.md、handoff/STATUS.md
handoff/rounds/074-design-system/{request,report,review}.md、seed_demo.py、mutate.py
```
