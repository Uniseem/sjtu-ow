# 065 实现报告

## 结论

**完成。** 前台风格照上海交大官网做：交大红、米色、宋体、直角、只做浅色。首页照官网首页的版式重做（焦点图轮播、图片新闻、要闻和通知、赛事卡片和内战日历、战队、快速入口）；资讯、文章、普通页面照官网内页和交大新闻网的文章页改。测试机已部署，放了 7 张 CC0 真实图片做示例内容。

**顺带修了一个从 M2 起就存在的 bug**：文章正文的样式规则全部挂在 `.rich-text` 上，但 Wagtail 渲染富文本时不加这个类，所以文章、赛事说明、用户协议和隐私政策的段落间距、列表圆点、链接颜色**一直没生效**。

## 过程（用户的几次否决）

| 版本 | 用户意见 | 结论 |
|---|---|---|
| HeroUI 样式包 + 深红主题的三页原型（没进仓库） | 「太不正式了，不能用 HeroUI」 | 放弃，改照交大官网 |
| 交大风格第一版：红页头、米色横幅加两个按钮、2×2 区块 | 「AI 味还是很重，特别是首页」 | 横幅加两个按钮、四个一样的区块是落地页套路 |
| 第二版：不对称门户布局 | 「AI 味更重了，就不能模仿交大官网吗，包括图片滚动」 | 照官网首页逐区块对应 |
| 文章页摘要框（红色左边框 + 底色） | 「引用有点 AI 味」 | 去掉摘要框；引用改用楷体 |

教训：**「参考某个网站」时先把对方页面完整看一遍再动手**。官网首页用了整页滚动插件，普通截图下面全是空白，我前两版只看了页头和内页；第三版把视口拉到整页高度才看到完整结构（焦点图、图片新闻、学术卡片 + 日历、拱形专栏、快速入口、条纹页脚），照着做了才过。

## 设计（v1.5.16）

- 13.2 节重写：风格、颜色、字体、只做浅色、**不用交大的校徽、书法校名和照片**
- 5.2 节：首页区块照官网；置顶文章由「覆盖最新文章」改为「排在最前」；文章页不显示摘要，引用用楷体
- 12.5.1 节：新增 `HomePageCarouselItem`
- 13.3 节：页头页脚按新版式；13.13.4 节：战队变化也刷新首页
- 19.2 第 8、9 条结案

## 实现

| 部分 | 内容 |
|---|---|
| 主题 | `assets/css/input.css`：关掉 daisyUI 内置主题，自定义主题 `sjtu`（交大红 `#B2141A`、米色 `#F8F2EA`、圆角 0.125–0.25rem、无阴影）；默认字体改成宋体；`--sj-*` 几个官网首页的装饰色 |
| 页头页脚 | 深红顶栏（账号区域）；红色页头：自己设计的印章标志「交大守望」（从右列读起）、常用入口、细白框主导航，当前栏目高亮（`components/main_nav.html`）；米色条纹页脚，中间写明不是官方网站 |
| 首页 | `content/home.py` 取数据；模板照官网：红色延伸到焦点图后面、图片新闻 4 张、社区要闻 / 赛事通知、赛事卡片一行 3 张 + 内战日历、拱形战队卡片、快速入口 |
| 焦点图 | 首页子表 `HomePageCarouselItem`（迁移 `content.0003`），后台「页面 → 首页」里维护，最多 6 张；链接只能以 `/` 或 `https://` 开头；链接的页面没发布时用填写的地址；一张都没有时用最近 5 篇带封面的文章 |
| 轮播脚本 | `static/js/carousel.js`，外部文件（Alpine 是 CSP 构建，属性里不能写表达式）；5 秒一张，鼠标悬停、键盘聚焦、切到后台、系统设了「减少动态效果」时停；圆点可点；隐藏的幻灯片里的链接不能 Tab 到 |
| 内页 | 资讯列表、文章页、普通页面：左边米色栏目侧栏（手机上文章页的侧栏放到正文后面）；文章页照交大新闻网：标题左对齐、日期、细线，文末右对齐写作者和栏目 |
| 引用 | 楷体、左右各缩进两格，出处「——出处」右对齐；不加边框和底色 |
| 图标 | `components/icon.html`，自己画的 9 个线条图标，没引入图标库 |
| 刷新 | `teams.services.refresh_team_list()` 也请求刷新首页 |

