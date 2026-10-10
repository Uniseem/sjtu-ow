# 新栈前台迁移要求

| 项目 | 内容 |
|---|---|
| 日期 | 2026-10-10（260 轮之后） |
| 状态 | **生效**。新栈前台（`web/`，前台和后台）每一页、每个部件「做到什么程度算完」的验收依据 |
| 起因 | 用户 2026-10-10：「目前这个新的前端迁移的一塌糊涂。请你给出完整的迁移要求文档。」 |
| 管什么 | 现在差什么（第 2 节）、留什么拆什么（第 3 节）、每页都要满足的硬条件（第 4 节）、前端怎么搭（第 5 节）、每一页的验收（第 6、7 节）、后端和部署先要补的（第 8 节）、怎么证明做完了（第 9 节）、要用户拍板的（第 10 节）、按什么顺序做（第 11 节）、流程纪律（第 12 节） |
| 不管什么 | 页面**长什么样、规则是什么**，本文不重复，照第 1 节的依据。进度只写 `handoff/STATUS.md` |

---

## 0. 结论

1. **260 轮说的「前台 16 页面与专用组件全量移植上线」不成立。** 正式站上文章页全部 404、图片全部是坏图、战队页数据错位、成员墙的链接是 `/members/undefined/`；52 条前台路由里 **34 条只显示一个标题**（找回密码、改密码、改邮箱、账号安全、注销、我的战队、我的报名、我的内战、建战队、管理战队、赛事报名、待发信、退订、搜索、关于、两份协议……）；后台 **17 个本该能改东西的页面一个写请求都没有**，「保存草稿」按钮不发请求就显示「草稿已保存」。
2. **可靠的只有 M2（231–238）打的底座**：样式包、SSR 服务骨架、页头页脚和几个全局部件、主题、加载条、右键菜单、样张页、CSP 和体积测试。这些留着用。
3. **页面层推倒重写**：260 的 18 个前台页面文件、253 的 27 个后台页面文件，连同 `routes.ts` 里的标题占位。**数据层和激活方式先修**：生成的接口函数绕过了 `createClient`，SSR 把会话里的权限字段丢了，客户端不是激活（hydrate）而是清空重画。
4. **验收改成「和旧站对拍」**：同一份数据，旧站（Django，代码还在仓库里）和新站各起一套，逐页、逐身份比状态码、标题、正文、链接、表单和截图。**对拍没过的页不算完成**，报告里写「完成」要附对拍结果。
5. 开工前有几件事要用户拍板（第 10 节）。**最急的是第 1 件：要不要趁 48 小时回滚窗口还没关，把正式站先回滚到旧站**，前台在测试机上重做到对拍全绿再割接。

---

## 1. 依据和优先级

页面「应该是什么样」按下面的顺序找，**本文不复述**：

| 顺序 | 依据 | 管什么 |
|---|---|---|
| 1 | `docs/design.md` 13.2–13.5、13.9、13.11、13.14–13.17（设计体系、布局、路由、个人中心、响应式、可访问性、元信息、错误页、搜索、自动保存）；`docs/design-details.md`（前台每页）；`docs/admin.md`（后台每页） | 显示什么、缺了怎么办、太长太多怎么办、谁能看到 |
| 2 | **旧站代码**：`templates/`、各应用的 `templates/`、视图、`static/js/`、`assets/css/input.css`、旧测试 | 设计文档没写到的细节：DOM 结构、类名、文案（含空状态、报错、按钮字、提示）、字段顺序、链接去向、查询参数名 |
| 3 | `docs/rewrite-research/05-business-rules.md`（R001–R237）、`08-contracts.md` | 业务规则、前后端契约 |
| 4 | `docs/design-next.md` 第 4、6 节，`docs/rewrite-research/12-architecture.md` 第 6 节 | 新栈的不变量和前端架构 |

- 依据 1 和 2 矛盾时：停下来，写进当轮报告「设计偏差」问用户，不自己挑一边。
- **旧站代码在新前台全部对拍通过之前不许删**（`design-next.md` 第 8 节最后一项本来就是这样排的，这里重申）。
- 新栈要改设计的地方（只有 `design-next.md` 第 7 节列的那几条），先改 `design-next.md` 再改代码。

---

## 2. 现状（2026-10-10 核查）

标【实测】的是对正式站 `https://sjtu.ow-shanghaiuniversity.com` 发请求或在浏览器里看到的；标【读码】的是读 `main`（`92290ea`）上的代码得出的。

### 2.1 正式站上看得到的问题

| 编号 | 现象 | 原因 | 来源 |
|---|---|---|---|
| S1 | **文章页全部 404**（站上唯一一篇 `/news/网站正式发布/` 打不开） | `ArticleDetail.vue` 写了但没进路由表；`/news/<slug>/` 和普通页 `/<slug>/` 都没登记 | 【实测】【读码】 |
| S2 | **所有图片都是坏图**（头像、队标、封面、首屏图） | 页面把 `<img src>` 写成 `/api/images/{id}`，这个接口返回的是图片信息的 JSON；真正出图的缩略图处理函数 `media.ServeThumbnailHTTP` 写了但没挂到任何路由；Caddy 的 `/media/r/*` 回源写法 `try_files {path} @api` 也不成立 | 【读码】 |
| S3 | **战队页数据错位**：`/teams/1/` 队名空白、「0 人」、已解散的队显示「暂不招募」、标题是「战队详情」 | 接口返回 `{team:{…}, members, alumni, viewer}`，页面按 `team.name`、`team.members`、`team.disbanded_at` 读顶层 | 【实测】 |
| S4 | **成员墙每个人的链接都是 `/members/undefined/`** | 字段名对不上 | 【实测】 |
| S5 | 不存在的对象返回 200：`/teams/999/` 是 200 加一句「战队不存在」 | 每个页面的 `load` 把接口错误 `catch {}` 吞成 `null` | 【实测】【读码】 |
| S6 | 访客打开 `/me/`、`/me/teams/` 是 200，不跳登录 | 同上，401 被吞了；`/me/*` 也没有「要登录」的声明 | 【实测】 |
| S7 | **34 条前台路由只有一个 `<h1>`**：`/about/`、`/terms/`、`/privacy/`、`/search/`、`/submit/`、`/letters/` 三条、`/unsubscribe/<token>/`、`/me/security/`、`/me/delete/`、`/me/teams/`、`/me/registrations/`、`/me/scrims/`、`/me/game-accounts/<id>/`、`/me/contacts/<id>/`、`/teams/new/`、`/teams/<id>/manage/`、`/tournaments/<id>/register/`、`/tournaments/<id>/signup/`、`/registrations/<id>/`、`/accounts/` 下的 logout、inactive、reauthenticate、email、password 六条、login/code/confirm、`/_styleguide/emails/` 两条 | `routes.ts` 的 `page()` 只返回标题 | 【实测】【读码】 |
| S8 | **登录**：没有「忘记密码」链接；不认 `?next=`，登录后一律去首页；没验证邮箱的人（接口回 200 + `result: "verify_required"`）被当成登录成功送回首页，其实没登录、也没去输验证码；报错读的是 `message`，接口的错误在 `error.message` | `Login.vue` 自己写的 `fetch` | 【实测】【读码】 |
| S9 | **入队申请、报名这类动作产生的信永远发不出去** | 写接口返回 `letters: {batch, count}`，规则 R206–R208 要求前端跳到「发信」页让本人确认；页面用裸 `fetch`，不看这一项；就算看了，`/letters/<batch>/` 也只是个标题。冻结的信 7 天后过期，队长收不到申请通知 | 【读码】 |
| S10 | **个人中心改宣言会改掉别的设置**：每敲一个字就把 `show_rank: true` 和 `main_role`（空时填 `"tank"`）一起提交，关了「公开段位」的人被悄悄打开；网络错误时也显示「已保存」 | `Profile.vue` 手写的「自动保存」 | 【读码】 |
| S11 | 一键退订（RFC 8058）`POST /unsubscribe/<token>/` 返回 405 | Go 注册了这条，但 Caddy 把它交给了 SSR | 【实测】 |
| S12 | `/sitemap.xml`、`/robots.txt`、`/favicon.ico` 都是 404 | `content.GenerateSitemap`、`GenerateRobots` 写了没挂路由；图标地址新站没接 | 【实测】【读码】 |
| S13 | `<title>` 格式不统一、和旧站不一样：旧站「成员 · SJTU-OW」，新站 `/members/` 是「成员 - SJTU-OW」、`/news/` 是「资讯」、`/teams/` 是「战队」、`/teams/1/` 是「战队详情 - SJTU-OW」；没有描述、分享卡片、`canonical`、图标链接 | 每页手写 `useHead` | 【实测】 |
| S14 | 后台：所有干部（包括超管）顶栏只看得到「首页」一个大类 | SSR 的 `fetchSession` 只留了 `nickname`、`admin`，把 `superuser`、`caps` 丢了；后台导航按 `caps` 过滤 | 【读码】 |
| S15 | `/healthz` 是 503（磁盘检查不过） | 运维问题，不是前台；记在这里免得被忘 | 【实测】 |

