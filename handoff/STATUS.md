# 当前状态

```yaml
milestone: 正式站265起仍旧Django，新栈逐页验收/试用后割接。285账号正常态98/98、284真SMTP35、283真评论23已验；286全Web严格类型门及必要契约/空节点/安全投影修复已验。账号错误/限流态、F4全身份、真实图片及F5–F10仍待，既有any随待重写页面清理，不称全量完成。自主范围例外见request，长期分工不变。
round: 286-f1-strict-types
next_frontend: BE-4–8已接；285账号正常态98/98及284真实SMTP35已验；286全Web strict/strictTemplates门进pnpm test，必要契约/空节点修复已验。下一步账号错误/限流态、F4全身份视觉和F5–F10。F2真实图片样张/自动保存等仍待，既有待重写any随各页面组清理。长期分工不变。
next_backend: 282公开门/283生成与限额/284邮件MIME已验；286查询严格生成、禁PasswordHash序列化、兼容roles/slug/招募投影与JSON/HTTP回归已过。继续配合错误态及F5接口；旧普通页限制重建/访问解锁和真实旧库核查仍待。未部署IP试用站，正式站Django；长期分工不变。
updated: 2026-10-11
blocked_on: 无（等用户点头的三件不挡开发：定时任务换冬令时写法、磁盘清理、异地备份）
```

## 前台迁移（2026-10-10 起，先读这里）

**正式站现在跑的是旧站（Django）**：259 割接到新栈，前台没做完，265 按用户的决定回滚了（旧库和割接前的快照逐字节一致，没丢数据）。新栈的前台在测试机上做，和旧站对拍全绿、干部试用过（检查点 B）再割接；下一次割接照 `docs/cutover.md` 第 5 节（先给旧镜像另打标签）。

**259 曾经把正式站割接到新栈，但新栈的前台没做完。** 261 核查了正式站和代码，把要求写进 `docs/frontend-migration.md`（现状、留什么拆什么、不变量、架构要求、每页验收、后端缺口、和旧站对拍的验收方法、待拍板、阶段计划、流程纪律）。**做前台的每一轮都照它来**；[历史状态](archive/status-through-277.md)里 252–260 的说法，凡是和它冲突的以它为准。

- 一页「完成」的定义见那份文档 9.4：不变量全满足、要点有证据、和旧站对拍通过、旅程通过、报告贴日志
- 里程碑描述只按下面这张表说话，不再写「全量完成」这种总括句
- 迁移文档第 10 节六件已拍板（265、266）；割接时间仍需检查点 B 后确定。

### 底座进度（文档第 5、8 节）

| 项 | 状态 |
|---|---|
| A1 激活（`createSSRApp`，browser-check 验 `#main` 没被换掉） | ✓ 262 |
| A2 加载器（`ctx.api`、`ctx.query`、不吞错误、`auth: "member"`、客户端换页出错的去向） | ✓ 262（260 的页面还没换成新写法） |
| A3 接口客户端（生成的函数经 `createClient`、查询参数、超时、连不上 `ApiError(0)`） | ✓ 262 |
| A4 类型（嵌入摊平、`(T \| null)[]`、切片不会是 null） | 半（262/283契约；286全Web strict/strictTemplates门已进整组，既有待重写any随F5–F9清理） |
| A6 整份会话进页面（`superuser`、`caps`） | ✓ 262；B3 一次性提示已在 268 实现；头像、资料不全、待发信数仍缺 |
| A7 图片地址（`imageUrl`、规格白名单从 Go 生成） | ✓ 263（旧图的母版没导，见 264） |
| A12 错误页照旧站（独立文档、`error.css`、无脚本；渲染抛错 500） | ✓ 263 |
| 源码守卫（色板、编出来的类、裸 `/api/`、`style`、`v-html`、`any`；待重写列表只缩不涨） | ✓ 263 |
| B1 出图（`/media/r/<id>/<spec>.webp`，Caddy 缺图回源 Go） | ✓ 263 |
| B2 `sitemap.xml`、`robots.txt`、图标跳转 | ✓ 263 |
| B6 Caddy（`{client_ip}`、安全头、维护页、请求体上限、一键退订、media 路径） | ✓ 263（`e2e/caddy/smoke.sh`；部署后才生效） |
| 旧原图导成母版（`sjtuow import-media`） | ✓ 264（正式站上还没跑） |
| 对拍工具（`e2e/parity/run.sh`，同一份数据、旧站和新站逐页逐身份比） | ✓ 264 |
| A5、A8–A11、A13、A14；B3–B5、B7、B8 | B3 提示部分 268；其余 — |

