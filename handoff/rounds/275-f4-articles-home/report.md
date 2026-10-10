# 275 实现报告

## 结论

完成：BE-0–3 前端接入（`pending-api.ts` 三段删除、三页换生成类型）、文章页（含评论区）照旧模板重写并登记路由、资讯列表和首页照旧模板重写；后端缺口登记 BE-4–8。整组、browser-check、对拍结果见「验收输出」。

## 逐条结果

1. **接 BE-0/BE-1**：`pending-api.ts` 的 `SitePage` 段删除，`StandardPage.vue` 直接用生成的 `GetApiPageSlugOut`（`seo_title`、`search_description`、`last_published_at` 都在生成形状里）。content.test.ts 的普通页测试原样通过。
2. **接 BE-2**：`SearchResults`/`SearchGroup`/`searchSite` 删除，`Search.vue` 直接用 `getApiSearch` + 生成的 `GetApiSearchOut["groups"]`。旧的五份平铺列表在生成类型里保留，没有动（GLM 交接 3 的要求）。
3. **接 BE-3**：`SubmitAbility` 删除，`Submit.vue` 直接读 `ViewerUser.can_submit_article`（生成类型已带）。
4. **文章页**：`ArticleDetail.vue` 照 `content/templates/content/article_page.html`、`_toc.html` 重写；路由 `/news/:slug/`（slug 规则照 Wagtail 的 `[\\w%\\u0080-\\uffff-]+`，永不匹配点号）进 `routes.ts`——之前 404 的根因就是路由没登记。评论区按 5.1 表做成 `packages/ui` 的 `CComments`/`CCommentItem`/`CCommentReply`/`CCommentComposer` 四个组件：SSR 照 `comments/*.html` 画（访客只读+登录链接、成员 composer、管理员置顶/隐藏），动作 emit 给页面，页面调生成的评论接口后重拉整个列表——和旧站 HTMX `hx-target="#slot-article-comments"` 的 outerHTML 换新同一语义。评论的递归形状生成器表达不了（`replies` 生成成 `unknown[]`），在 `pending-api.ts` 收窄成 `CommentNode`（唯一的 cast，照 BE-2 时代的 SearchResults 先例），注明随生成器修掉删除。
   - 动作失败用 toast 显示 `error.message`，评论区保持原状（I5）；删除/隐藏的确认文案照旧模板（「删除这条评论？删除后不能恢复。」「隐藏这条评论？」「隐藏这条回复？」，浏览器原生 confirm，和 hx-confirm 一致）。
   - 登录链接照旧模板原样插值（`?next=/news/slug/`，不 urlencode）。
   - 「已编辑」标记挂在 `edited_at` 上（BE-8 之前恒不显示，因为 Go 还不发）。
   - 草稿文章（作者在前台打开自己的未发布文章）的评论接口回 404：load 只把 404 降级成空评论区（旧站 `thread()` 对未发布页就是空列表），其它错误照抛。
5. **资讯列表**：`News.vue` 照 `article_index_page.html` 重写：`CPagehead` 栏目头图（BE-5 的 banner 没来之前画场景占位图，和旧站没配置时一致）、栏目简介（有 `intro_html` 才显示）、分类标签条（`aria-current`，BE-5 之前只有「全部」）、`PostCard` 文章卡、`CPager`（`extra_query` 保留 category）。分页、每页 12 条照旧站。
6. **首页**：`Home.vue` 照 `home_page.html` 重写：首屏（`CPagehead section="home"`，`stats.hero_image_id` 或昼夜两套场景图）、两行标题、校徽齿轮、数字条（含 age）、「近期」（大图卡 facts 用 Go 拼好的字符串 + 内战行 + `CSeats`）、「资讯与公告」（置顶标记、公告行）、「战队」（`TeamTile`）；登录成员多调一个已有的 `/api/me/agenda` 画「我的安排」（slots/agenda.html 的结构：时间未定、「接下来没有报名的活动」空态）。hero 的「加入社区」照旧模板无条件渲染（260 时代是登录换成「个人中心」，和旧站不符；shell.test 的对应断言收窄到账号菜单）。
7. **后端缺口登记**：STATUS「交给后端（GPT）」加 BE-4（文章页投影）、BE-5（列表 categories/intro/默认封面）、BE-6（首页 feature 默认封面）、BE-7（会话 `can_comment`）、BE-8（评论 `edited_at`）；页面全部「有就显示」。BE-0–3 三行改「已接 275」。

## 设计偏差

无。一处测试调整需要说明：`shell.test.ts` 的「登录成员页面无 `/accounts/signup/` 链接」断言收窄到账号菜单面板——旧首页模板无条件画「加入社区」（allauth 对已登录用户自行跳走），I3/I4 以旧模板为准。