### 2.2 代码层面的问题

| 编号 | 问题 | 位置 |
|---|---|---|
| C1 | **客户端不是激活，是清空重画**：`entry-client` 用的是 `createApp`（不是 `createSSRApp`），挂载时 Vue 先清空 SSR 的 DOM 再画一遍。激活不一致永远测不出来，233 起 `browser-check.mjs` 的「激活」一项是白过的 | `web/apps/site/src/main.ts` |
| C2 | **用了被关掉的颜色**：17 个前台页面用 `stone-*`、`rose-*`、`emerald-*`、`amber-*` 这类 Tailwind 色板类（`input.css` 里 `--color-*: initial`，只留了 `white`、`black`），这些类不生成，元素没颜色；而且页面是照深色底配的色（`bg-stone-900`、`text-stone-300`），浅色模式下本来也不对（违反 AGENTS「前台组件是自己写的」那条） | 260 的 17 个前台页面（除 `Home.vue`） |
| C3 | **编出来的组件类**：`c-notice--err`、`c-notice--danger`、`c-notice--success`、`c-btn--ghost`、`c-btn--xs`、`c-checkbox`、`c-stage--member` 这 7 个，`input.css` 和旧模板里都没有，元素没样式；后台 25 个文件写 `c-notice--warning`，样式里叫 `c-notice--warn`（提示的四种是 `--info/--ok/--warn/--error`）。（`c-crumbs__sep`、`c-row__main` 这类没有样式、但旧模板里就有的挂钩类不算问题） | 前台页面、后台页面 |
| C4 | **页面不照旧站模板写**：结构、类名、文案都是重新编的（`c-btn--secondary`、「登录社区账号」「暂无队员信息」「返回战队列表」），和 `templates/` 对不上 | 各页面 |
| C5 | **数据层没有统一入口**：页面手写 `fetch` + `any`，错误吞成 `null`；`@sjtu-ow/api` 里生成的函数走自己的 `call()`——不带幂等键、不处理 401、不看 `letters`、错误抛 `Error(原文)`、用相对地址所以 SSR 里用不了；`createClient` 写好了但没有一处在用 | `pages/**`、`packages/api/src/gen/index.ts` |
| C6 | **apigen 生成的类型不对**：GET 的查询参数一个都没生成（`getApiPageNews()` 没法带 `category`、`page`）；Go 的匿名嵌入结构生成成 `Person: {…}`（JSON 里其实是摊平的）；`{…} \| null[]` 的优先级错了 | `server/internal/platform/apigen` |
| C7 | **后台的写操作基本没有**：文章编辑、赛事编辑、内战编辑、分类、成员分组、评论、巡查、战队、用户详情、角色、队伍编排、文章列表、赛事列表、内战列表、图片、待发信、报名审核共 17 页零写请求；`AdminRegistrations.vue` 32 行是空壳 | `pages/admin/**` |
| C8 | **该有的交互件一个都没有**：`useAutosave()`、`useConfirm()`、`CField`、选图对话框、Markdown 编辑器（CodeMirror 6）、拖拽编队和分队（SortableJS）、搜人；后台导航是前端手写的，没用 Go 生成的 `nav`，Go 那边的大类名（`scrims`、`tournaments`、`roles`、`moderation`、`review`）和 `admin.md` 的八个大类也对不上 | — |
| C9 | **后台走的是前台的 SSR 应用**，数据在 `onMounted` 里取，SSR 出来是空壳；`b-*` 样式打进了前台的 `site.css`。12 号文档 6.1、6.8 定的是独立 SPA、单独的样式包——要么照做，要么改设计（第 10 节第 2 件） | `App.vue`、`routes.ts` |
| C10 | **后台地址改了**：旧站 `/admin/tournaments/edit/<id>/`、`/admin/tournaments/<id>/teams/`、`/admin/pages/pins/` 在新站是 `/admin/tournaments/<id>/`、`/board/`、`/admin/home-pins/`；干部收藏的地址失效（违反 `design-next.md` 不变量 12） | `routes.ts` |
| C11 | **错误页是一行字**：`server.ts` 里写死 `<main><h1>找不到这个页面</h1></main>`，和 `templates/errors/*.html` 不一样；没有 429、500 | `entry-server.ts` |
| C12 | **客户端换页出错没人管**：`load` 抛错时导航被拒、加载条停下，页面原地不动，用户不知道发生了什么 | `entry-client.ts` |
| C13 | **测试防不住这些**：没有 `vue-tsc`、没有源码扫描守卫（色板、裸 `fetch`、`:style`、`v-html`、`any`）、没有逐页 SSR 测试、没有对拍；`scripts/journey.mjs`、`scripts/screens.mjs` 写了没跑过；`web/apps/site/screenshot-home.png` 被提交进了仓库 | — |
| C14 | **Caddy 配置**（`deploy/Caddyfile.new`）：安全头不在 Caddy 统一加（只有 SSR 的页面带 CSP，接口、`/assets/`、`/media/` 没有 `nosniff` 等）；没有 `POST /unsubscribe/*` 去 Go 的路由；502–504 不出维护页；非接口的写请求不在代理层 405；没有请求体上限；`/favicon.ico`、`/apple-touch-icon.png` 没接 | `deploy/Caddyfile.new` |

### 2.3 流程上怎么走到这一步

- 252–260 九轮在一天里做完（用户当时说「多写代码少测试」），260 连轮次目录都没有（没有 `request.md`、`report.md`、`review.md`），253 的 `review.md` 写「严格按 `superuser` 与 `caps` 过滤展示」，实际 SSR 把这两个字段丢了。
- 12 号文档 11.2 的**检查点 A（公开页对拍）和检查点 B（干部在测试机上试用）都跳过了**；M2 之后 M3–M8 只写了后端，前端页面一页没做，就在 259 割接上线，260 才补页面。
- 260 的报告说「公网实测渲染 200 OK 并通过真浏览器截图验证」——200 不等于页面对，截图没和旧站比。