### F2 公共组件进度

- **266 第一组自查通过**：CAvatar、CEmpty、CField、CPager、CRank、CRoleIcon、CPlay、CProfileGaps、CStatus、CRegStatus、CSeats；CIcon、BrandMark、SectionHead 与图标移入 packages/ui；时间、图片、首字移入 packages/shared。旧模板 60 组 SSR 参考通过；16 处显示规则变异、1 处对拍守卫变异抓到；整组 Go/Web 和 browser-check 通过。
- 样张真正跑过四种组合（此前 --wide 漏了 375 深色，已补）：最大差 0.05906%，都小于 0.5%，正文/链接/控件/状态/标题一致。日志与证据见 266 报告。
- **267 部分完成**：栏目图片 CPagehead、PostCard、TeamTile、CTournamentCard、CScrimRow、CTeamLogo、CStartsAt、AuthLayout/旁栏/面包屑/错误提示、MeLayout 已实现；新增 35 组旧模板真渲染参考，组件 SSR 对照全部通过。文章/战队卡保留 site 兼容导出，默认封面与上海时区显示搬进 shared。整组 Go/Web（15 + 153 条）、browser-check 和 13 处变异通过。用户要求先更新文档并推送，按当前实际进度收口。
- **待验收/待做**：267 新组件尚未接入样张、未跑四种组合截图对拍；真实图片与默认图片池的页面投影、完整账号表单与个人中心行为仍待各页面组。评论、真实图片样张、自动保存等仍待补。F2 未完成，页面表不因公共组件通过而直接标完成。

### 前台页面进度

**264 对拍基线**：清单 48 行（现在 47 行，去掉了旧站开发设置下不公平的 404）只有 `/_styleguide/` 一行通过，其余全部「不同」；逐行的差别在 `handoff/rounds/264-f1-image-masters-parity/parity-baseline.md`。下表的「对拍」一栏，没写的就是「不同（264 基线）」。

账号组285正常/待验证态98/98，272对截图差0；30跳转含六项已批准301。错误/过期/限流逐字截图仍待；286严格类型门已补，既有any随待重写页面清理。真实SMTP35与视觉夹具分记，不称整页完成。

每轮更新。格子里：`—` 没开始、`缺` 只有标题或没有路由、`错` 有但数据或结构错、`半` 近似但没照旧模板、`✓` 做完并有证据。「页面」是页面本身，「部件」是它用到的组件，「接口」是它要的后端接口，「对拍」「旅程」见文档 9.2、9.3。