没有新增依赖。HeroUI 的原型只在临时目录里，没进仓库。

## 测试

`content/tests/test_home_sections.py` 21 条（含参数化）：焦点图顺序、回退、未发布页面回退到地址、链接地址校验（3 种拒绝、3 种接受）、首页出现轮播和脚本、没图片时没有轮播；图片新闻只取有封面的；要闻置顶在前且不重复；赛事卡片顺序和数量；日历只标公开和已结束的内战、标今天、周一开头；新建战队刷新首页；解散的战队不上首页；文章页不显示摘要（列表页显示）；引用出处带破折号；**编译后的 CSS 里没有 `.rich-text`，`.article-body p` 带首行缩进**；导航标出当前栏目。

`content/tests/test_content.py` 里「置顶文章覆盖最新文章」的断言按新设计改成「置顶在前」。

## 变异

```
KILLED   焦点图没有时不回退到带封面的文章  | 1 failed, 1 passed in 0.57s
KILLED   焦点图顺序反了  | 1 failed in 0.39s
KILLED   允许 // 开头的地址  | 1 failed, 27 passed in 3.34s
KILLED   允许 http:// 等任意地址  | 1 failed, 30 passed in 3.30s
KILLED   链接到未发布页面  | 1 failed, 2 passed in 0.71s
KILLED   图片新闻不要求封面  | 1 failed, 1 passed in 0.57s
SURVIVED  要闻重复  | 34 passed in 2.85s
KILLED   置顶不排在前  | 1 failed, 6 passed in 1.26s
KILLED   日历漏掉已结束的内战  | 1 failed, 7 passed in 1.26s
KILLED   日历包括草稿和取消  | 1 failed, 7 passed in 1.27s
KILLED   日历不标今天  | 1 failed, 7 passed in 1.28s
KILLED   日历从周日开始  | 1 failed, 7 passed in 1.33s
KILLED   内战排在赛事前  | 1 failed, 32 passed in 3.03s
KILLED   首页显示已解散的战队  | 1 failed, 9 passed in 1.39s
KILLED   战队变化不刷新首页  | 1 failed, 8 passed in 1.47s
KILLED   文章页显示摘要  | 1 failed, 10 passed in 1.56s
KILLED   引用出处不带破折号  | 1 failed, 11 passed in 1.57s
KILLED   导航不标当前栏目  | 1 failed, 12 passed in 1.69s
KILLED   首页不加载轮播脚本  | 1 failed, 3 passed in 0.75s
KILLED   没有图片也显示轮播  | 1 failed, 4 passed in 0.88s
KILLED   正文规则又写回 .rich-text  | 1 failed, 33 passed in 3.27s
20/21 killed
```

幸存的「要闻重复」是测试写弱了：置顶的是最旧的一篇，本来就不在「最新」里，去掉去重也不会重复。改成置顶最新的一篇后重跑：

```
KILLED   要闻重复  | 1 failed, 6 passed in 1.47s
1/1 killed
```

21/21 被抓到，全部还原。CSS 那条变异改的是 `input.css`，变异和还原后都重新编译了 `app.css`。

## 测试机

打补丁部署（提交后再把服务器上的仓库对齐到提交），升级流程：

```
--- 1. 升级前备份:
已备份到 /app/backups/sjtu-ow-20260919-014556.tar.gz（0.1 MB）
--- 2. 构建:
 Image sjtu-ow-test-web Built
 Image sjtu-ow-test-worker Built
--- 3. 迁移:
  Applying content.0003_homepage_carousel... OK
--- 4. 启动:
 Container sjtu-ow-test-proxy-1 Running
 Container sjtu-ow-test-web-1 Started
 Container sjtu-ow-test-worker-1 Started
web: healthy
```

**示例内容**：用户要求把示例图换成网上真实的图片。只用了 **CC0 / 公有领域**的图片（仓库是公开的，测试站也公开），**没用交大的照片和暴雪的官方素材**。来源：