第 12 节的纪律就是针对这几条定的。

---

## 3. 保留什么、重写什么

| 部分 | 处理 | 说明 |
|---|---|---|
| `web/packages/styles`（`input.css` 原样、守卫测试） | **留** | M2 的像素对拍过了（238：0.0268%） |
| `web/apps/site/server.ts` | **留，补** | 方法限制、补斜杠 301、401/403/404/503 分流、`ow-state` 转义、缓存头、无脚本横幅都对。要补：错误页正文（C11）、429/500、`load` 抛的错误按状态码分流（不再被页面吞） |
| `public/theme.js`、`ThemeMenu`、`loadbar.ts`、`CContextMenu`、`Toasts`、`WeChatHint`、`time.ts`、`initial.ts`、`BrandMark`、`CIcon`、`SLink`、`SectionHead` | **留** | 233 在真浏览器里验过 |
| `SiteHeader`、`SiteFooter`、`AccountArea` | **留，对拍时一起验** | 账号区要接上新的会话字段（头像、待发信数、资料不全） |
| `/_styleguide/`、`specimen.ts`、`browser-check.mjs`、`budget.mjs` | **留** | 新组件按 13.2.7 照旧补进样张 |
| `packages/api/src/client.ts`（`createClient`） | **留，接上** | 设计是对的；生成的函数必须经过它（第 5 节 A3） |
| `entry-client.ts`、`main.ts` | **改** | 激活（C1）、换页出错（C12） |
| `entry-server.ts` 的 `fetchSession` | **改** | 会话整份透传（S14） |
| `routes.ts` | **重写** | 照第 6、7 节逐条登记，旧地址一个不改 |
| 260 的 18 个前台页面、`CSeats`、`PostCard`、`TeamTile` | **重写** | 照旧站模板逐个搬 |
| 253 的 27 个后台页面、`AdminLayout`、`AdminHead`、`admin/nav.ts` | **重写** | 照 `admin.md`；形态看第 10 节第 2 件 |
| apigen 的 TypeScript 输出 | **重写** | C5、C6 |
| `scripts/journey.mjs`、`scripts/screens.mjs` | **改造后并进对拍工具** | 第 9 节 |

---

## 4. 不变量（每一页都要满足，一条不满足不算完成）

| 编号 | 要求 | 怎么查 |
|---|---|---|
| I1 | **地址不变**：02 号文档第 1–3 节的每个页面地址、`/news/<slug>/`、普通页 `/<slug>/` 都在，结尾斜杠照旧；查询参数名和取值照旧（`?page=`、`?category=`、`?q=`、`?next=`、`?sort=`、`?role=`、`?free=`、`?to=`、`?back=`……） | 对拍的状态码一栏；路由表测试逐条断言 |
| I2 | **状态码语义照旧**：没登录 → 302 `/accounts/login/?next=原地址`；没权限 → 403（固定文案，不说原因）；不存在、未发布、看不到的 → 404。**不许 200 加一句「不存在」** | 对拍；SSR 测试 |
| I3 | **视觉照旧**：DOM 结构和类名照旧站模板（`c-*`、`l-*`、`b-*`），只用语义颜色；375/1280、浅/深四种截图和旧站并排一致（阈值见第 10 节第 4 件） | 对拍截图 |
| I4 | **文案照旧**：标题（含 `<title>` 的「页面 · SJTU-OW」格式、后台「页面 · 管理后台」）、按钮、空状态、报错、提示、确认框，一字不改 | 对拍正文比对 |
| I5 | **写操作说真话**：只有收到 2xx 才显示成功；失败显示接口给的 `error.message` 和逐字段的 `fields`；**只提交用户改了的字段**（`PATCH` 带 `base_version`），不许顺手带上别的字段的默认值（S10） | 单元测试；旅程测试 |
| I6 | **待发信**：任何写请求的回答里有 `letters`，就跳「发信」页（前台 `/letters/<batch>/?back=`，后台 `/admin/letters/<batch>/?back=`），确认后回原页（R206–R208） | 旅程测试走一遍入队申请 |
| I7 | **隐私**：页面只画接口给的东西；接口不给看不该看的人（邮箱只给本人和超管、联系方式按 design-details 1.8、关了公开段位就不显示段位） | 守门矩阵（Go）；对拍各身份 |
| I8 | **CSP**：零内联脚本、零 `style` 属性（组件不写 `:style`）；`v-html` 只许用在服务端渲染好的 Markdown 正文（`body_html`）和邮件预览，别处一律不许 | 源码扫描测试；`browser-check` 零违规 |
| I9 | **SSR 写法纪律**（12 号 6.3）：`setup` 里不碰 `window`/`document`；时间一律走 `time.ts`（`Asia/Shanghai`）；不用随机数和当前时间决定渲染结果 | 激活不一致在浏览器测试里算失败（A1） |
| I10 | **不出现占位页**：生产构建里不许有「只有标题」的页面。没做完的地址不登记（404），并在 STATUS 的进度表里列着 | 路由表测试：每条路由都有真正的页面组件 |
| I11 | **可访问性照旧**（13.11）+ SPA 的三条（换页更新标题、焦点到新页 `h1`、读屏播报；后退恢复滚动） | 浏览器测试 |
| I12 | **体积**：首页 HTML + CSS + JS gzip ≤ 300 KB，JS ≤ 120 KB；后台的块和样式不进前台首页 | `budget.mjs` |

---

## 5. 前端架构要求