| 地址 | 页面 | 部件 | 接口 | 对拍 | 旅程 |
|---|---|---|---|---|---|
| **账号入口** | | | | | |
| `/accounts/login/` | 半（268实现；285正常态已验） | ✓ | ✓ | ✓（285正常态七身份；错误态待） | ✓（284真实登录/错误/安全next） |
| `/accounts/signup/` | 半（268实现；285正常态已验） | ✓ | ✓ | ✓（285正常态七身份；错误态待） | ✓（284真实注册/未验证/防枚举） |
| `/accounts/confirm-email/` | 半（268重写；285正常态已验） | ✓ | ✓ | ✓（285正常态七身份四组合） | ✓（284 SMTP码/三次作废/重发/验证登录） |
| `/accounts/logout/` | 半（268实现；285正常态已验） | ✓ | ✓ | ✓（285七身份；访客跳转修复） | ✓（284 GET确认/POST撤销） |
| `/accounts/inactive/`、`/reauthenticate/` | 半（268实现；285正常态已验） | ✓ | ✓ | ✓（285正常态七身份四组合） | ✓（284说明打开/重新认证/草稿返回） |
| `/accounts/password/change/` | 半（268实现；285正常态已验） | ✓ | ✓ | ✓（285正常态七身份；错误态待） | ✓（284改密保留本人/撤销其他会话） |
| `/accounts/password/set/`、`/login/code/confirm/` | 半（268 真跳转） | — | — | ✓（285七身份跳转；设密码6项已批准301） | ✓（284/285真实跳转；安全页F5待） |
| `/accounts/password/reset/done/` | 半（268 静态说明） | ✓ | — | ✓（285正常态七身份四组合） | ✓（284重置落地且不自动登录） |
| `/accounts/email/`、`/accounts/password/reset/` | 半（269实现；285正常态已验） | ✓ | ✓（269 回归） | ✓（285正常态七身份；错误态待） | ✓（284真实SMTP换邮箱/取消/找回/防枚举） |
| `/accounts/password/reset/confirm/`、`/complete/` | 半（269实现；285正常态已验） | ✓ | ✓（269 回归） | ✓（285正常态七身份四组合） | ✓（284三步/私有凭证/全会话撤销） |
| **内容** | | | | | |
| `/` | ✓（275；281接聚合agenda） | ✓ | ✓（281接BE-6；282公开API矩阵） | ✓（281/282访客/成员四组合） | 未逐项验 |
| `/news/` | ✓（275；281接生成类型） | ✓ | ✓（281接BE-5；282公开API矩阵） | ✓（281/282访客四组合） | 未逐项验 |
| `/news/<slug>/`（含评论） | 半（283类型/edited_at与真实旅程通过；全身份视觉待补） | ✓（17组旧模板；283真实Go23/23） | ✓（字段已接；282公开矩阵；283每日编辑限额） | ✓（283访客/成员四组合，最大0.153032%） | ✓评论写旅程283真实Go/Caddy23/23；桩23/23分别记录 |
| `/about/`、`/terms/`、`/privacy/`、普通页 | 半（270 照旧模板） | ✓ | ✓（BE-0/1） | ✓（275，三页访客逐字通过） | — |
| `/search/` | 半（270 照旧模板） | ✓ | ✓（BE-2） | ✓（275，访客逐字通过） | — |
| `/submit/` | 半（270 照旧模板） | ✓ | 半（BE-3） | 访客 ✓（270，四组合）；成员 302 一致、目的地是后台写文章页（F9） | — |
| **个人中心、发信、退订** | | | | | |
| `/me/` | 错（会改掉公开段位） | — | ✓ | — | — |
| `/me/game-accounts/`、`/<id>/` | 半 / 缺 | — | ✓ | — | — |
| `/me/contacts/`、`/<id>/` | 半 / 缺 | — | ✓ | — | — |
| `/me/security/`、`/me/delete/` | 缺 | — | ✓ | — | — |
| `/me/teams/`、`/me/registrations/` | 缺 | — | ✓ | — | — |
| `/me/scrims/` | 缺 | — | 缺 | — | — |
| `/letters/`、`/letters/<batch>/` | 缺 | — | ✓ | — | — |
| `/letters/<batch>/<id>/` | 缺 | — | 缺 | — | — |
| `/unsubscribe/<token>/`（含一键退订） | 缺 | — | 半（Caddy 没接 POST） | — | — |
| **战队、成员** | | | | | |
| `/teams/` | 错（新站 500，264 对拍发现） | — | ✓ | — | — |
| `/teams/new/` | 缺 | — | 半 | — | — |
| `/teams/<id>/` | 错（数据错位） | — | ✓ | — | — |
| `/teams/<id>/apply/` | 半（不走发信） | — | ✓ | — | — |
| `/teams/<id>/manage/` | 缺 | — | ✓ | — | — |
| `/members/` | 错（链接 undefined） | — | ✓ | — | — |
| `/members/<id>/` | 半 | — | ✓ | — | — |
| **赛事、内战** | | | | | |
| `/tournaments/`、`/tournaments/<id>/` | 半 | — | ✓ | — | — |
| `/tournaments/<id>/register/` | 缺 | — | 半（表单数据缺） | — | — |
| `/tournaments/<id>/signup/` | 缺 | — | ✓ | — | — |
| `/registrations/<id>/` | 缺 | — | ✓ | — | — |
| `/scrims/`、`/scrims/<id>/` | 半 | — | ✓ | — | — |
| **其他** | | | | | |
| `/_styleguide/` | ✓（M2） | ✓ | — | ✓（238） | — |
| `/_styleguide/emails/` 两条 | 缺 | — | 缺 | — | — |
| 错误页 403/404/429/500/503 | 半（一行字） | — | — | — | — |
| `/sitemap.xml`、`/robots.txt`、`/favicon.ico`、`/apple-touch-icon.png` | — | — | 缺（没挂路由） | — | — |
| **后台**（已定独立 SPA，265；尚未重做） | | | | | |
| 首页、发信 | 半 / 缺写 | — | ✓ | — | — |
| 内容：文章列表、写文章、编辑（含预览、编辑器、选图） | 缺写（假保存） | — | 半（预览、传图缺） | — | — |
| 内容：分类 | 缺写 | — | ✓ | — | — |
| 内容：网站页面（置顶、栏目简介、普通页） | 只有置顶 | — | 缺 | — | — |
| 内容：图片（网格、上传、编辑、集合、选图对话框） | 只读 | — | 半 | — | — |
| 活动：赛事（列表、新建、编辑、复制、删除、动作、取消、通知） | 缺写 | — | ✓ | — | — |
| 活动：队伍编排板 | 只读 | — | ✓ | — | — |
| 活动：内战（同赛事一套） | 缺写 | — | ✓ | — | — |
| 活动：分队板、分队文字 | 半（无拖拽） | — | 半（文字缺） | — | — |
| 成员：用户、角色 | 缺写 | — | ✓ | — | — |
| 成员：战队（编辑、指定队长、解散） | 缺写 | — | ✓ | — | — |
| 成员：成员分组 | 缺写 | — | ✓ | — | — |
| 审核：报名（列表、详情、批量、导出、撤销） | 空壳 | — | 半 | — | — |
| 审核：内容巡查 | 缺写 | — | ✓ | — | — |
| 审核：头像 | 半 | — | ✓ | — | — |
| 审核：评论 | 缺写 | — | ✓ | — | — |
| 数据：活动数据 | 半 | — | ✓ | — | — |
| 设置：全站设置 | 半 | — | 半（试异地备份缺） | — | — |
| 设置：字体库、排版（D4） | 缺 | — | 缺 | — | — |
| 设置：操作记录 | 半 | — | ✓ | — | — |
| 手册 | 半 | — | ✓ | — | — |

