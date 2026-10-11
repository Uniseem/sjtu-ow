# 当前状态

```yaml
milestone: 正式站 265 起回到旧站（Django），新栈前台在测试机上照 docs/frontend-migration.md 重做，和旧站对拍全绿再割接。F1 关键底座补齐（262–264，细项仍见表）；F2 第一组通过（266），267 卡片/布局已有旧模板 SSR 对照；F3 账号入口 268–269 有页面、登录/注册/找回/改密码/邮箱/退出对拍通过；F4 内容组 270–275 前端写齐（普通页/搜索/投稿对拍通过，文章页含评论区/资讯列表/首页照旧模板重写，剩余差异在 BE-4–8）。前端 Claude、后端 GLM（274 起）。
round: 279-be-comment-contracts
next_frontend: Claude：FE-0–4 已由用户授权 GPT 在 277 修复（原探针8/8、新浏览器23/23、8处变异通过）；BE-4–8 接入后补文章页/列表/首页对拍与评论真实 Go 旅程。账号组其余对拍、真实旅程、F2 样张仍待补。
next_backend: 本轮用户授权 Codex 自主接手后端，279 已完成 BE-7/8（权限/编辑时间、9处变异与整组通过），长期分工不变。下一轮先补 BE-4–6 的文章页、资讯列表、首页投影并核查公开门/统计/错误传播；之后按 request 中计划推进账号内容验收、F5–F9 页面、F10 全站验收。IP 试用站未部署，正式站继续 Django。
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
| A4 类型（嵌入摊平、`(T \| null)[]`、切片不会是 null；`vue-tsc` 等拍板） | 半 262 |
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
- **待验收/待做**：267 新组件尚未接入样张、未跑四种组合截图对拍；真实图片与默认图片池的页面投影、完整账号表单与个人中心行为仍待各页面组。评论、vue-tsc、自动保存等仍待补。F2 未完成，页面表不因公共组件通过而直接标完成。

### 前台页面进度

**264 对拍基线**：清单 48 行（现在 47 行，去掉了旧站开发设置下不公平的 404）只有 `/_styleguide/` 一行通过，其余全部「不同」；逐行的差别在 `handoff/rounds/264-f1-image-masters-parity/parity-baseline.md`。下表的「对拍」一栏，没写的就是「不同（264 基线）」。

每轮更新。格子里：`—` 没开始、`缺` 只有标题或没有路由、`错` 有但数据或结构错、`半` 近似但没照旧模板、`✓` 做完并有证据。「页面」是页面本身，「部件」是它用到的组件，「接口」是它要的后端接口，「对拍」「旅程」见文档 9.2、9.3。

| 地址 | 页面 | 部件 | 接口 | 对拍 | 旅程 |
|---|---|---|---|---|---|
| **账号入口** | | | | | |
| `/accounts/login/` | 半（268 实现） | ✓ | ✓ | ✓（268，四组合） | 桩浏览器通过，真接口未验 |
| `/accounts/signup/` | 半（268 实现） | ✓ | ✓ | ✓（268，四组合） | 同上 |
| `/accounts/confirm-email/` | 半（268 重写） | ✓ | ✓ | 未逐页验 | 桩浏览器通过 |
| `/accounts/logout/` | 半（268 实现） | ✓ | ✓ | ✓（269，四组合；占位已修） | 未验 |
| `/accounts/inactive/`、`/reauthenticate/` | 半（268 实现） | ✓ | ✓ | 未逐页验 | 未验 |
| `/accounts/password/change/` | 半（268 实现） | ✓ | ✓ | ✓（268，四组合） | 未验 |
| `/accounts/password/set/`、`/login/code/confirm/` | 半（268 真跳转） | — | — | SSR 跳转回归通过 | 未验 |
| `/accounts/password/reset/done/` | 半（268 静态说明） | ✓ | — | 未逐页验 | 未验 |
| `/accounts/email/`、`/accounts/password/reset/` | 半（269 实现） | ✓ | ✓（269 回归） | ✓（269，四组合） | 未验 |
| `/accounts/password/reset/confirm/`、`/complete/` | 半（269 实现） | ✓ | ✓（269 回归） | 未逐页验 | 未验 |
| **内容** | | | | | |
| `/` | ✓（275 照旧模板重写） | ✓ | 半（BE-6：feature/公告缺、agenda 链接形状） | 不同（BE-6；about/search/submit 访客已过） | — |
| `/news/` | ✓（275 照旧模板） | ✓ | 半（BE-5：分类标签、简介、默认封面） | 不同（BE-5） | — |
| `/news/<slug>/`（含评论） | 半（275 实现；277 修 FE-0–4，评论交互已验） | ✓（17组旧模板；277浏览器23项） | 半（BE-4/7/8） | 半（277：仍缺作者卡/相关文章，17.21%/16.21%，与275一致） | 评论桩浏览器通过；真实 Go 旅程未验 |
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
| BE-4 | 待做 | `GET /api/page/news/{slug}` | 文章页正文之外的投影，逐条照 `content/models.py` `ArticlePage.get_context`：`author`（`{user_id, nickname, avatar_image_id, is_active, motto}`，作者卡用：链接 `/members/<user_id>/`、头像、宣言「…”motto“」、停用的人不显示头像）；`author_article_count`（作者已发布公开文章数）；`last_published_at`（可空；前端按「距首发超过一天」显示「更新于」）；`comment_total`（头部事实行的顶层评论数）；`older`/`newer`（同栏目按 `first_published_at` 前后最近一篇 `{slug, title}`，无首发时间时 null）；`related`（同分类排除自己、按首发时间倒序前 3 篇，形状照 `NewsItemOut` 再加 `default_cover_image_id`）；`category_slug`（面包屑和分类 tag 链接 `?category=`）；`default_cover_image_id`（分类默认封面，即 `cover_fallback`）；`tournament`（关联赛事卡，`is_public` 才给：`{id, title, phase, starts_at, registration_opens_at, registration_closes_at, cover_image_id, default_cover_image_id, roster_min, roster_max, registration_mode_label, takes_individuals, sjtu_only}`）；`seo_title`、`search_description`（页面标题和描述） | `article`（作者卡、上下篇、相关文章、关联赛事卡、SEO） |
| BE-5 | 待做 | `GET /api/page/news` | 列表页三样（`ArticleIndexPage.get_context`）：`categories`（有名字有 slug 的分类，按 `sort_order, name`，`{slug, name}` 数组，分类标签条）；`intro_html`（栏目简介渲染后的 HTML，`c-pagehead__lede`）；items 每项补 `default_cover_image_id`（文章卡的默认封面） | `news`（分类标签、栏目简介、默认封面） |
| BE-6 | 待做 | `GET /api/page/home`（含 `/api/me/agenda` 的组合） | 275 对拍（`/tmp/sjtu-ow-parity/out/report.md`）拿到三处：① `feature_tournament` 是空——种子里有整队赛（id 2），旧站画了「报名中 · 截图战队杯 · 已通过 0 队」大卡，新站整块没有，查选择逻辑/门；② `notices` 是空——旧站公告列出了 notice 分类文章，新站没有；③ 议程条目的报名链接形状不对：旧站是 `/registrations/1/`，新站 `/api/me/agenda` 给 `/tournaments/2/registrations/1/`。glm-handoff 5.1 让把 agenda 组合进 home、`feature_tournament` 补 `default_cover_image_id`（和 BE-5 同一个默认封面池）——这三条一起做 | `home`（访客像素差 56%、member 50%，大头是缺的大卡和公告） |
| BE-7 | ✓ 279（待前端接入） | `GET /api/session` | `user` 补 `can_comment`：`can_use("article_comment")` 本身。评论区要像旧站的 `post_problems` 一样预先显示「你暂时无法使用此功能，如有疑问请联系管理员」（`accounts/permissions.py`）；后台 caps 是另一套语义，判不了这个。和 BE-3 的 `can_submit_article` 同一模式 | `article`（功能被禁的成员，种子数据里没有） |
| BE-8 | ✓ 279（待前端接入） | `GET /api/articles/{id}/comments` 等评论接口 | `Comment` 投影补 `edited_at`（可空，RFC 3339；旧站 `comments/models.py` 有这列，Go 的 `comments/model.go` 没有）。「已编辑」标记只看它，`updated_at` 会被管理员隐藏/置顶动作带新 | `article`（编辑过的评论；种子数据里没有） |

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

**279（2026-10-11，自查通过）**：用户授权先规划再自主推进，Codex 本轮接手后端；BE-7 session.can_comment 独立于邮箱/后台能力，BE-8 评论独立 edited_at 与旧库导入，00019 升级不虚构历史；相同正文不记编辑。测试机最终 `20261011-122024-44ae78e`：9处可编译变异、Go/Web整组（15 + 202）、apigen一致、预算96649字节通过，退出0。前端接入、文章对拍与真实Go旅程未验证，不标整页完成；下一轮BE-4–6。无依赖或部署改动，长期分工不变。见 `rounds/279-be-comment-contracts/`。

**278（2026-10-11，自查通过）**：用户授权重组文档入口；AGENTS 314→36、README 550→35、STATUS 1069→177 行，分工/验收/运维/踩坑按需读取；旧手册和状态原文另存历史，当前表保留，长期前后端分工不变。测试机 `20261011-021035-9ea4624` 文档审计（100 链接/79 坑/15 范围/105 行表/历史逐字/28 小节）及 Go/Web 整组（15 + 202）退出 0，预算 96649 字节；首轮审计路径比对误报已修，最终文档收尾 `20261011-021222-2d95457`（20 文件/100 链接）也退出 0。没有网站代码、依赖、生成契约或部署改动。见 `rounds/278-docs-navigation/`。

**277（2026-10-11，自查通过）**：用户明确「你开始改吧」，GPT 获本轮前端范围例外，修 FE-0–4：点赞监听、显式原生确认、Go page_size 契约、SPA 状态/旧响应隔离、空文章渲染、提交同步防重/失败留稿/成功复位、实时头部计数；多页操作刷新不丢已加载范围。默认 browser-check 增加真实评论浏览器回归。最终 `20261011-013837-db781c7`：17组旧参考字节一致、8个可编译变异、Go/Web整组（15 + 202）、原复核8/8、新浏览器23/23通过，退出0。文章四组合对拍 `20261011-014720-6937a5a` 仍0/2（BE-4），17.21%/16.21%与275一致，无新增差异；不标整页完成、不部署。长期仍 Claude 前端/GLM 后端，BE-4–8未动。见 `rounds/277-f4-comment-review-fixes/`。


## 历史记录

移出的最近轮次摘要见 [近期历史](archive/status-recent-through-279.md)。277 以前迁出的叙述、旧里程碑表与轮次总表见 [状态历史](archive/status-through-277.md)，每轮证据见 [rounds/](rounds/)。历史快照不再更新成进度；查当前下一步只看本文件头部与交接表。