| 编号 | 要求 |
|---|---|
| A1 | **激活**：客户端用 `createSSRApp` 挂到 SSR 画好的 DOM 上。测试构建打开 `__VUE_PROD_HYDRATION_MISMATCH_DETAILS__`，`browser-check` 和旅程测试遇到任何 `Hydration` 警告都算失败。补一条「拆掉就红」：把客户端换回 `createApp`，测试必须红 |
| A2 | **路由和加载器**（12 号 6.3）：一张路由表登记全部页面地址，编号参数 `:id(\\d{1,18})`。每页导出 `load(ctx)`，只经共享的接口客户端取数，**不吞错误**；路由元信息声明 `auth: "member" \| "admin"`，SSR 在调接口前就 302 去登录（体验），真正的门仍在 Go。客户端换页时：401 整页跳登录；403/404 原地画错误页并改标题；网络错误和 5xx 弹提示、留在原页 |
| A3 | **接口客户端**：apigen 生成的每个函数都经过 `createClient`（幂等键、401、`letters`、`ApiError` 带 `fields`/`current`）；支持路径参数和查询参数；SSR 里由 `load` 传入的 `fetch` 和基地址发请求（转交 Cookie、访客 IP、请求编号）。**页面里不许出现 `fetch("/api/…")`**，有源码扫描测试 |
| A4 | **类型**：生成的类型和 Go 的 JSON 一致（匿名嵌入摊平、可空数组写对）；页面里不许 `any`；`vue-tsc --noEmit` 进每轮检查（新开发依赖，见第 10 节第 3 件） |
| A5 | **一页的数据**：服务端渲染时最多「一个页面接口 + `/api/session`」两个请求（12 号 5.4「一页一个接口，含 `viewer`」）。已有的资源接口如果已经带 `viewer`、够一页用，可以直接当页面接口；不够就在 Go 加 `/api/page/…`。第 6、7 节的表里每页写明用哪个 |
| A6 | **会话**：`/api/session` 整份进 SSR 和 `ow-state`：编号、昵称、头像地址、`admin`、`superuser`、`caps`、邮箱是否验证、资料是否不全、待发信数、一次性提示（12 号 5.4、6.4）。后端缺的字段见第 8 节 B3 |
| A7 | **图片**：一个 `imageUrl(id, spec)` 生成 `/media/r/<编号>/<规格>.webp`，规格白名单从 Go 的 `AllowedSpecs` 生成，不在白名单的规格编译不过；正文里写死的 `/media/images/*` 原样；没有图时按 design-details 2.2–2.4、13.2.5 画默认头像、底图、占位图（`/static/img/placeholders/`、`hue-N.svg`） |
| A8 | **组件**：旧站 `templates/components/` 的 22 个部件各对应一个 Vue 组件（对照表见 5.1），评论区、个人中心骨架、账号页骨架同样。每个组件：同一份数据下 SSR 输出和旧模板输出比对（去掉空白和 Vue 的片段注释后结构、类名、文字一致），并补进 `/_styleguide/` |
| A9 | **表单**：`CField`（三种：单选、多选组、普通；帮助文字；首条错误 `role=alert`）；不自动保存的表单（登录、注册、验证码……）提交时按钮禁用、显示 `fields`；自动保存的表单用 `useAutosave()`，完全照 12 号 6.7（状态、防抖、同时只一个请求、409 换成最新值、网络错误同一个幂等键退避重试、离开前先存、存不上就拦），状态行用 `c-autosave` |
| A10 | **12 个旧脚本的行为逐条搬**（12 号 6.6）：下拉互斥和外点关闭、`data-confirm` → `useConfirm()`、标签条滚到当前项、微信提示、加载条、主题、右键菜单、自动保存、后台的全选和筛选即提交和搜人（250 毫秒防抖）、选图对话框、Markdown 编辑器（CodeMirror 6 挂进 ShadowRoot，12 号 6.8）、排版预览、拖拽分队、拖拽编队（SortableJS）。每条行为一条测试 |
| A11 | **元信息**：`useHead` 统一由一个 `usePageMeta()` 出：标题格式照旧、描述、分享卡片（`fill-1200x630`）、`canonical`；`/me/`、`/accounts/`、`/letters/`、`/admin/` 加 `noindex`；图标、`apple-touch-icon`、`theme-color` 照旧 `base.html` |
| A12 | **错误页**：403/404/429/500/503 的正文照 `templates/errors/*.html`，无脚本；维护页照旧由 Caddy 出 |
| A13 | **后台**：形态按第 10 节第 2 件定。无论哪种：导航来自 Go 生成的 `nav`，大类和标签的编号、名字、顺序照 `admin.md` 第 4 节的八个大类；有能力才出现；进门没权限给 403 页；布局照 `admin.md` 第 3 节（`b-top`、`b-head`、`b-tabs`、`b-subtabs`、`b-main`、`b-split`）；`b-*` 样式单独成包，不进前台 |
| A14 | **目录**：照 12 号 6.1——`packages/ui`（组件、图标、角色字形）、`packages/shared`（时间、主题、`useAutosave`、`useSortable`、`useConfirm`、`imageUrl`）、`apps/site`、`apps/admin`（若选独立 SPA）、`e2e/`（对拍、旅程、响应头） |

### 5.1 旧部件 → 新组件

| 旧模板（`templates/components/`） | 新组件 | 现状 |
|---|---|---|
| `account_area` | `AccountArea` | 有，补会话字段 |
| `avatar`（真人头像 / 默认头像池 / 首字底图三档，xs–lg，`c-hue-N`） | `CAvatar` | 没有（各页面自己拼，且图片地址错） |
| `brand` | `BrandMark` | 有 |
| `empty_state` | `CEmpty` | 没有 |
| `form_field` | `CField` | 没有 |
| `icon` | `CIcon` | 有 |
| `main_nav` | `SiteHeader` 内 | 有 |
| `pagehead_picture`（昼夜两套场景） | `CPagehead` | 没有 |
| `pagination` | `CPager` | 没有 |
| `play_style`（位置 + 段位，180 天变灰） | `CPlay` | 没有 |
| `post_card` | `PostCard` | 有，重写 |
| `profile_gap_links` | `CProfileGaps` | 没有 |
| `rank_badge` | `CRank` | 没有 |
| `registration_status` | `CRegStatus` | 没有 |
| `role_icons`（坦 / 输 / 援字形） | `CRoleIcon` | 没有 |
| `scrim_row` | `CScrimRow` | 没有 |
| `seats` | `CSeats` | 有，重写 |
| `section_head` | `SectionHead` | 有 |
| `speculation_rules` | — | **不搬**（新栈 CSP 去掉了 `'inline-speculation-rules'`，`design-next.md` 第 5 节 15.2） |
| `status_badge` | `CStatus` | 没有 |
| `team_tile` | `TeamTile` | 有，重写 |
| `tournament_card` | `CTournamentCard` | 没有 |
| `comments/*`（section、_item、_composer、_reply、_like、_own、_more） | `CComments` 一组 | 没有 |
| `me/base.html`、`_nav`、`_incomplete`、`_letters` | `MeLayout` | 没有 |
| `account/layout.html`、`_form`、`_why`、`base_entrance`、`base_manage*`、`_back_to_security` | `AuthLayout` 一组 | 没有 |
| `teams/_logo`、`_alumnus`、`_member_contact` | `CTeamLogo` 等 | 没有 |
| `tournaments/_starts_at` | `CStartsAt` | 没有 |

---

## 6. 前台页面清单与验收

每页除第 4 节的通用条件外，还要满足「要点」一栏。「旧模板」是对拍的参照，「数据」是页面接口（缺的在第 8 节）。现状：**缺** = 只有标题或没有路由；**错** = 有页面但数据或结构错；**半** = 结构近似但没照旧模板、没对拍。

### 6.1 账号入口（`/accounts/`）

共同骨架：`account/layout.html`（一列窄表单 `c-auth` + 右侧 `c-why`）。

| 地址 | 旧模板 | 数据 | 现状 | 要点 |
|---|---|---|---|---|
| `/accounts/login/` | `account/login.html` | `POST /api/auth/login` | 错 | 「忘记密码」链接；认 `?next=`（只认站内地址）；`verify_required` 时带着邮箱去 `/accounts/confirm-email/`；已登录访问照旧站行为；限流 429 的提示 |
| `/accounts/signup/` | `account/signup.html` | `POST /api/auth/register` | 半 | 字段、顺序、协议勾选照旧；成功后去验证码页；已注册与新注册的回答一样（防枚举，R004） |
| `/accounts/confirm-email/` | `account/confirm_email_verification_code.html` | `verify-email`、`resend-code` | 半 | 重发按钮冷却（1 次 / 10 秒）；三次错作废的提示；成功即登录，去资料页并带一次性提示 |
| `/accounts/logout/` | `account/logout.html` | `POST /api/auth/logout` | 缺 | GET 是确认页，提交才退出，回首页 |
| `/accounts/inactive/` | `account/account_inactive.html` | 无 | 缺 | 静态说明 |
| `/accounts/reauthenticate/` | `account/reauthenticate.html` | `POST /api/auth/reauthenticate` | 缺 | 成功回 `?next=`，5 分钟窗口 |
| `/accounts/email/` | `account/email.html`、`email_change.html` | `email/change`、`email/change/confirm` | 缺 | 要重新认证时先去 reauthenticate；输码确认 |
| `/accounts/password/change/` | `account/password_change.html` | `POST /api/auth/change-password` | 缺 | 成功后其他会话作废的说明 |
| `/accounts/password/set/` | `account/password_set.html` | — | 缺 | 本站用户都有密码；照旧站行为（第 10 节第 5 件确认） |
| `/accounts/password/reset/` | `account/password_reset.html` | `POST /api/auth/reset-password` | 缺 | 防枚举 |
| `/accounts/password/reset/confirm/` | `account/confirm_password_reset_code.html` | `reset-password/confirm` | 缺 | 3 分钟 3 次 |
| `/accounts/password/reset/complete/` | `account/password_reset_from_key.html` | 同上 | 缺 | 没确认过码就回 confirm |
| `/accounts/password/reset/done/` | `account/password_reset_from_key_done.html` | 无 | 缺 | |
| `/accounts/login/code/confirm/` | — | 无 | 缺 | 照旧站：302 回 `/accounts/login/` |