## 交给后端（GPT）

前端需要后端补的接口与缺陷。字段形状、完成后的类型接入和状态更新规则只维护在 [改动范围与交接](OWNERSHIP.md)，编号对应 pending-api 的 `[BE-n]`。

| 编号 | 状态 | 接口 | 要补什么（依据） | 挡住的对拍 |
|---|---|---|---|---|
| BE-0 | 已接 275 | `sjtuow import`（`internal/content/import.go` 第 5 段） | **普通页一条都没导进来**：它读旧库的 `content_sitepage`，旧站的表是 `content_standardpage`（`content/models.py` `StandardPage`），`QueryContext` 报错被 `if err == nil` 吞了，`INSERT` 的错误也是 `_, _ =`。270 对拍里 `/about/`、`/terms/`、`/privacy/` 在新站都是 404。改成读 `content_standardpage`，顺带把 `seo_title`、`search_description`、`first_published_at`、`last_published_at`（`wagtailcore_page`）一起导；这一段和同文件别处吞掉的错误改成报出来（导入失败要让人看见）。正式站割接前必须修，否则三页协议在新站消失 | `about`、`terms`、`privacy` |
| BE-1 | 已接 275 | `GET /api/page/{slug}` | 加 `seo_title`、`search_description`、`last_published_at`（可空，RFC 3339）。`content.Page` 里都有，`SitePageOut` 没带出来（`content/models.py` `StandardPage` + `SeoPageMixin`） | `about`、`terms`、`privacy` |
| BE-2 | 已接 275 | `GET /api/search?q=` | 回答改成旧搜索页的分组：`{query, groups: [{key, label, hits: [{title, url, excerpt, meta}], truncated}]}`。规则逐条照 `search/services.py`：查询去空白截 50 字、按空白切最多 5 个词、大小写折叠、每个词都要命中，空查询不搜；四组顺序固定 `articles` 文章 / `events` 赛事与内战 / `teams` 战队 / `members` 成员，空组也要在（前端按位置编 `search-N`）；每组最多 20 条，多了 `truncated: true`；摘录是第一个命中词前后各 40 字，被截的一头加「…」，没命中就取开头 80 字。文章：已发布公开的，按 `last_published_at` 倒序，搜标题+摘要+`body_plain`，`meta` 是分类名（没有就「文章」），`url` `/news/<slug>/`。赛事与内战一组：先赛事（已发布、已结束，按 `updated_at` 倒序）后内战（同），搜标题+摘要+说明纯文本，`meta` 是「赛事」「内战」。战队：没解散的，按 `updated_at` 倒序，搜名字+简介，摘录取简介，`meta`「招募中」或「战队」。成员：成员墙上的人，按昵称排序，只搜昵称，摘录是宣言，`meta`「成员」，`url` `/members/<用户编号>/`。限流照旧回 429 | `search` |
| BE-3 | 已接 275 | `GET /api/session` | `user` 加 `can_submit_article`：`can_use(article_submit)` 本身，不看邮箱验证（`content/views.py` `submit_entry` 把「邮箱未验证」「没有投稿权限」分开列）。现在前端只能从 `caps` 里的 `articles.publish_own` 推，未验证邮箱又被禁投稿的人只看到前一条 | `submit`（只影响这一种人，种子数据里没有） |
| BE-4 | 已接 283 | `GET /api/page/news/{slug}` | 文章页正文之外的投影，逐条照 `content/models.py` `ArticlePage.get_context`：`author`（`{user_id, nickname, avatar_image_id, is_active, motto}`，作者卡用：链接 `/members/<user_id>/`、头像、宣言「…”motto“」、停用的人不显示头像）；`author_article_count`（作者已发布公开文章数）；`last_published_at`（可空；前端按「距首发超过一天」显示「更新于」）；`comment_total`（头部事实行的顶层评论数）；`older`/`newer`（同栏目按 `first_published_at` 前后最近一篇 `{slug, title}`，无首发时间时 null）；`related`（同分类排除自己、按首发时间倒序前 3 篇，形状照 `NewsItemOut` 再加 `default_cover_image_id`）；`category_slug`（面包屑和分类 tag 链接 `?category=`）；`default_cover_image_id`（分类默认封面，即 `cover_fallback`）；`tournament`（关联赛事卡，`is_public` 才给：`{id, title, phase, starts_at, registration_opens_at, registration_closes_at, cover_image_id, default_cover_image_id, roster_min, roster_max, registration_mode_label, takes_individuals, sjtu_only}`）；`seo_title`、`search_description`（页面标题和描述） | `article`（作者卡、上下篇、相关文章、关联赛事卡、SEO） |
| BE-5 | 已接 281 | `GET /api/page/news` | 列表页三样（`ArticleIndexPage.get_context`）：`categories`（有名字有 slug 的分类，按 `sort_order, name`，`{slug, name}` 数组，分类标签条）；`intro_html`（栏目简介渲染后的 HTML，`c-pagehead__lede`）；items 每项补 `default_cover_image_id`（文章卡的默认封面） | `news`（分类标签、栏目简介、默认封面） |
| BE-6 | 已接 281 | `GET /api/page/home`（含 `/api/me/agenda` 的组合） | 275 对拍（`/tmp/sjtu-ow-parity/out/report.md`）拿到三处：① `feature_tournament` 是空——种子里有整队赛（id 2），旧站画了「报名中 · 截图战队杯 · 已通过 0 队」大卡，新站整块没有，查选择逻辑/门；② `notices` 是空——旧站公告列出了 notice 分类文章，新站没有；③ 议程条目的报名链接形状不对：旧站是 `/registrations/1/`，新站 `/api/me/agenda` 给 `/tournaments/2/registrations/1/`。glm-handoff 5.1 让把 agenda 组合进 home、`feature_tournament` 补 `default_cover_image_id`（和 BE-5 同一个默认封面池）——这三条一起做 | `home`（访客像素差 56%、member 50%，大头是缺的大卡和公告） |
| BE-7 | 已接 283 | `GET /api/session` | `user` 补 `can_comment`：`can_use("article_comment")` 本身。评论区要像旧站的 `post_problems` 一样预先显示「你暂时无法使用此功能，如有疑问请联系管理员」（`accounts/permissions.py`）；后台 caps 是另一套语义，判不了这个。和 BE-3 的 `can_submit_article` 同一模式 | `article`（功能被禁的成员，种子数据里没有） |
| BE-8 | 已接 283 | `GET /api/articles/{id}/comments` 等评论接口 | `Comment` 投影补 `edited_at`（可空，RFC 3339；旧站 `comments/models.py` 有这列，Go 的 `comments/model.go` 没有）。「已编辑」标记只看它，`updated_at` 会被管理员隐藏/置顶动作带新 | `article`（编辑过的评论；种子数据里没有） |

