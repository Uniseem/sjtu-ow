# 270 F4 内容（一）：普通页、搜索、投稿

## 背景

269 之后 GPT 留了这一轮的本地草稿（一个通用的 `ServerHtml` 组件、`StandardPage.vue`，没接路由，读了接口里没有的 `last_published_at`），没提交。用户 2026-10-10：「你把前端往下推进，后端之后让 gpt 去写」。从这一轮起前端由 Claude 做，**页面要的 Go 改动不在前端轮次里写**，写成「交给后端」清单（STATUS）等 GPT 做。草稿由本轮接手重写。

## 本轮范围

做（`docs/frontend-migration.md` 6.2 的后三行）：

1. `/about/`、`/terms/`、`/privacy/` 和其他普通页 `/<slug>/`：照 `content/templates/content/standard_page.html`（三页切换标签、标题、最后更新、正文）
2. `/search/`：照 `search/templates/search/results.html`（空查询的说明、没结果、计数、四组结果、截断提示、Go 的 429 成 429 页）
3. `/submit/`：照 `content/views.py submit_entry` 和 `content/submit.html`（投稿者 302 去写文章，其余逐条说明原因）
4. 页面要用、但 Go 还没给的字段：前端照旧模板写好（有就显示），期望的形状写在 `web/apps/site/src/pending-api.ts`（带 `[BE-n]` 编号），规格写进 STATUS「交给后端（GPT）」
5. 底座顺带：`<title>` 统一由 `meta.ts` 的 `usePageMeta()` 出（`页面 · SJTU-OW`，A11 的一部分）；加载器上下文加 `viewer()`（同一次 `/api/session`，不多发请求），让 `load` 能按身份 302
6. `v-html` 白名单收回到具体页面：删掉草稿里的通用 `ServerHtml` 组件（它让任何页面都能把任意字符串塞进 `v-html`，I8）

不做：

- 不改 `server/`（Go）。普通页的最后更新、SEO 标题和描述（BE-1），搜索结果的分组和摘录（BE-2），会话里单独的投稿资格（BE-3）留给后端
- 文章页（含评论）、资讯列表、首页：下一轮起
- `vue-tsc`、`usePageMeta` 的 canonical 和 og（要 Go 给站点设置）：另轮

## 验收

- 测试机后台：整组（`sh scripts/check.sh`：Go 五项 + Web）、`browser-check`
- SSR 测试（`content.test.ts`）：三页的标签和当前项、标题格式、上海时区的最后更新、正文原样、SEO 标题和描述优先；`/<slug>/` 走普通页且 Go 的 404 照样 404；中文 slug 只编码一次；带点或多段的地址直接 404、不问 Go；固定路由优先于 slug；搜索的空查询不调 Go、计数、分组顺序和 `search-N` 编号、截断提示、没结果、429、截到 50 字；投稿的访客、投稿者 302、非投稿者、未验证邮箱、未验证且被禁
- 变异：拆掉上面几条规则（标签当前项、slug 的点号限制、空查询不调 Go、投稿者跳转、`v-html` 白名单），测试要红
- 对拍：`e2e/parity/run.sh --only=about,terms,privacy,search,submit --wide`。预期：投稿页可以通过；三个普通页差「最后更新」一行（BE-1）；搜索差摘录和分组（BE-2）。差异逐条记进报告，不算通过的不写通过