### 6.2 内容

| 地址 | 旧模板 | 设计 | 数据 | 现状 | 要点 |
|---|---|---|---|---|---|
| `/` | `content/home_page.html`（`templates/core/home.html` 是没站点时的降级） | dd 7 | `/api/page/home` | 半 | 首屏（校徽双层、齿轮慢转、标题两行）、数字条、近期（大图卡 + 内战行最多 5 场）、**我的安排**（登录成员，B5）、资讯与公告、战队；图片全部经 A7 |
| `/news/` | `content/article_index_page.html` | dd 6.1 | `/api/page/news?category&page` | 半 | 栏目简介、分类标签（`aria-current`）、文章卡、置顶标签、分页参数照旧 |
| `/news/<slug>/` | `content/article_page.html`、`_toc.html`、`comments/section.html` | dd 6.2–6.6 | `/api/page/news/{slug}` + `/api/articles/{id}/comments` | **缺（404）** | 封面弧形页头、信息小块、正文排版、3 个标题以上才有目录（宽屏侧栏 / 窄屏 `<details>`）、作者卡、关联赛事、上下篇、评论（发表、回复、点赞、编辑、删除、隐藏、置顶、排序、加载更多，全部照 `comments/*`）、同分类更多文章；未发布 404 |
| `/about/`、`/terms/`、`/privacy/` 及其他普通页 `/<slug>/` | `content/standard_page.html` | dd 6.7 | `/api/page/{slug}` | 缺 | 没有封面；三页切换标签、最后更新日期 |
| `/search/` | `search/results.html` | 13.16 | `/api/search?q` | 缺 | 五类结果、空查询、没结果、限流 429 页 |
| `/submit/` | `content/submit.html` | — | 会话 | 缺 | 有权限跳后台写文章，没有就说明原因 |

### 6.3 个人中心（`/me/`）与发信、退订

共同骨架：`me/base.html`（页头、窄容器、桌面左侧 `c-sidenav` / 手机 `c-tabs`、资料不全提示、待发信提示）。全部要登录（A2），全部 `noindex`。

| 地址 | 旧模板 | 数据 | 现状 | 要点 |
|---|---|---|---|---|
| `/me/` | `me/profile.html` | `GET/PATCH /api/me/profile`、`POST/DELETE /api/me/avatar` | 错（S10） | 昵称、是否交大、宣言（`maxlength` 计数）、主位置单选 + 补位多选、公开段位开关，**逐字段自动保存**（A9）；头像上传进审核的说明、撤回 |
| `/me/game-accounts/`、`/<id>/` | `me/game_accounts.html` | `/api/me/game-accounts` | 半 / 缺 | 行内编辑、新增、删除（确认）；段位编码照附录 A |
| `/me/contacts/`、`/<id>/` | `me/contacts.html` | `/api/me/contacts` | 半 / 缺 | 同上；谁能看见的说明照旧 |
| `/me/security/` | `me/security.html` | `/api/me/announcements`、`/api/me/export` 等 | 缺 | 改邮箱、改密码入口；活动通知开关；导出（限流 5 次 / 小时）；注销入口 |
| `/me/delete/` | `me/delete.html` | `POST /api/auth/delete-account` | 缺 | 验密码；在任队长等阻碍逐条说明；代发的信（R208） |
| `/me/teams/` | `me/teams.html` | `/api/me/teams` | 缺 | 现役（队内联系方式三种文案）、退役记录「从名单去掉」 |
| `/me/registrations/` | `me/registrations.html` | `/api/me/registrations`、`/api/me/calendar`、`calendar/renew` | 缺 | 两张表带比赛时间；订阅到手机日历（`webcal://`）、换新地址（确认） |
| `/me/scrims/` | `scrims/me.html` | **缺接口**（B5） | 缺 | 自己的内战和分队去向 |
| `/letters/` | `core/letters/waiting.html` | `/api/letters` | 缺 | 自己还没发的信 |
| `/letters/<batch>/` | `core/letters/confirm.html` | `GET/POST /api/letters/{batch}` | 缺 | 每封主题、收件人、勾选；「发出勾选的信」「都不发」；回 `?back=` |
| `/letters/<batch>/<id>/` | 邮件预览（iframe） | **缺接口**（B5） | 缺 | 只有本人能看；邮件预览的 CSP |
| `/unsubscribe/<token>/` | `core/unsubscribe.html` | `GET/POST /api/announcements/unsubscribe/{token}` | 缺 | 免登录；`POST` 同一地址由 Go 处理（S11、B6） |

### 6.4 战队、成员

| 地址 | 旧模板 | 设计 | 数据 | 现状 | 要点 |
|---|---|---|---|---|---|
| `/teams/` | `teams/index.html` | dd 5.1 | `/api/teams` | 半 | 战队卡（底图、队标、人数 / 上限、成立、简介两行、招募和缺的位置） |
| `/teams/new/` | `teams/create.html` | — | `POST /api/teams` | 缺 | 每天 3 次、队长上限的提示照旧 |
| `/teams/<id>/` | `teams/detail.html`、`_logo`、`_alumnus`、`_member_contact`、`slots/join.html` | dd 5.3–5.4 | `/api/teams/{id}` | **错（S3）** | 队头横幅、申请面板按 `viewer`、简介保留换行、现役（停用账号的样子）、退役（12 人以上收起）、参赛记录、已解散只写一句；不存在 404 |
| `/teams/<id>/apply/` | `teams/apply.html` | dd 5.2 | `POST /api/teams/{id}/applications` | 半 | 缺的位置排前标「缺」；没有游戏 ID 的引导；**提交后走待发信（I6）** |
| `/teams/<id>/manage/` | `teams/manage.html` | dd 5.5 | `/api/teams/{id}/manage` + 各动作 | 缺 | 资料自动保存、申请批准 / 拒绝、成员表（位置、段位、停用标记）、移出、转让、退役表、解散（确认、有进行中报名时受阻）；非队长 404 |
| `/members/` | `members/index.html` | dd 4.1–4.5、4.7 | `/api/members` | **错（S4）** | 分组目录和左右两栏、名片、全部成员编号、筛选链接（位置、只看没进战队的） |
| `/members/<id>/` | `members/detail.html` | dd 4.6 | `/api/members/{id}` | 半 | 横幅、事实行、段位隐私、战队 |