## 交给前端（Claude）

后端需要前端跟进的字段变更与缺陷。交接规则只维护在 [改动范围与交接](OWNERSHIP.md)。

| 编号 | 状态 | 涉及 | 要做什么（依据） |
|---|---|---|---|
| FE-0 | ✓ 277（用户授权 GPT 修复） | 275 评论点赞/删除/隐藏 | 点赞无文章页 @like 监听，CComments 未声明 like；组件模板裸 confirm 报 not a function，删除/隐藏不发请求。见 276 report R1/R2 与浏览器证据 |
| FE-1 | ✓ 277（用户授权 GPT 修复） | 评论分页 | Go 返回 page_size，CComments 读 pageSize，21 条仅画 20 条且无加载更多。fixture 人工传错形状掩盖。见 276 R3 |
| FE-2 | ✓ 277（用户授权 GPT 修复） | ArticleDetail 的 SPA 状态 | thread/sort 只初始化一次，相同组件从 A 换 B 保留 A 评论；离开文章时 coverClass else 解引用 undefined.id 抛异常。见 276 R4/R5 |
| FE-3 | ✓ 277（用户授权 GPT 修复） | 评论提交状态与计数 | 提交中连点发不同幂等键的重复 POST，成功不清稿；评论区 22 条但头部仍 21（读旧 data.thread）。见 276 R6/R7 |
| FE-4 | ✓ 277（用户授权 GPT 修复） | browser-check 与最终验收 | 脚本仍要求首页 title=SJTU-OW，当前正确标题为首页 · SJTU-OW，复跑退出 1；更新预期后验最终提交，并加入评论真实点击/换页回归。见 276 R8 |