| 用途 | 图片 | 来源 | 许可 |
|---|---|---|---|
| 焦点图、封面 | All-Star eSports Arena, Taipei Game Show 20190128a | Wikimedia Commons | CC0（在 Commons 的文件信息里核对过） |
| 焦点图、封面 | Taipei Game Show eSports Stage 20220125 | Wikimedia Commons | CC0（同上） |
| 焦点图 | Shanghai skyline from the bund | Wikimedia Commons | CC0（同上） |
| 封面 | 游戏键盘 | WordPress 图片库 | CC0 |
| 封面、队标 | 手柄按键、耳机、客厅开黑 | StockSnap | CC0 |

图片只在测试机的数据库和 media 里，**不进仓库**。示例内容脚本在本轮的临时目录里，没提交：建 3 个示例用户（`demo-*@example.com`，**密码不可用，不能登录**，没建管理员）、3 支战队、4 篇文章（带引用块）、2 个赛事、2 场内战、2 条车帖、3 张焦点图。

```
demo content ready
```

外部核对（首页是 Caddy 直接返回的静态页）：

```
cache-control: public, max-age=0, must-revalidate
carousel blocks: 1
carousel-box__caption">2026 秋季校内赛报名开始
carousel-box__caption">上海交通大学守望先锋社区网站开始测试
carousel-box__caption">暑期内战回顾：48 人、8 支队伍、一个晚上
/media/images/demo-arena.2e16d0ba.fill-1600x700.jpg 200 212393
/media/images/demo-shanghai.2e16d0ba.fill-1600x700.jpg 200 123794
/media/images/demo-stage.2e16d0ba.fill-1600x700.jpg 200 258517
/media/images/demo-arena.2e16d0ba.fill-600x375.jpg 200 52054
```

```
Counter({'ready': 20})
[]
worker log lines with failures: 0
{"status": "ok", ... "disk": {"ok": true, "detail": "free space 77.2%"}, "worker_heartbeat": {"ok": true, ...
HTTP/1.1 308 Permanent Redirect
```

20 个静态页全部由 worker 生成成功（064 修好后第一次大批量走 worker）。

## 验收输出

```
$ ruff check . && ruff format --check .
All checks passed!
239 files already formatted

$ uv run python manage.py tailwind build --force
Built production stylesheet '.../static/css/app.css'.

$ uv run python -m pytest -q
868 passed in 58.78s

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ （生产配置）uv run python manage.py check --deploy
System check identified no issues (0 silenced).
```

847 → 868。`app.css` 153426 字节，gzip 后 23012 字节（设计 15.1 首页资源预算 300KB）。

## 顺带发现

- **`tailwind build` 只看 CSS 入口文件的修改时间**，只改模板时会说「up to date」直接跳过，模板里新用的类名不会进 `app.css`。本轮中途因此看到过缺样式的页面。已写进 `AGENTS.md` 的坑
- `templates/core/home.html` 是 M0 的首页占位模板，现在没人用（首页由 Wagtail 的 `content/home_page.html` 渲染）。没删，留给以后清理
- 文章分类改名时，文章页侧栏里的分类名要等每晚全量生成才更新（事件表里没有「分类变化」这一行）。影响小，没加

## 改动文件

```
docs/design.md                                   v1.5.16
assets/css/input.css                             主题、页头页脚、首页、内页、正文
templates/base.html                              页头、页脚、抽屉菜单
templates/components/{main_nav,icon,about_side,account_area}.html
templates/slots/{account,home_lfg}.html
content/home.py、content/models.py              首页数据、焦点图子表
content/migrations/0003_homepage_carousel.py
content/templates/content/{home_page,article_page,article_index_page,standard_page,_news_side}.html
content/templates/content/blocks/quote.html
static/js/carousel.js
teams/services.py                                战队变化刷新首页
tournaments/templates/tournaments/detail.html、lfg/templates/lfg/index.html   标题样式
content/tests/test_home_sections.py              新建
content/tests/test_content.py                    置顶的断言按新设计改
README.md、AGENTS.md、handoff/STATUS.md
handoff/rounds/065-sjtu-style/
```