### 6.5 赛事、内战

| 地址 | 旧模板 | 设计 | 数据 | 现状 | 要点 |
|---|---|---|---|---|---|
| `/tournaments/` | `tournaments/index.html` | dd 8 | `/api/tournaments` | 半 | 按阶段分组、赛事卡文案按阶段 |
| `/tournaments/<id>/` | `tournaments/detail.html`、`slots/actions.html`、`_starts_at.html` | dd 8 | `/api/tournaments/{id}` | 半 | 横幅、报名操作区按 `viewer`（个人 / 整队两套文案、名单里的队员看到自己被报了、选手联系方式）、说明、队伍与散人名单；未发布 404 |
| `/tournaments/<id>/register/` | `tournaments/register.html` | dd 8 | `POST /api/tournaments/{id}/registrations`；表单数据**缺接口**（B5） | 缺 | 只给队长（非队长回详情）；游戏 ID 默认选好；说明文案照旧 |
| `/tournaments/<id>/signup/` | `tournaments/individual_signup.html` | 8.1 | `POST/DELETE /api/tournaments/{id}/signup` | 缺 | 进散人池、取消 |
| `/registrations/<id>/` | `tournaments/registration_detail.html` | — | `/api/registrations/{id}`、`withdraw`、`leave` | 缺 | 只给队长、名单里的人、管理员；队长可改可重提 |
| `/scrims/` | `scrims/index.html` | — | `/api/scrims` | 半 | 进行中 / 已结束、`CScrimRow` |
| `/scrims/<id>/` | `scrims/detail.html`、`slots/_form.html`、`slots/actions.html` | dd 8 | `/api/scrims/{id}` | 半 | 横幅占位图按编号固定；报名表单（选 ID、位置）、改报名、取消；报了名的人看到自己的分队和 QQ 群链接 |

### 6.6 其他

| 地址 | 处理 |
|---|---|
| `/_styleguide/` | 留（M2 已对拍）；新组件补进来 |
| `/_styleguide/emails/`、`/<key>/` | 34 种信的样张（`core/styleguide_emails.html`），只给能进后台的人，否则 404；预览用邮件 CSP；**缺接口**（B5） |
| 403、404、429、500、503 | A12 |
| `/favicon.ico`、`/apple-touch-icon.png` | 301 到 `/static/img/…`（照旧站）（B2） |
| `/calendar/<token>.ics`、`POST /unsubscribe/<token>/`、`/sitemap.xml`、`/robots.txt`、`/media/images/*`、`/healthz` | 不是页面，但地址必须照旧能用（B2、B6） |

---

## 7. 后台页面清单与验收

依据 `docs/admin.md`（第 3 节布局、第 4 节每页、第 6 节测试）和 02 号文档第 1 节（地址）。**地址照 02 号第 1 节**（第 10 节第 5 件），旧书签不能失效。每页共同要求：用「能进后台但不是超管」的身份和超管各打开一遍；没登录跳登录，没这个标签的能力给 403；改值的表单自动保存（A9）；危险操作走 `useConfirm()`；动作产生的信走后台发信页（I6）。

| 大类 | 页面（地址） | 旧模板 | 现状 |
|---|---|---|---|
| 首页 | `/admin/`（问候、快捷按钮、待办卡、我的文章、上线清单） | `backoffice/home.html` | 半（只读待办） |
| 首页 | `/admin/letters/`、`/admin/letters/<batch>/` | `backoffice/letters/*` | 缺写（不能发信） |
| 内容 | `/admin/articles/`（筛选、行上撤下 / 通知全体 / 看文章） | `content/articles.html` | 缺写 |
| 内容 | `/admin/articles/new/`、`/<id>/`（表单字段按身份增减、选封面、Markdown 编辑器、关联赛事、网址和定时、自动存草稿、发布 / 撤下 / 删除）、`/<id>/preview/` | `content/article_edit.html`、`widgets/*` | **假保存**；编辑器、选图、预览都没有 |
| 内容 | `/admin/categories/`、`/new/`、`/<id>/`（删除只给没文章的） | `content/categories.html`、`category_edit.html` | 缺写 |
| 内容 | `/admin/pages/`、`/admin/pages/pins/`、`/admin/pages/intro/`、`/admin/pages/<id>/`、`/<id>/preview/` | `content/pages.html`、`draft_form.html`、`page_edit.html` | 只有置顶（地址也改了）；其余缺接口（B5） |
| 内容 | `/admin/images/`（网格、筛选、48 一页）、`/upload/`（多张）、`/<id>/`、集合管理 `/collections/`；选图对话框 | `content/images.html`、`image_upload.html`、`image_edit.html`、`collections.html`、`image_chooser.html` | 只读；上传、编辑、集合缺（部分缺接口） |
| 活动 | `/admin/tournaments/`（筛选、待审核件数、「更多」菜单按状态）、`/new/`、`/edit/<id>/`、`/copy/<id>/`、`/delete/<id>/`、`/<id>/action/<动作>/`（发布可顺带通知）、`/<id>/cancel/` | `events/tournaments.html`、`event_form.html`、`tournaments/admin/confirm.html` | 缺写；地址改了 |
| 活动 | `/admin/tournaments/<id>/teams/` 队伍编排板（散人池、多队、满队拒收、低于下限标记、键盘移动、两阶段保存、`base_version`） | `tournaments/admin/teams.html`、`_zone`、`_card` | 只读，没有拖拽 |
| 活动 | `/admin/scrims/` 同赛事一套、`/<id>/cancel/`、`/<id>/<动作>/` | `events/scrims.html`、`scrims/admin/confirm.html` | 缺写 |
| 活动 | `/admin/scrims/<id>/split/` 分队板（勾选上场、生成、拖拽 A/B 队和缓冲区、每动一次就存、复制文案、过期标记、`board_version`）、`/split/text/` | `scrims/admin/split.html`、`_board`、`_zone`、`_card`、`_roles`、`_problem`、`_copy` | 半（有写，没有拖拽、没有自动保存） |
| 活动 | `/admin/announce/<种类>/<id>/`（`?to=participants`） | `core/admin/announce.html` | 缺 |
| 成员 | `/admin/users/`、`/<id>/`（停用写原因、角色勾选、个人功能规则） | `members/users.html`、`user_edit.html` | 缺写 |
| 成员 | `/admin/roles/`（每组人数、能做什么、功能限制加删） | `members/roles.html` | 缺写 |
| 成员 | `/admin/teams/`、`/edit/<id>/`、`/<id>/assign-captain/`、`/<id>/disband/` | `members/teams.html`、`team_edit.html`、`teams/admin/*` | 缺写；地址改了 |
| 成员 | `/admin/member-groups/`、`/new/`、`/<id>/`（搜人加人、排序、头衔、移出） | `members/groups.html`、`group_edit.html`、`_people.html` | 缺写 |
| 审核 | `/admin/registrations/`（筛选、批量通过、导出 CSV）、`/<id>/`（通过 / 驳回 / 撤销） | `tournaments/admin/review_index.html`、`review_detail.html` | 空壳；全局列表、批量、导出、撤销缺接口 |
| 审核 | `/admin/moderation/`、`/<id>/`（处置、发信要作者改；AI 巡查按 D5 只读） | `moderation/index.html`、`detail.html` | 缺写 |
| 审核 | `/admin/avatars/`（三种状态的标签） | `moderation/avatars.html` | 半 |
| 审核 | `/admin/comments/`（筛选、隐藏 / 恢复、置顶 / 取消） | `review/comments.html` | 缺写 |
| 数据 | `/admin/activity/`（周期、CSV） | `core/admin/activity.html` | 半 |
| 设置 | `/admin/settings/site/`（分组、选图、密钥不回显、测试邮件、试异地备份） | `settings/site.html` | 半 |
| 设置 | `/admin/settings/fonts/…`、`/admin/settings/typography/`（D4） | `core/fonts/*` | 缺（缺接口） |
| 设置 | `/admin/log/`（筛选、50 一页） | `settings/log.html` | 半 |
| 设置 | `/admin/settings/prerender/` | — | **不搬**（新栈没有预渲染）；旧地址给 404 还是 301 到设置页，第 10 节第 5 件一起定 |
| 手册 | `/admin/manual/`（按角色出部分，路径照新后台说法） | `core/admin/manual.html` | 半 |