## 仍有效的运维与验收事项

| 事项 | 状态 / 下一步 |
|---|---|
| 正式站 cron | 265 回滚后仍是旧的柏林夏令时写法；2026-10-25 换冬令时前需要用户授权改成 `at-shanghai.sh`。步骤在 docs/legacy-guide.md「把正式站的 cron 换成新写法」 |
| 正式站磁盘 | 265 记录剩余 19%、healthz 503；这是当时测量，执行前重新探测。清理要用户授权，不能全局清掉别的项目缓存 |
| 异地备份 | R2 配置与正式站备份外存待用户；操作见 docs/operations.md 和旧站手册 |
| 割接与试用 | IP 试用站未部署；staging/反代、检查点 B 和割接时间仍需用户确定，验收与操作分别见 frontend-migration.md 和 cutover.md |
| 旧上线清单中未闭环的验收 | 多种真实邮箱收信、校园网与三大运营商访问、新机器 4 小时内完整恢复、外部监控与成员试用/公告仍缺最终证据；旧清单保存在 archive/status-through-277.md，后续核实后更新本表，不把历史「下一步」直接当开工任务 |
| 其他旧复核遗留 | 设计与规格清单见 docs/rewrite-research/13-ideas-and-followups.md 和 handoff/REVIEW-GUIDE.md；不在本轮文档整理中判定已修复 |