## 未完成 / 顺带发现 / 需要确认

- 对拍里文章页的作者卡、上下篇、相关文章、关联赛事卡，资讯页的分类标签/栏目简介/默认封面，首页 feature 的默认封面，都是「结构在、数据等 BE-4/5/6」：后端补齐后跑同一组对拍才能把这三行标「✓ 对拍」。
- 评论的排序/加载更多/点赞等交互的 SSR 有对照（fixture）和内容测试，真实浏览器里的点击行为要等旅程脚本（F5 阶段的任务）。
- 顺带发现：`GetApiMeAgendaOut` 的 `items[].kind` 是代码值（旧站显示的是标签文案）；首页「我的安排」的 `{{ item.kind }}` 现在原样输出。BE-4–8 之外没有为它单开行——agenda 组合进 HomePageOut（glm-handoff 5.1）时一起把 kind 投影成显示文案即可，届时在这行备注里说明。

## 改动文件

- `web/apps/site/src/pending-api.ts`：删 BE-0/1/2/3 三段；加 BE-4/5/7 形状、评论收窄
- `web/apps/site/src/pages/ArticleDetail.vue`、`News.vue`、`Home.vue`：重写
- `web/apps/site/src/pages/StandardPage.vue`、`Search.vue`、`Submit.vue`：换生成类型
- `web/apps/site/src/routes.ts`：登记 `/news/:slug/`
- `web/packages/ui/src/CComments.vue`、`CCommentItem.vue`、`CCommentReply.vue`、`CCommentComposer.vue`：新增
- `web/packages/ui/src/icons.ts`：补 `list`、`text`（照旧模板 icon.html 的路径）
- `web/packages/ui/src/types.ts`：`CommentView`
- `web/apps/site/src/testdata/legacy-comments.json`：17 组评论区旧模板真渲染参考（生成脚本 `handoff/rounds/275-f4-articles-home/legacy_fixtures.py`）
- 测试：`content.test.ts`（三页 SSR）、`ui.test.ts`（fixture 对照 + 评论区行为）、`routes.test.ts`（文章路由）、`guards.test.ts`（三页出待重写清单、v-html 白名单加两页）、`shell.test.ts`/`handle.test.ts`（按路径分发的桩）

## 验收输出

1. **整组 + browser-check（测试机后台）**，日志 `20261011-005408-8177543`：`pnpm test` 全绿（201 条，含 17 组评论区 fixture 对照）、`BUDGET-OK`（首页壳 gzip 96,636 字节，上限 307,200）。browser-check 首次随整组跑报首页探测失败（`TypeError ... querySelectorAll of null`，连接时序偶发），单独复跑日志 `20261011-005955-f6f48c4` → `BROWSER-CHECK-OK`（本地 Chrome 同样 OK）。
2. **变异自查**（本地，五处改坏→红→恢复）：评论 404 降级（4 失败）、更新阈值（1）、agenda 可见性（1）、分类 aria-current（1）、加载更多（5）。全部恢复原样后 201 条全绿。
3. **对拍**（测试机，`--only=home,news,article,about,terms,privacy,search,submit --wide --strict`，日志 `20261011-010123-cfa1a30`）：`PARITY 5/11 通过`——
   - 通过：`/about/`、`/terms/`、`/privacy/`（BE-0/1 接入后逐字通过）、`/search/?q=截图`（BE-2 接入后逐字通过）、`/submit/`（访客）。
   - `/` 访客/成员：标题差（旧「首页 · SJTU-OW」——已修，见下）；feature 大卡、公告缺（BE-6 ①②）；成员 agenda 的报名链接形状（BE-6 ③）；像素差 56.03%/50.49%（大头是缺的大卡）。
   - `/news/`：分类标签缺（BE-5）。
   - `/news/screens-guide/` 访客/成员：作者卡、作者链接、相关文章缺（BE-4）；像素差 17.21%/16.21%。
   - `/submit/` 成员：目的地后台编辑页是 F9 的空壳（STATUS 进度表 submit 行早已注明，非本轮回归）。
4. **home 对拍复验**（标题修复后，`--only=home --wide --strict`）：结果见下方补记。
5. fixture 生成：本地与测试机各自跑 `legacy_fixtures.py` 产出一致（17 组）。

## 补记（提交前最后一轮）

- 首页标题照对拍改「首页 · SJTU-OW」（旧站 HomePage 是标题为「首页」的 Wagtail 页），`content.test` 断言同步；201 条全绿。
- BE-6 行已用对拍证据充实（feature/notices 空、agenda 链接形状、像素差）。