---

## 8. 后端和部署的前置缺口

前台做不下去、或者做了也白做的地方。每条照现有 Go 的标准做（注册表声明、守门矩阵、`// 契约 Rxxx`、变异），**在用到它的那一组页面之前或同一轮做完**。

| 编号 | 缺口 | 挡住哪些页 |
|---|---|---|
| B1 | **缩略图出图**：挂上 `/media/r/<id>/<spec>.webp` 的原始处理函数（文件在就由 Caddy 出，不在才回源 Go 生成），修 Caddy 回源写法；生成 `AllowedSpecs` 给前端 | 所有带图的页（S2） |
| B2 | 挂上 `/sitemap.xml`、`/robots.txt`；`/favicon.ico`、`/apple-touch-icon.png` 301 | S12 |
| B3 | `/api/session` 补头像地址、资料是否不全、待发信数、一次性提示 | 页头账号区、个人中心、后台 |
| B4 | **apigen**：查询参数、匿名嵌入摊平、可空数组、生成的函数经过 `createClient`、`nav` 带大类和标签的名字与顺序，并和 `admin.md` 八个大类对齐 | 全部（C5、C6、C8） |
| B5 | **缺的接口**：`/api/me/scrims`（我的内战和分队去向）；战队报名表单数据（能选的名单、游戏 ID）；建战队表单的限制；我的安排进首页数据或单独接口；待发信单封预览（HTML）；邮件样张列表和预览；Markdown 预览、编辑器传图（走统一上传管线）；后台「网站页面」（列表、普通页、栏目简介的读写、预览、发布）；图片改标题和集合、集合增删改；报名全局列表、批量通过、导出 CSV、撤销；分队结果纯文本；字体库和排版（D4）；试异地备份 | 6.3–6.6、第 7 节 |
| B6 | **Caddy**：`POST /unsubscribe/*` 去 Go；安全头（CSP 按前台 / 后台 / 邮件预览三套、HSTS、`nosniff`、`Referrer-Policy`、`frame-ancestors`）统一在 Caddy 加；502–504 出维护页；非接口的写请求 405；请求体上限（上传 10 MB，其余 1 MB）；后台形态定了以后 `/admin/*` 的去向 | S11、C14 |
| B7 | 如果后台选独立 SPA：`apps/admin` 的构建和部署（产物进 assets 卷，`/admin/*` 给 `index.html`） | 第 7 节 |
| B8 | `/healthz` 磁盘告警（S15）：运维处理，清理前问用户 | — |

---

## 9. 怎么验收

### 9.1 每轮必跑（测试机，后台跑，照 AGENTS「常用命令」）

现有整组（Go 五项 + `pnpm install --frozen-lockfile` + `pnpm test`）之外加上：

1. `vue-tsc --noEmit`（严格模式）
2. **源码扫描守卫**（Vitest 读源文件，不加新依赖）：没有色板类（`(bg|text|border|…)-(stone|rose|…)`，`white`、`black` 除外）、没有 `c-`/`l-`/`b-` 类是 `input.css` 和旧模板里都找不到的、页面里没有 `fetch("/api`、没有 `:style`、`v-html` 只在白名单文件里、页面里没有 `any`、路由表里没有只返回标题的页面
3. **逐页 SSR 测试**：每页用固定数据渲染，断言状态码、`<title>`、关键结构、没有可执行内联脚本和 `style` 属性；401/403/404 三种分流
4. 构建 + `budget.mjs`
5. `browser-check.mjs`（加上 A1 的激活检查）
6. 当轮动到的页面跑对拍（9.2）和相关旅程（9.3）

每条新守卫都要「拆掉就红」（硬规则 7）：比如把一个页面的 `catch {}` 加回去，对应的 404 测试必须红。

### 9.2 对拍（本文的核心验收）

- **数据**：在测试机上用旧站的种子数据（`scripts/screens.py` 那套：成员、队长、战队、个人赛、整队赛、内战，外加文章、评论、普通页、图片）建旧库 → `sjtuow import` 导进新库 → 媒体一起拷。两边同一份数据、同一组账号。
- **两套服务**：旧站 Django 开发服务器（关预渲染）；新站 `sjtuow serve` + 生产构建的 SSR + 按 `Caddyfile.new` 起的 Caddy（这样响应头和路由也一起验）。
- **会话**：旧站沿用 `screens.py` 在服务器里直接生成会话的办法；新站给 `sjtuow` 加一个只在测试里用的「给某个用户发会话」命令（不输入任何密码）。
- **身份**：访客、普通成员、队长、能进后台但不是超管的干部（赛事管理员、内战管理员、内容编辑各一个）、超管。
- **每个地址 × 每个身份比**：
  1. 状态码和跳转去向
  2. `<title>`
  3. `#main` 的纯文本（去掉空白差异；相对时间按同一时刻算）
  4. `#main` 里的链接集合（`href`）
  5. 表单控件（`name`、类型、选项）
  6. `#main` 截图：375 / 1280 × 浅 / 深，减少动态效果，图片先拉起来（238 的做法，`handoff/rounds/238-m2-styleguide-shots/compare.py`）
- **输出**：一张表，每个「地址 × 身份」一行：通过 / 有差异（列出差异和原因）/ 失败。工具放 `e2e/parity/`，用 Node 自带的 WebSocket 走 CDP（和 `browser-check.mjs` 一样，零新依赖）；如果第 10 节第 3 件同意加 Playwright，就用 Playwright 并加跑 WebKit。
- 已知的、设计允许的差异（`design-next.md` 第 7 节：后台编辑器换了、原图不再公开等）写进工具的白名单，每条注明出处。

### 9.3 浏览器旅程

把 `scripts/journey.py` 的三种模式**逐条断言地**搬到新栈（`scripts/journey.mjs` 已有雏形）：

- **新人的第一晚**：注册 → 从 worker 发的信里读验证码 → 验证 → 加游戏 ID 和联系方式 → 报内战 → 申请战队（**经过发信页**）→ 首页「我的安排」
- **pages**：每个地址以访客、成员、干部、超管打开
- **admin（干部那一晚）**：再报 10 个人；分队页勾满 10 人、生成、用卡片按钮移到缓冲区再移回、保存；编队页把 3 个散人编进新队、起名、保存；写一篇文章、对话框选封面、发布

任何一步出现：控制台错误、未捕获异常、CSP 违规、激活不一致、500，都算失败，退出码 1。

### 9.4 一页「完成」的定义

同时满足：