## 最近轮次

只保留最近 3 轮的摘要；新加一轮时把超出的条目移到 `archive/` 的历史记录。过去的执行结果归档，当前未完成项必须仍在上面的任务/验收表。

**286（2026-10-11，自查通过）**：全Web严格类型门进pnpm test，固定vue-tsc3.3.12/TS6.0.3/Node开发类型，不改发布保护。修实际契约/空节点/组件类型，禁PasswordHash进JSON/HTTP，兼容roles/slug/招募字段。最终 `20261011-165938-bfa53d5` 正/四负类型探针、三安全/投影变异、整组（Web15+212、预算96779）、账号真35/评论真23/桩23、四组合10/10退出0，最大0.153032%；HTTP补验 `20261011-170624-0416217` 退出0。评论旧驱动跨分钟429假设失败，改真实burst，不改业务限流。既有any/后台功能、错误态/全身份及F5–F10仍待，不标全量，无旧站/部署变更。见 `rounds/286-f1-strict-types/`。

**285（2026-10-11，自查通过）**：补账号14地址×七身份（含三非超管干部）正常/待验证态；Location比去向/来源/编码等价，跳转不跟F5目标，仅列266批准的设密码301差异。修重置码页多按钮、访客退出与已登录登录码入口；浏览器异常/CSP/500收集并Native负向探针。初次42行34/42及全组91/98退出1如实留证；最终 `20261011-154406-a7774f1` 工具四/页面三变异、整组（Web15+210、预算96697）、真实账号35与桩23/23、正常态98/98全绿退出0。68个200×四视图272对最大差0，30跳转含6批准差异；代表图人工查看一致。错误/限流态、严格类型门、F4全身份及F5–F10仍待，不标全量；无依赖/旧站/部署变更。见 `rounds/285-f3-account-parity/`。

**284（2026-10-11，自查通过）**：真实空库注册/worker本地SMTP/Go/生产SSR/真Caddy/Chromium账号旅程35项通过，涵盖验证登录、错码三次作废/重发、退出、改密会话隔离、重新认证草稿、换邮箱/取消、三步重置私有凭证与全会话撤销、防枚举页面及真实跳转。实际邮件暴露顶层MIME头落进正文，修Build并标准解析纯文本/HTML/两张PNG；宽松提取器初测27项不作最终合法收信证明，故障轮退出1如实记。最终 `20261011-151305-757bae8` 三处负向验收、Go/Web整组（15+208、预算96680）、严格真实账号35与原桩浏览器23/23全绿，退出0。账号其余四组合对拍、F4全身份和F5–F10仍待，未标整页完成；无依赖/旧站/部署改动。见 `rounds/284-f3-real-accounts/`。



## 历史记录

移出的最近轮次摘要见 [近期历史](archive/status-recent-through-279.md)。277 以前迁出的叙述、旧里程碑表与轮次总表见 [状态历史](archive/status-through-277.md)，每轮证据见 [rounds/](rounds/)。历史快照不再更新成进度；查当前下一步只看本文件头部与交接表。