1. 第 4 节 I1–I12 全部满足
2. 第 6、7 节这一行的「要点」逐条有测试或对拍证据
3. 对拍这一页的所有身份都是「通过」，或差异已列出并由用户认可
4. 这一页涉及的旅程步骤通过
5. 报告里贴了上面这些的真实日志名和退出码

### 9.5 进度怎么记

`handoff/STATUS.md` 加一张「前台页面进度」表，行就是第 6、7 节的每个地址，列是「页面 / 组件 / 接口 / 对拍 / 旅程」五格，每轮更新。**里程碑描述只按这张表说话**，不再写「全量完成」这种总括句。

---

## 10. 待用户拍板

2026-10-10 用户拍了前四件（265），266 补齐地址和 IP 试用入口，结果在最后一栏。

| 编号 | 问题 | 选项 | 建议 | 拍板 |
|---|---|---|---|---|
| 1 | **正式站现在怎么办** | ① 趁 48 小时回滚窗口（`docs/cutover.md` 第 4 节；按割接快照 `legacy-final-20261009134549` 算，大约 10-11 到期，以服务器上旧镜像和数据卷是否还在为准）回滚到旧站，前台在测试机上重做，对拍全绿再割接；② 不回滚，先做第 11 节的 F0 止血，没做完的地址在生产上 404 | **①**。割接对账显示正式站上只有 1 个用户、1 支队、1 篇文章，回滚丢的数据几乎为零；现在新站的找回密码、改密码、文章页、个人中心大半、后台的编辑和发布都不能用，没验证邮箱的人登录不进来。回滚后要把割接时停掉的旧站定时任务恢复，并在 10-25 柏林换冬令时前换成新的 cron 写法（AGENTS 第二台服务器那一节） | **回滚到旧站**（265 做完：10-10 15:30 北京时间起正式站是旧站） |
| 2 | **后台的形态** | ① 照 12 号 6.8：`apps/admin` 独立 SPA，Caddy 直接给 `index.html`，不经 SSR；② 改设计：后台留在 SSR 应用里，和前台一样用加载器 | **①**。后台不需要 SEO 和首屏渲染，独立打包不占前台体积，CSP 和编辑器的 ShadowRoot 也更好隔离；现有后台页面反正要重写 | **独立 SPA** |
| 3 | **新依赖**（硬规则 5） | SortableJS（MIT，旧站就在用，12 号 6.6 写了保留）；CodeMirror 6 一组（MIT，12 号 6.8，含显式声明 `@codemirror/streamparser`）；`vue-tsc`（MIT）；Playwright（Apache-2.0，对拍和 WebKit） | 前三个必须加；Playwright 建议加（iOS / 微信内置浏览器只有 WebKit 能代表），不加就用 CDP 只跑 Chromium，Safari 手工试 | **四个都同意**（SortableJS、CodeMirror 6、vue-tsc、Playwright） |
| 4 | **对拍的截图阈值** | `#main` 像素差上限 | 0.5%（238 的样张做到了 0.0268%）；超过的逐页说明原因 | **0.5%** |
| 5 | **地址的几处细节** | 后台旧地址照 02 号第 1 节原样（推荐），还是新地址加 301；`/admin/settings/prerender/` 和 `/accounts/password/set/` 的去向 | 后台地址原样；两处没用的旧地址 301 到上一级 | **按文档建议保留旧地址**（266） |
| 6 | **检查点 B 的测试站（D8）** | 测试机配一个子域名经你的反代转过去，给干部试用 | 割接前要有；没有就只能在测试机上截图给你看 | **直接 IP 访问**（266） |

---

## 11. 阶段计划

按依赖排，**一组页面一轮或两轮**，不再「一轮全量」。轮数是估计。

| 阶段 | 内容 | 出口条件 | 估计 |
|---|---|---|---|
| **F0 止血**（只在第 10 节第 1 件选②时做） | S1–S4、S6、S8–S12 的最小修复；没做完的地址从生产路由表拿掉（404）；部署 | 正式站上这些地址实测正确 | 1–2 轮 |
| **F1 底座** | A1–A7、A9 的 `CField` 和 `useAutosave`、A11、A12；B1–B4；源码扫描守卫；`vue-tsc`；对拍工具和种子数据；旅程脚本骨架 | 9.1 全绿；对拍工具对 `/_styleguide/` 跑通（应和 238 一致） | 3–4 轮 |
| **F2 部件** | 5.1 表里的全部组件，逐个和旧模板比 SSR 输出，进样张 | 样张页对拍通过 | 2 轮 |
| **F3 账号入口** | 6.1 全部 14 条 + 错误页 | 这些地址对拍通过；新人第一晚走到「验证完成」 | 2 轮 |
| **F4 内容** | 6.2 全部（含评论、搜索） | 对拍通过 | 2–3 轮 |
| **F5 个人中心** | 6.3 全部（含发信、退订）；B5 的相应接口 | 对拍通过；新人第一晚走完 | 2–3 轮 |
| **F6 战队、成员** | 6.4 全部 | 对拍通过 | 2 轮 |
| **F7 赛事、内战** | 6.5 全部 | 对拍通过 | 2 轮 |
| **F8 后台底座** | A13、`apps/admin`（若选①）、导航、门、发信页、选图、编辑器、`useSortable`、`usePersonSearch` | 后台首页和发信页对拍通过；每个后台地址三身份打开无报错 | 2–3 轮 |
| **F9 后台各页** | 第 7 节全部；B5 的后台接口 | 对拍通过；干部那一晚走完 | 6–8 轮 |
| **F10 收尾** | 全站对拍一次（全部地址 × 全部身份）、WebKit、响应头、体积；检查点 B 干部试用；再割接（若回滚了）；之后按 `design-next.md` 第 8 节删 Django | 对拍全绿；干部能完成一周的日常工作 | 2–3 轮 + 试用期 |

合计约 25–35 轮。F3–F7 互相不依赖，可以换顺序；F9 依赖 F8。

---

## 12. 流程纪律

这次乱，乱在流程。下面几条和 `handoff/README.md` 一起执行：

1. **每轮都有** `request.md`、`report.md`、`review.md`；报告里只放真实跑过的输出，页面的「完成」要附 9.4 的证据。没有证据就写「未完成」。
2. **一轮一组页面**（第 11 节的一个阶段或半个），不在一轮里铺开全站。
3. **不再「多写代码少测试」**：测试和对拍是完成的一部分，不是可选项。用户要求加速时，减的是范围，不是验收。
4. **自查要换角度**：把页面改坏看测试红不红；拿旧站模板逐段对；用非超管身份打开。自查不能替代独立复核，STATUS 里标「自查通过」。
5. **部署到正式站**：只部署对拍通过的页面；部署后对正式站跑一遍只读的 pages 巡检（访客身份）。
6. **不宣称没做到的事**：STATUS 的 `milestone`、提交标题、报告结论都按 9.5 的进度表写。
7. **提交署名照实写具体模型**（硬规则 3）。

---

## 本文的维护

- 拍板结果（第 10 节）定了以后，改本文对应的行，并在 `design-next.md` 第 9 节记一行；改了 12 号文档的地方（比如后台形态选②）同步改 12 号第 6 节。
- 每做完一组页面，不改本文的现状列，进度只在 STATUS 的进度表里更新；本文的第 2 节是 2026-10-10 的快照。
- 割接并删掉 Django 以后，本文的要求并进 `design.md` v8.0（`design-next.md` 第 8 节），本文删除。
